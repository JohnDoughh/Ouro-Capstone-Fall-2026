"""Team C Sprint 5: an offline HTML view of an intent report.

Renders only what is already in the JSON report: no database access, no free
text, no viewer or coder IDs. The page has no scripts and no external
resources, and the same report always gives the same bytes. It is bound to its
report by the report's SHA-256, shown in the footer.
"""
from __future__ import annotations

import hashlib
from html import escape

from .contracts import INTENT_FIELDS
from .intent_metrics import render_intent_report

# Five recovery-rate bins on one blue ramp (light mode low->high, dark mode
# low->high). Index = bin. Text ink is chosen per bin for contrast.
BINS = [(0.2, "0-19%"), (0.4, "20-39%"), (0.6, "40-59%"), (0.8, "60-79%"), (1.01, "80-100%")]
SURVIVAL_LABEL = {
    "survived": "✓ survived",
    "not_survived": "✕ not survived",
    "pending_adjudication": "… coders disagree",
    "incomplete_coding": "… coding incomplete",
    "insufficient_responses": "too few responses",
    "not_applicable": "— not intended",
}
STYLE = """
:root{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--muted:#6f6e69;
--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--na:#f0efec;--hatch:#d6d5ce;
--b0:#cde2fb;--b1:#86b6ef;--b2:#3987e5;--b3:#1c5cab;--b4:#0d366b;
--i0:#0b0b0b;--i1:#0b0b0b;--i2:#0b0b0b;--i3:#ffffff;--i4:#ffffff;
--warn-bg:#fff4dc;--warn-ink:#5c4100;--warn-ring:#fab219}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--surface:#1a1a19;--page:#0d0d0d;--ink:#f0efec;--ink2:#c3c2b7;--muted:#a3a29b;
--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--na:#262624;--hatch:#383835;
--b0:#184f95;--b1:#256abf;--b2:#3987e5;--b3:#86b6ef;--b4:#cde2fb;
--i0:#ffffff;--i1:#ffffff;--i2:#0b0b0b;--i3:#0b0b0b;--i4:#0b0b0b;
--warn-bg:#3a2c08;--warn-ink:#fbd78a;--warn-ring:#fab219}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1120px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 8px}
p{margin:6px 0}.muted{color:var(--muted)}.ink2{color:var(--ink2)}
.banner{background:var(--warn-bg);color:var(--warn-ink);border:1px solid var(--warn-ring);
border-radius:8px;padding:10px 14px;margin:12px 0 20px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(150px,100%),1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:8px;padding:12px 14px}
.tile .v{font-size:24px;font-weight:600}.tile .k{color:var(--ink2);font-size:13px}
.scroll{overflow-x:auto;background:var(--surface);border:1px solid var(--ring);border-radius:8px}
table{border-collapse:separate;border-spacing:2px;width:100%}
th,td{padding:6px 8px;text-align:left;vertical-align:top}
thead th{color:var(--ink2);font-weight:600;font-size:13px;border-bottom:1px solid var(--axis)}
.plain td,.plain th{border-bottom:1px solid var(--grid)}
.plain{border-spacing:0}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.heat td.c{min-width:112px;border-radius:4px;font-size:12px;line-height:1.35}
.heat th.sep,.heat td.sep{border-left:2px dashed var(--axis)}
.c .r{font-size:15px;font-weight:600}
.b0{background:var(--b0);color:var(--i0)}.b1{background:var(--b1);color:var(--i1)}
.b2{background:var(--b2);color:var(--i2)}.b3{background:var(--b3);color:var(--i3)}
.b4{background:var(--b4);color:var(--i4)}
.na{background:repeating-linear-gradient(45deg,var(--na) 0 6px,var(--hatch) 6px 7px);color:var(--ink2)}
.flag{display:inline-block;margin-top:2px;font-weight:600}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;margin:10px 0;font-size:13px;color:var(--ink2)}
.sw{display:inline-block;width:22px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:4px;
border:1px solid var(--ring)}
code{font:12px ui-monospace,SFMono-Regular,Consolas,monospace;word-break:break-all}
footer{margin-top:36px;color:var(--ink2);font-size:13px}
"""


