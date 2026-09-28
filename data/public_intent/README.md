# Fictional intent-bearing clips (Team C material)

Four 12-second fictional ad-style clips for piloting an **intent-survival** protocol: can a viewer recover what the creator meant the clip to communicate? They are public-safe teaching material. They are **not Ouro media, AVC inputs, AVC findings, or human research evidence**. Each clip uses on-screen text, simple shapes and an audible synthetic tone. There is no speech, person, real product or brand.

Keep this README and `manifest.json` away from viewers during blinded viewing. Viewers should see only the clip in the lab.

## What is public and what is withheld

- **Public:** the clips, `manifest.json`, and `intent_commitments.sha256`, which holds one SHA-256 per frozen intent record.
- **Withheld by the sponsor until reveal:** the four frozen intent records (`clip01.intent.json` … `clip04.intent.json`). They were written and hashed before this repository saw the clips. Each record contains a random salt, so the commitment cannot be guessed from its contents.
- The manifest's `defect_present: false` only means no production defect was seeded. It says nothing about whether the intent comes through. That is the question Team C measures.

Each record uses the same bounded fields: `audience`, `problem`, `product`, `key_benefit`, `support`, `call_to_action` and `tone`. Each field also has a sponsor-coded `delivery` value, one of `explicit_text`, `implied`, `visual_only`, `partially_delivered`, `omitted_in_edit` or `not_intended`. The clips differ on purpose in how much of the intent they deliver. Which clip does what stays sealed until reveal.

## Procedure

1. **Verify and load**, using a new database for this set:
   ```sh
   python3 -m ouro_eval_lab.cli verify --manifest data/public_intent/manifest.json
   python3 -m ouro_eval_lab.cli ingest --db data/intent-demo.db --manifest data/public_intent/manifest.json
   python3 -m ouro_eval_lab.cli serve --db data/intent-demo.db --port 8080
   ```
2. **Blinded response.** The viewer watches a clip and records a free-recall answer in the note field *before* anything is revealed. Team C writes the actual prompts. A minimal version: who is it for, what problem, what product, main benefit, what am I asked to do. The PASS/HOLD/UNSURE verdict and confidence are production-quality fields, not intent scores.
3. **Freeze responses:** `python3 -m ouro_eval_lab.cli export --db data/intent-demo.db --out data/exports/intent-responses.json`, and record that file's SHA-256.
4. **Reveal.** The sponsor releases the four records. Anyone checks them against the commitments:
   ```sh
   python3 scripts/verify_intent_reveal.py --records /path/to/revealed/records
   ```
   Any mismatch invalidates the reveal.
5. **Separate coding.** Coders who did not watch as viewers compare each frozen response to the record, field by field, with Team C's codebook. Agreement between coders is reported. Nothing here is an AVC score or a probability.

## Limits

- Four clips are enough to pilot the protocol, not to estimate anything. They do not meet the project-wide 90–150 artifact target.
- On-screen text makes intent easier to recover than in real ads. The clips cannot test speech, voice, captions, lip sync, persuasion strength, or real advertising effect.
- The existing public fixtures (`data/public_playable`, `data/public_audio`, `data/fixtures`) carry no intent records and cannot support this study.

To regenerate the video, install FFmpeg (with drawtext) and DejaVu Sans, then run `python3 scripts/generate_public_intent_clips.py --out /tmp/intent-rebuild`. The committed files were made with FFmpeg 6.1.1. Other encoder versions may produce different bytes, so always verify against the committed manifest.
