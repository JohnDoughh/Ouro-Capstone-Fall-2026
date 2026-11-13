# Intent codebook (Team C, Stage 2)

Status: **DRAFT v0.1, not frozen.** Freeze it with the pre-registration
(`docs/TEAM_C_PREREGISTRATION.md`), after a calibration round on the practice
anchors below. Changes after any study response is coded are dated amendments.

Coders use this codebook to compare each frozen viewer response with the
revealed intent record, one component at a time. It must agree with the coding
scale in the pre-registration (§4).

**Viewers must never see this document.** Coders read it only after the
response freeze and reveal. The worked examples use invented practice ads that
are not in the study set, so the examples cannot hint at the answers for
`data/public_intent`.

## 1. Who codes, and how

- A coder never codes a clip they watched as a viewer.
- Coders work independently. They do not see viewer IDs, other coders' codes, or
  any evaluator output.
- The unit is one (response, component) pair. Code each component on its own;
  do not let a good answer on one component raise the code for another.
- Compare the response with the record's `text` for that component. Judge
  meaning, not wording, spelling or grammar.
- Code what the viewer wrote, not what you think they meant. If the answer is
  ambiguous between two readings, use the less generous one and say why in the
  note.

- You receive a CSV sheet from `intent-coding-sheet`. Fill in only the
  `code`, `confidence` and `note` columns; leave a row blank if you have not
  coded it yet. Import with `intent-import-codes`. A code cannot be changed
  once imported, so check before you import. The import enforces the
  `not_applicable` rule and the note rule below.

## 2. Recovery scale

| Code | Use when |
|---|---|
| `recovered` | The response states the intended content in any wording. A synonym, paraphrase or more specific correct statement counts. |
| `partially_recovered` | The response contains part of the intended content, or a correct but clearly vaguer version of it. |
| `not_recovered` | The response is blank, “could not tell”, off-topic, or too generic to show the intended content. |
| `contradicted` | The response states content that conflicts with the record. The meaning was distorted, not just lost. |
| `not_applicable` | The record's `delivery` is `not_intended`. Use this whatever the viewer wrote. |

Each code also gets a coder confidence: 1 (unsure), 2 (fairly sure),
3 (sure). Add a short note for any `partially_recovered`, `contradicted`, or
confidence-1 code.

### Decision rules

1. **Recovered vs partial.** If the record has two key parts (for example a
   product type and what it does), naming both is `recovered`; naming one is
   `partially_recovered`.
2. **Generic answers.** An answer that would fit almost any ad (“people who want
   a good product”, “buy it”) is `not_recovered`, not partial.
3. **Extra content.** Extra correct detail is fine. Extra *incorrect* detail
   that changes the meaning of the component is `contradicted`; incorrect detail
   that is merely added on is noted but does not lower an otherwise correct
   code.
4. **Contradicted beats partial.** If a response contains both a correct part
   and a conflicting claim about the same component, code `contradicted`.
5. **Could not tell.** A viewer who ticked “could not tell” is `not_recovered`.
   The viewer's own certainty is never used to choose the code.
6. **Wrong component.** If the viewer put the right content under the wrong
   question (for example the benefit under “problem”), code each component only
   from its own answer. Note the swap.

## 3. Delivery codes

The sponsor's `delivery` value says how the creator meant the component to
come through. It never changes what counts as recovered, except for
`not_intended`.

| Delivery | Coding rule |
|---|---|
| `explicit_text` | Code as usual. |
| `implied` | Code as usual. An inference that matches the intent is `recovered`. |
| `visual_only` | Code as usual. Viewers may describe the image rather than name it; that is fine. |
| `partially_delivered` | Code as usual against the full intended text. Recovering only the delivered part is usually `partially_recovered`. |
| `omitted_in_edit` | Code as usual. A low recovery rate here is the expected result, not a viewer failure. Analysis reports it as its own stratum. |
| `not_intended` | Always `not_applicable`. Never code it `not_recovered`: the creator did not try to communicate it. |

## 4. Component guidance

| Component | Recovered means the viewer identified… |
|---|---|
| `audience` | who the ad is aimed at, as specifically as the record says. |
| `problem` | the situation or pain the ad opens with. |
| `product` | what the product is (its type and, if the record says so, its name). |
| `key_benefit` | the main promised outcome. A feature without its outcome is usually partial. |
| `support` | the evidence, demonstration or detail offered for the benefit. If the creator meant to give none, the record says `not_intended` and the code is `not_applicable`. |
| `call_to_action` | the action the ad asks for. The right action with the wrong channel is partial. |
| `tone` | the intended tone. Exploratory only; never part of the primary outcome. |

## 5. Practice anchors (invented, not in the study set)

### Anchor P1: “Lumastep” running shoe

Record (summary): audience *runners*; problem *heavy shoes slow you down*;
product *Lumastep, a running shoe*; key benefit *feels weightless*; support
none (`delivery: not_intended`); call to action *“link in bio”*; tone *upbeat*.

| Component | Viewer wrote | Code | Why |
|---|---|---|---|
| `key_benefit` | “so light you forget you're wearing them” | `recovered` | Same meaning, different words. |
| `key_benefit` | “it's a comfortable shoe” | `partially_recovered` | Related but vaguer than “weightless”. |
| `key_benefit` | “it's waterproof” | `contradicted` | States a different benefit. |
| `product` | “some kind of shoe” | `partially_recovered` | Type without the running context or name, when the record has both. |
| `call_to_action` | “buy it” | `not_recovered` | Generic; fits any ad. |
| `call_to_action` | “check their website” | `partially_recovered` | Right action, wrong channel. |
| `support` | “they said it's the lightest shoe ever” | `not_applicable` | Support was `not_intended`; whatever the viewer wrote is not coded. |

### Anchor P2: “Quillpad” notebook app

Record (summary): audience *students*; problem *notes scattered across apps*;
product *Quillpad, a note-taking app*; key benefit *all notes in one place*;
support *screen shows notes syncing across devices* (`visual_only`); call to
action *download free* (`omitted_in_edit`); tone *calm*.

| Component | Viewer wrote | Code | Why |
|---|---|---|---|
| `support` | “it showed the phone and laptop updating together” | `recovered` | Describes the visual; naming it is not required. |
| `call_to_action` | (ticked could not tell) | `not_recovered` | Expected for `omitted_in_edit`; still coded as usual. |
| `audience` | “busy professionals” | `contradicted` | Names a different audience. |
| `audience` | “people who take notes” | `partially_recovered` | Correct but vaguer than “students”. |

## 6. Calibration before freezing

1. Every coder codes the practice anchors independently.
2. Compare codes and discuss each disagreement. Change the rules above only
   where they were unclear, and record each change.
3. Repeat until coders agree on the practice anchors, then freeze this
   codebook with the pre-registration. Practice codes are never pooled with
   study codes.

Disagreement on study items is kept as raw data. It is resolved only through
separate adjudication records, never by editing a coder's code.