def _pct(rate) -> str:
    return "—" if rate is None else f"{round(rate * 100)}%"


def _ci(ci) -> str:
    if not ci or ci[0] is None:
        return "—"
    return f"{round(ci[0] * 100)}–{round(ci[1] * 100)}%"


def _num(value, digits=2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _bin(rate: float) -> int:
    return next(index for index, (upper, _) in enumerate(BINS) if rate < upper)


def _label(name: str) -> str:
    return name.replace("_", " ")


def _table(headers: list[str], rows: list[list[str]], numeric: set[int] = frozenset()) -> str:
    if not rows:
        return '<p class="muted">None.</p>'
    head = "".join(f'<th{" class=num" if i in numeric else ""} scope="col">{escape(h)}</th>'
                   for i, h in enumerate(headers))
    body = "".join(
        "<tr>" + "".join(f'<td{" class=num" if i in numeric else ""}>{cell}</td>'
                         for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="scroll"><table class="plain"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _heat_cell(cell: dict, separator: bool) -> str:
    recovery = cell["recovery"]
    decided = cell["survival"] in {"survived", "not_survived"}
    css = f"b{_bin(recovery['rate'])}" if decided and recovery["rate"] is not None else "na"
    flags = []
    if cell["ambiguity"]["ambiguous"]:
        flags.append("◆ ambiguous")
    if cell["coder_disagreement"]["disagreed"]:
        flags.append(f"coders split {cell['coder_disagreement']['disagreed']}/"
                     f"{cell['coder_disagreement']['multi_coded']}")
    if cell["contradicted"]["count"]:
        flags.append(f"{cell['contradicted']['count']} contradicted")
    tip = (f"{cell['clip']} · {_label(cell['component'])}: {SURVIVAL_LABEL[cell['survival']]}; "
           f"recovered {recovery['count']} of {recovery['n']} "
           f"(95% CI {_ci(recovery['ci95'])}); delivery {_label(cell['delivery'])}")
    if decided:
        rate = (f'<div class="r">{_pct(recovery["rate"])}</div>'
                f'<div>{recovery["count"]}/{recovery["n"]}</div>')
    elif recovery["n"]:
        # No percentage: it would read as a result, and only agreed codes are counted.
        rate = f'<div>{recovery["count"]}/{recovery["n"]} agreed codes recovered</div>'
    else:
        rate = ""
    return (
        f'<td class="c {css}{" sep" if separator else ""}" title="{escape(tip)}">'
        f'{rate}<div>{escape(SURVIVAL_LABEL[cell["survival"]])}</div>'
        + ("" if cell["delivery"] == "not_intended" else f'<div>{escape(_label(cell["delivery"]))}</div>')
        + "".join(f'<div class="flag">{escape(flag)}</div>' for flag in flags)
        + "</td>"
    )


def _heatmap(cells: list[dict], exploratory: list[str]) -> str:
    clips = sorted({cell["clip"] for cell in cells})
    by_key = {(cell["clip"], cell["component"]): cell for cell in cells}
    fields = [f for f in INTENT_FIELDS if any((clip, f) in by_key for clip in clips)]
    first_exploratory = next((f for f in fields if f in exploratory), None)
    head = "".join(
        f'<th scope="col"{" class=sep" if f == first_exploratory else ""}>{escape(_label(f))}'
        f'{"<br><span class=muted>exploratory</span>" if f in exploratory else ""}</th>'
        for f in fields
    )
    rows = []
    for clip in clips:
        tds = "".join(
            _heat_cell(by_key[(clip, f)], f == first_exploratory) if (clip, f) in by_key
            else '<td class="c na">no data</td>'
            for f in fields
        )
        rows.append(f'<tr><th scope="row">{escape(clip)}</th>{tds}</tr>')
    legend = "".join(f'<span><span class="sw b{i}"></span>{escape(text)}</span>'
                     for i, (_, text) in enumerate(BINS))
    return (
        f'<div class="legend"><span>Recovery rate:</span>{legend}'
        '<span><span class="sw na"></span>no decided result</span>'
        '<span>◆ ambiguous (pre-registered)</span></div>'
        f'<div class="scroll"><table class="heat"><thead><tr><th scope="col">clip</th>{head}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )


def render_intent_html(report: dict) -> bytes:
    """The HTML view of one intent report. Deterministic: same report, same bytes."""
    results = report["results"]
    cells = results["cells"]
    exploratory = report["parameters"]["exploratory_components"]
    primary_cells = [c for c in cells if c["role"] == "primary"]
    agreement = results["agreement"]["primary_nominal"]
    disruption = results["comprehension_disruption_primary"]
    survival_counts = {}
    for cell in primary_cells:
        survival_counts[cell["survival"]] = survival_counts.get(cell["survival"], 0) + 1
    report_sha = hashlib.sha256(render_intent_report(report)).hexdigest()

    tiles = [
        (str(results["responses"]), "viewer responses"),
        (str(report["inputs"]["coders"]), "coders"),
        (_num(agreement["alpha"]), f"Krippendorff's alpha, primary nominal (95% CI "
                                   f"{_num(agreement['ci95'][0])}–{_num(agreement['ci95'][1])}); "
                                   f"{_label(agreement['interpretation'])}"),
        (f"{survival_counts.get('survived', 0)} / {survival_counts.get('not_survived', 0)}",
         "primary cells survived / not survived"),
        (str(survival_counts.get("pending_adjudication", 0)), "primary cells waiting on adjudication"),
        (_pct(disruption["rate"]), f"comprehension disruption ({disruption['count']} of {disruption['n']} "
                                    "delivered primary components)"),
    ]
    tiles_html = "".join(f'<div class="tile"><div class="v">{escape(v)}</div><div class="k">{escape(k)}</div></div>'
                         for v, k in tiles)

    def cell_row(c: dict) -> list[str]:
        return [escape(c["clip"]), escape(_label(c["component"])), escape(_label(c["delivery"])),
                f'{c["recovery"]["count"]}/{c["recovery"]["n"]}', _pct(c["recovery"]["rate"]),
                _ci(c["recovery"]["ci95"]), str(c["contradicted"]["count"])]

    cell_headers = ["clip", "component", "delivery", "recovered", "rate", "95% CI", "contradicted"]
    not_survived = [cell_row(c) for c in primary_cells if c["survival"] == "not_survived"]
    pending = [[escape(c["clip"]), escape(_label(c["component"])),
                f'{c["coder_disagreement"]["disagreed"]} of {c["coder_disagreement"]["multi_coded"]}']
               for c in primary_cells if c["survival"] == "pending_adjudication"]
    ambiguous = [[escape(c["clip"]), escape(_label(c["component"])),
                  "yes" if c["ambiguity"]["viewers_split"] else "no",
                  "yes" if c["ambiguity"]["coders_split"] else "no"]
                 for c in primary_cells if c["ambiguity"]["ambiguous"]]
    by_delivery = [[escape(_label(k)), f'{v["recovery"]["count"]}/{v["recovery"]["n"]}',
                    _pct(v["recovery"]["rate"]), _ci(v["recovery"]["ci95"]),
                    _pct(v["contradicted"]["rate"])]
                   for k, v in results["by_delivery_primary"].items()]
    by_component = [[escape(_label(k)) + (" (exploratory)" if k in exploratory else ""),
                     f'{v["recovery"]["count"]}/{v["recovery"]["n"]}', _pct(v["recovery"]["rate"]),
                     _ci(v["recovery"]["ci95"]), _num(results["agreement"]["by_component_nominal"].get(k))]
                    for k, v in results["by_component"].items()]
    calibration = results["viewer_calibration"]
    calib_rows = [[escape(_label(k)), str(v["n"]), _num(v["mean_certainty"]), str(v["could_not_tell"])]
                  for k, v in calibration["by_reference_code"].items()]
    wrong = calibration["confidently_wrong"]
    agreement_rows = [
        [escape(_label(name)), _num(a["alpha"]), f'{_num(a["ci95"][0])}–{_num(a["ci95"][1])}',
         str(a["pairable_units"])]
        for name, a in (("primary nominal", agreement),
                        ("exploratory ordinal", results["agreement"]["exploratory_ordinal"]),
                        ("exploratory tone nominal", results["agreement"]["exploratory_tone_nominal"]))
    ]
    inputs = report["inputs"]
    bindings = [
        ("report JSON (canonical rendering)", report_sha),
        ("response freeze", inputs["response_freeze_sha256"]),
        ("record commitments", inputs["commitments_sha256"]),
        ("codes", inputs["codes_sha256"]),
    ] + [(f"record {r['relative_path']}", r["record_sha256"]) for r in inputs["revealed_records"]]
    params = report["parameters"]
    versions = report["versions"]
    pilot = report.get("pilot")

    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intent fidelity report</title>
<style>{STYLE}</style></head>
<body><main>
<h1>Intent fidelity report</h1>
<p class="ink2">Team C. Did each clip's intended meaning survive for its viewers?</p>
<div class="banner" role="note"><strong>{"Synthetic demo. " if report["synthetic_demo"] else ""}Not a research finding.</strong>
{escape(report["disclaimer"])}{" " + escape(pilot["note"]) if pilot else ""}</div>
<div class="tiles">{tiles_html}</div>

<h2>Clip × component</h2>
<p class="ink2">Each cell: share of viewers whose agreed code is <em>recovered</em>, with the survival
decision under the pre-registered rule ({escape(params["survival_rule"])}; at least
{params["min_responses_for_survival"]} responses). Hover a cell for its confidence interval.
Cells without a decided result are hatched. Tone is exploratory and never enters the primary result.</p>
{_heatmap(cells, exploratory)}

<h2>Failure views</h2>
<h3>Primary cells that did not survive</h3>
{_table(cell_headers, not_survived, {3, 4, 6})}
<h3>Waiting on adjudication (coders disagree)</h3>
<p class="ink2">Survival is not decided here until a separate adjudication exists.</p>
{_table(["clip", "component", "responses where coders disagree"], pending, {2})}
<h3>Ambiguous cells (pre-registered reference class)</h3>
{_table(["clip", "component", "viewers split", "coders split"], ambiguous)}

<h2>Recovery by delivery code (primary components)</h2>
{_table(["delivery", "recovered", "rate", "95% CI", "contradicted"], by_delivery, {1, 2, 4})}

<h2>Recovery by component</h2>
{_table(["component", "recovered", "rate", "95% CI", "alpha (nominal)"], by_component, {1, 2, 4})}

<h2>Coder agreement</h2>
{_table(["measure", "alpha", "95% CI", "pairable units"], agreement_rows, {1, 3})}

<h2>Viewer certainty vs coded recovery</h2>
<p class="ink2">Human calibration only; separate from any evaluator calibration.
Confidently wrong ({escape(wrong["definition"])}): {wrong["count"]} of {wrong["n"]}.</p>
{_table(["agreed code", "n", "mean certainty (1–5)", "could not tell"], calib_rows, {1, 2, 3})}

<h2>Not in this report</h2>
<p>Evaluator comparison: <strong>{escape(_label(report["evaluator_comparison"]["status"]))}</strong>,
{escape(report["evaluator_comparison"]["reason"])}.</p>
<p>Persuasion: <strong>{escape(_label(report["persuasion"]["status"]))}</strong>,
{escape(report["persuasion"]["reason"])}.</p>

<footer>
<h2>Bindings and parameters</h2>
<p>Seed {params["seed"]}, {params["bootstrap_samples"]} bootstrap samples ({escape(params["bootstrap_resampling"])}).
Report {escape(report["intent_report_version"])}; intent contract {escape(versions["intent_contract"])};
codebook {escape(", ".join(versions["codebooks"]))}; code commit <code>{escape(versions["code_commit"])}</code>.</p>
{_table(["input", "SHA-256"], [[escape(k), f"<code>{v}</code>"] for k, v in bindings])}
</footer>
</main></body></html>
"""
    return body.encode()
