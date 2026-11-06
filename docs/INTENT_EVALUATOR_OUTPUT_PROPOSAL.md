# Proposal: what an evaluator reports about intent

**From Team C, 2026-11-04. Draft for the council. Not agreed.**

## The problem

Team C measures whether viewers recover what each clip was meant to say: per
clip and intent field, did the meaning **survive**? To compare an evaluator
with people, we need the evaluator's answer to the same question, in a fixed
format, frozen before anyone looks at the human results.

The existing evaluator format (`1.0.0`) answers a different question: one
PASS/HOLD per clip for production defects. It has no intent field and no way
to abstain. We don't want to change it. This would be a separate, new format.

## The idea

One record per clip and intent field (for example *clip 3, call to action*).
Each record says:

- **which clip** (by its SHA-256) and **which field** (one of the seven intent
  fields);
- **which evaluator**, by anonymous alias only (`eval-...`), never a model or
  product name;
- **the answer**: `survived`, `not_survived`, or `abstain` (too ambiguous to
  judge);
- **how likely it thinks survival is**, from 0 to 1, even when it abstains;
- **short evidence codes** from a fixed list, never free text or reasoning;
- **when** it ran, and the format version.

It must **not** contain the intended text, prompts, model names, thresholds,
reasoning or anything from Ouro systems. A file of these records is hashed and
the hash recorded **before** the reveal, the same way viewer responses are
frozen.

## How we would score it

Against the human reference from the intent report (synthetic data only until
the sponsor provides frozen outputs):

- **false survived:** the evaluator says survived; people didn't recover it;
- **false not-survived:** the reverse;
- **calibration:** Brier score and ECE on the 0–1 survival likelihood;
- **abstention:** how often it abstains, and whether it abstains on the cells
  people found ambiguous (the pre-registered reference class), shown as risk
  versus coverage.

## Questions for the council

1. Is per clip and field the right unit, or should the evaluator also judge
   individual viewer responses?
2. Is a separate format, leaving `1.0.0` unchanged, acceptable?
3. Should the evaluator answer all seven fields, or only the six primary ones
   (tone is exploratory)?
4. What should the fixed list of evidence codes be? Team C suggests starting
   with: `stated_in_text`, `stated_in_speech`, `shown_visually`, `implied`,
   `absent`, `conflicting_signals`.
5. Who freezes and holds the evaluator outputs before reveal? It should not be
   a coder.

Until this is agreed, Team C's report marks the evaluator comparison as not
available, and any demo uses clearly labelled synthetic outputs only.
