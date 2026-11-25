# Team C limitations statement: what the intent fidelity slice does not do

Status date: 2026-11-13 (end of course Sprint 5). Team C wrote this before
anyone else could find these gaps. Each item says what is missing, why it
matters, and what would close it. "Built" elsewhere in this repository means
built and tested on synthetic data; nothing below has been shown with real
viewers.

## 1. It has produced no research findings

- **No real viewers have taken part.** FIU has not recorded a human-subjects
  determination, and Team C has not named its human-subjects owner. Every
  response so far is a team dry run or simulated. *Closes when:* FIU records
  the determination and the pre-registration is frozen.
- **Every number we can show is synthetic.** The pilot's alpha of 0.84, its
  8 surviving and 14 not-surviving cells, and its 22% comprehension disruption come from
  simulated viewers and coders that follow probabilities we invented. They
  show the pipeline computes correctly. They say nothing about people, clips,
  Ouro or AVC. Every report and HTML view carries that label, and so must
  any slide that shows them.
- **The study set is four fictional clips.** The pre-registration targets
  90–150. Even at the minimum of 3 viewers per clip, one clip's recovery rate
  is very uncertain: 1 of 5 viewers gives a 95% interval of 4%–62%.
- **The real sealed intent records have never been revealed.** `reveal` has
  been tested on stand-in records and the pilot's own fictional records only.
  The value types of five metadata keys were inferred from their names; the
  custodian has been asked to run `scripts/verify_intent_reveal.py` on the
  sealed records.

## 2. It cannot yet answer half of its research question

The question has two halves: can viewers recover the intended meaning, and
can the evaluator tell when it survived?

- **No evaluator comparison.** No intent evaluator outputs exist. The output
  format is still a proposal to the integration council (v2, with Team B's
  feedback; Team A has not replied). So false "survived" and false "not
  survived" rates, Brier score, calibration error and risk-versus-coverage are
  **not computed for intent**. The report says "not available" rather than
  showing placeholder numbers.
- **No adjudication.** When coders disagree, the cell is reported as
  `pending_adjudication` and gets no survival decision. In the pilot that is 13
  of the 36 primary cells. The adjudication record shape was sent to Teams A and B
  on 2026-11-04 and has no reply yet.

## 3. Parts of the slice are not measured

- **Offer and required beats.** The sponsor's sealed records have no `offer`
  field and no list of required beats, so neither is measured. Thesis, hook,
  proof and CTA are reported only as labels mapped onto the record's fields.
  That mapping is a proposal that the sponsor has not confirmed.
- **Persuasion, credibility and trust** are excluded unless FIU approves them.
  We measure whether meaning was recovered, not whether the ad was
  convincing.
- **Tone** is collected but exploratory; it never enters the primary result.

## 4. The coding instrument is not final

- **The codebook is a draft (v0.1).** It has not been calibrated by the team
  or frozen with the pre-registration. Any code imported now records version
  `0.1-draft`.
- **The anchors are practice anchors only.** The 11 committed anchors are the
  codebook's own invented examples. They exist for the calibration round. The
  codebook gives the delivery code for only some of them; for the rest we
  assumed `explicit_text`, and the team should confirm that. The study
  drift-anchor set waits for the frozen codebook.
- **Coders work in a CSV sheet**, not a web interface. A spreadsheet program
  can reformat cells; the import checks every row and refuses bad ones, but a
  coder can still mis-type a valid code.

## 5. Operational limits

- **Single machine, no login.** The server listens on `127.0.0.1` and trusts
  the pseudonymous viewer ID in the URL. Anyone using that computer can answer
  as any ID. It must not be put on a network or the internet as it is.
- **Exposure control is partial.** The play limit is enforced by the server
  and survives a reload. But it cannot stop a viewer from recording the
  screen or finding the clips on disk. The `data/public_intent` README, which
  holds the answers' commitments, sits next to the clips, so sessions must be
  run from the browser only. No exposure log is built.
- **Personal-data screening is narrow.** Free-text answers and notes are
  checked for email addresses, phone numbers and URLs only. Names, addresses
  or other identifying details would not be caught; viewer instructions are
  the only control.
- **Some actions are permanent by design.** The freeze cannot be reopened and
  imported codes cannot be changed. Mistakes can only be handled by
  adjudication or by starting a new database, so operators must follow
  `docs/TEAM_C_OPERATOR_GUIDE.md`.
- **Two harmless oddities:** opening the viewer page after the freeze still
  creates (empty) assignment rows, and re-running `export-intent` after the
  freeze records a duplicate freeze row with the same hash. Neither changes
  any response or result.

## 6. Reproducibility limits

- **Hosted CI does not run.** A billing lock on the repository owner's account
  stops GitHub Actions. All checks (200 Python tests, 52 browser tests, the
  boundary scan, manifest checks, the pilot hash and the anchor binding) are
  run locally. On Windows there is no `make`, so the steps are run one by one.
- **The pilot hash has been reproduced only on Windows** (Python 3.12 and
  3.14) and by the repository owner (Python 3.13). It has not been checked on
  macOS or Linux by Team C.
- **No independent rerun yet.** The intent section of
  `docs/INDEPENDENT_RERUN.md` has not been run by someone who did not build
  it.
- **None of Team C's code is merged into `main`.** PR #23 (Stage 1) has had
  all requested changes made since 2026-10-19 and is still blocked on the
  owner's re-review. PR #39 and this sprint's work are stacked on it.

## What we are confident of

Within those limits, these are tested and repeatable:

- viewers never receive the intended answers or any clip identifier;
- responses, plays, the freeze, the reveal and codes are append-only, and
  each code is bound by SHA-256 to the exact response, record and clip;
- the reveal refuses records that do not match their commitments, and refuses
  to run before the freeze;
- a coder never receives a clip they viewed;
- the same inputs always give a byte-identical report, and the pilot matches
  its recorded hash.
