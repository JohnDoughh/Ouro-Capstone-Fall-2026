# Team C operator guide: running an intent fidelity study

For anyone who has to run the intent study without the people who built it.
It covers who does what, every command in order, what each one prints, what
cannot be undone, and what to do when something refuses. What the system does
**not** do is in [`TEAM_C_LIMITATIONS.md`](TEAM_C_LIMITATIONS.md); read it
before you present any result.

Everything you can run today is synthetic or a team dry run. No real
(non-team) viewer may take part until FIU records a human-subjects
determination.

## 1. What the system does

The question: can viewers recover what an ad was meant to say? It works in
two stages so that no one is influenced by the answers:

1. **Stage 1, viewers.** Viewers watch each clip (limited plays) and write
   what they understood for seven components: audience, problem, product, key
   benefit, support, call to action, tone. They never see the intended answers.
2. **Freeze.** The responses are exported and their SHA-256 is recorded.
   Collection closes for good.
3. **Reveal.** Only now are the sealed intent records opened. Each must
   match the SHA-256 commitment published before the study.
4. **Stage 2, coders.** At least two coders, working separately, compare each
   response with the record, using `docs/INTENT_CODEBOOK.md`. A coder never
   codes a clip they watched as a viewer.
5. **Report.** `intent-report` computes recovery, survival, agreement
   (Krippendorff's alpha), calibration and ambiguity, as JSON plus an offline
   HTML view.

Every stored response, play, freeze, reveal and code is append-only. Nothing
is edited after the fact; disagreement is kept.

## 2. Roles

| Role | Does | Must not |
|---|---|---|
| Operator | Runs the commands, starts and stops the server, records hashes | Open the sealed records before the freeze |
| Viewer | Answers in the browser | See the codebook, records, README in `data/public_intent`, or other answers |
| Reveal custodian | Holds the sealed records; hands them over only after the freeze | Be a coder |
| Coder (2 or more) | Codes their own sheet | Code a clip they viewed; see others' codes |
| Adjudicator | Settles coder disagreements | *Not built yet; see limitations* |

One person can be the operator and a coder, but never a viewer *and* a coder of
the same clip (the coding sheet enforces this).

## 3. Before you start

- Python 3.11 or later, Git, and a web browser. No packages to install, no
  internet needed: everything runs on `127.0.0.1`.
- From the repository root, check the installation (about 30 seconds):

  ```
  python -m ouro_eval_lab.cli intent-pilot --out data/exports/intent-pilot.json --html data/exports/intent-pilot.html --expect team_c/intent_pilot/EXPECTED_SHA256
  ```

  It must end with `matches team_c/intent_pilot/EXPECTED_SHA256`. If not,
  stop: the code or your checkout differs from what was tested.
- Use **one database per study**, under `data/` (ignored by Git). Never reuse
  a PASS/HOLD annotation database. The server refuses to mix them.
- At any point, `intent-status` tells you where you are and the next command:

  ```
  python -m ouro_eval_lab.cli intent-status --db data/intent-study.db
  ```

  It only reads. Its output has no IDs or answers, so it is safe to paste into
  the team channel.

## 4. Running a study, step by step

Replace `data/intent-study.db` with your database. Write down every SHA-256
the commands print, in the run log (section 7).

| # | Stage | Command | Expect |
|---|---|---|---|
| 1 | Check the clips | `python -m ouro_eval_lab.cli verify --manifest data/public_intent/manifest.json` | `"verified": 4` |
| 2 | Create the study | `python -m ouro_eval_lab.cli ingest --db data/intent-study.db --manifest data/public_intent/manifest.json` | `ingested 4 verified artifacts` |
| 3 | Collect | `python -m ouro_eval_lab.cli serve --db data/intent-study.db --study intent --play-limit 2` | Open `http://127.0.0.1:8080`, enter a pseudonymous viewer ID (e.g. `viewer_07`, never a name or phone number) |
| 4 | Check progress | `intent-status` | `stage: collecting`; a warning until every clip has 3 responses |
| 5 | **Freeze** (irreversible) | Stop the server (Ctrl+C), then `python -m ouro_eval_lab.cli export-intent --db data/intent-study.db --out data/exports/intent-responses.json` | `froze N intent responses` and `sha256 …`. Record the hash |
| 6 | Reveal | Custodian provides the records directory, then `python -m ouro_eval_lab.cli reveal --db data/intent-study.db --records <directory>` | `revealed 4 intent records after freeze …` |
| 7 | Coding sheets | Per coder: `python -m ouro_eval_lab.cli intent-coding-sheet --db data/intent-study.db --coder coder_a --out data/exports/coding/coder_a.csv` | `issued a sheet of N items`. Give each sheet only to its coder |
| 8 | Import codes | Per coder, after filling `code`, `confidence`, `note`: `python -m ouro_eval_lab.cli intent-import-codes --db data/intent-study.db --coder coder_a --codes data/exports/coding/coder_a.csv` | `imported N codes`. Blank rows are skipped, so a coder can import in parts |
| 9 | Report | `python -m ouro_eval_lab.cli intent-report --db data/intent-study.db --out data/exports/intent-report.json --html data/exports/intent-report.html` | `sha256 …`. Running it again gives the same hash |

Open the HTML file in any browser; it works offline. It is labelled
"Synthetic demo. Not a research finding." and must stay so until the gates in
`CURRENT_STATUS.md` are met.

### What cannot be undone

- **The freeze (step 5)** closes collection permanently for that database.
  Browsers show "collection closed"; late answers are refused. Running
  `export-intent` again writes the same file with the same hash and records
  another freeze row; it never reopens collection.
- **Imported codes (step 8)** cannot be changed. Re-importing the same file is
  a no-op; a changed code is refused. Check the sheet before importing.
- **Never delete or edit the database** to "fix" something. To back it up,
  stop the server and copy the `.db` file.

## 5. Coder calibration with the practice anchors

Before the codebook is frozen, every coder codes the practice anchors on
their own (codebook §6). The anchors are invented examples, never study clips.

```
python -m ouro_eval_lab.cli intent-anchors sheet --anchors team_c/anchors/practice_anchors.json --out data/exports/anchors-coder_a.csv
python -m ouro_eval_lab.cli intent-anchors check --anchors team_c/anchors/practice_anchors.json --codes data/exports/anchors-coder_a.csv
```

`check` prints how many anchors match the expected code and lists each
mismatch by anchor ID. Discuss mismatches as a team; change the codebook only
where it was unclear. Anchor codes are never stored with study codes.

If the codebook text changes, `intent-anchors` refuses the set ("codebook
text has changed"). That is deliberate. After the team agrees the change,
re-bind: put the printed codebook SHA-256 into the set's `codebook_sha256`,
then the set's new SHA-256 into `practice_anchors.sha256`, in the same
commit as the codebook change.

## 6. When something refuses

Refusals never echo answers or intent text, so they are safe to share.

| Message (start) | Meaning | Do this |
|---|---|---|
| `no clips in …; first run: … ingest` | `serve` was started on an empty database | Run step 2, then start the server again |
| `no database at …` | `intent-status` was given a path that does not exist | Check the path. Status never creates a database |
| `database already holds PASS/HOLD annotations` | Wrong database | Use a separate database for the intent study |
| `no intent responses to freeze` | Nothing was collected | Collect first |
| `reveal check failed: clipNN.intent.json: missing` | Records directory incomplete | Ask the custodian for all records; never edit a record |
| `reveal check failed: clipNN.intent.json: SHA-256 does not match the commitment` | A record is not the one committed before the study | Stop. Do not reveal. Report to the custodian |
| `no response freeze is recorded; run export-intent before any reveal` | Step 5 not done | Freeze first; this order protects blinding |
| `coder already has a sheet built with seed …` | One sheet per coder | Re-run with the same (default) seed to rebuild the same sheet |
| `no items for this coder` | Nothing frozen, or the coder viewed every clip | Pick a coder who was not a viewer of these clips |
| `no coding sheet was issued to this coder` | Import before step 7 | Issue the sheet first |
| import: `a note is required …` | `partially_recovered`, `contradicted` or confidence 1 without a note | Add the note and import again |
| import: `a not_intended component must be coded not_applicable` | Codebook rule | Fix that row |
| `no intent records are revealed; nothing to report` or `no intent codes are imported` | Report run too early | Run `intent-status` to see what is missing |
| `pilot report SHA-256 … does not match` | Code or checkout differs from what was tested | If the change was deliberate, update `team_c/intent_pilot/EXPECTED_SHA256` in the same commit and say why |
| browser shows "Save status is unknown … Retry the same judgment" | Server stopped or busy mid-save | Restart the server if needed and press Retry; the server keeps exactly one copy of an identical answer |

## 7. Run log (copy for each session)

```
Date / operator (pseudonymous):
git rev-parse HEAD:
OS / Python version:
Database file:
Viewers (pseudonymous IDs) and clips each saw:
Freeze SHA-256:
Commitments file SHA-256 (sha256sum data/public_intent/intent_commitments.sha256):
Coders and sheet SHA-256s:
Import SHA-256s:
Report SHA-256 (first run / second run):
Anything that failed or needed help:
```

## 8. Recorded walkthrough (2026-11-13)

This walkthrough was recorded on a fresh database, following sections 3–5
exactly, to show the system can be operated from this guide. Environment:
Windows 11, Python 3.14.7, branch `team-c/sprint5-failure-views`. Three
dry-run viewers answered all four fictional clips through the same HTTP calls
the browser makes. Answers were placeholder text, so nothing here is a
finding. Hashes of local files (freeze, sheets) differ on every run because
they contain random IDs and times; the pilot and report hashes do not.

| Step | Command (abridged) | Result |
|---|---|---|
| Status, no database | `intent-status --db …/intent-walk.db` | refused: `no database …`, exit 2, nothing created |
| Serve, empty database | `serve … --study intent` | refused: `no clips …; first run: … ingest`, exit 2 |
| Verify clips | `verify --manifest data/public_intent/manifest.json` | `"verified": 4` |
| Ingest | `ingest …` | `ingested 4 verified artifacts` |
| Status | `intent-status` | `stage: collecting`, 4 clips, warning: needs 3 viewers per clip |
| Collect | 3 viewers × 4 clips | every play `201`, every save `201`, every identical retry `200`; no artifact ID, hash, path or intent text in any `/api/next` reply |
| Status | `intent-status` | `stage: collecting`, 12 responses, 3 per clip, no warning |
| Freeze | `export-intent …` | `froze 12 intent responses`, SHA-256 recorded, "collection is now closed" |
| Late viewer | `GET /api/next?rater=dryrun_v4` | `"collection_closed": true`, no assignment |
| Status | `intent-status` | `stage: frozen`, freeze SHA-256 shown, next: reveal by custodian |
| Reveal without records | `reveal --records <empty>` | refused: `clip01.intent.json: missing; …`, exit 2 |
| Pilot end to end | `intent-pilot … --workdir … --expect …` | `sha256 12807ee8…4b27`, `matches team_c/intent_pilot/EXPECTED_SHA256` |
| Status of pilot DB | `intent-status --db …/pilot.db` | `stage: coded`, 30 responses, 2 coders, 420 of 420 items coded |
| Report twice | `intent-report …` (×2) | same SHA-256 both times (`4cbac652…91cd`) |
| Sheet again | `intent-coding-sheet --coder pilot_coder_a` | `rebuilt the recorded sheet of 210 items`, same hash |
| Anchors | `intent-anchors verify --pinned …` | `11 anchors, codebook 0.1-draft` |
| Calibration | `intent-anchors sheet`, fill, `check` | `10 of 11 anchors match`; `P1-06: expected partially_recovered, coded not_recovered` (the deliberate mismatch) |

Two things the walkthrough found, both now fixed and tested: the server
used to start on an empty database and show every viewer "0 of 0 clips", and
the first version of `intent-status` counted people who only opened the page
as viewers.

Not covered by this walkthrough: a reveal of the real sealed records (only the
custodian can do that), and a run by someone who did not build the system,
which is still to do (`docs/INDEPENDENT_RERUN.md`).
