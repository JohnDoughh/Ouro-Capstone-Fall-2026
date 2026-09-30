# Fictional visual continuity pair (clean + seeded defect)

Two 12-second wordless videos for a first blinded visual test. They are public-safe teaching material. They are **not Ouro media, AVC inputs, AVC findings, or human research evidence**. No person, real product, brand, text or speech appears, and there is no soundtrack.

Both clips tell the same four-shot story about a fictional water bottle: a wide desk shot, a close-up, the bottle moving toward a bag, and an end card. One clip is clean. The other is the same clip with **one seeded visual defect**, which a rater finds only by looking closely at the product across the shots. The two files are named neutrally (`clip_a.mp4`, `clip_b.mp4`), and the seed, not the file order, decides which one is defective.

This README does not say which clip is defective or what the defect is, so it is safe to leave in the repository. Operators should still keep these files away from raters until their judgments are exported:

- `seeded_truth.json` holds the defective clip, a description of the defect, its frame and time window, and the provenance of the source frames.
- `manifest.json` holds `defect_present` for each clip.
- `scripts/generate_visual_continuity_pair.py` draws the defect.

## Run a blinded viewing

From the repository root, using a new database for this pair:

```sh
python3 -m ouro_eval_lab.cli verify --manifest data/public_visual_pair/manifest.json
python3 -m ouro_eval_lab.cli ingest --db data/visual-pair-demo.db --manifest data/public_visual_pair/manifest.json
python3 -m ouro_eval_lab.cli serve --db data/visual-pair-demo.db --port 8080
```

Open `http://127.0.0.1:8080` and enter a fictional rater ID. The lab assigns the clips in random order, with a blinded repeat. The rater watches each one and records PASS, HOLD or UNSURE, confidence, severity and, for a HOLD, where the defect is (for example `00:04-00:05`). Tell raters only that some clips may contain a visual problem with the product and that they may pause and rewatch.

Then freeze the judgments before anyone opens the truth file:

```sh
python3 -m ouro_eval_lab.cli export --db data/visual-pair-demo.db --out data/exports/visual-pair-annotations.json
shasum -a 256 data/exports/visual-pair-annotations.json
```

Score each exported judgment against `seeded_truth.json`: the verdict against `defect_present`, and any timestamp against the defect window. Keep the raw rows. Disagreement between raters is data, not an error to clean up.

## Reproduce

Frames are drawn with the Python standard library only (integer geometry, no fonts), so the raw source frames are identical on every platform. `make test` re-renders them and checks them against the digests in `seeded_truth.json`. It also checks that the two clips differ only inside the seeded window and only on the product.

To rebuild the MP4s you also need FFmpeg with libx264:

```sh
python3 scripts/generate_visual_continuity_pair.py --out /tmp/visual-pair-rebuild
```

The committed MP4s were encoded with FFmpeg 9.0.2 (libx264, CRF 18, one thread, bitexact flags). Other encoder versions may write different MP4 bytes from the same frames, so always verify the committed media against the committed manifest. The seed is `20260930`.

## Limits

- Two clips can pilot a blinded visual procedure and check that a rater can find and time one product-continuity defect. They are not enough to estimate rater accuracy or agreement, and they do not meet the project-wide 90–150 artifact target.
- A rater who has seen one clip may compare the other against it. Record assignment order, which the lab stores, so that effect can be seen.
- Flat shapes are much simpler than real footage. The pair cannot test faces, hands, presenter identity, text or claim accuracy, rendering artifacts in natural images, audio, or AVC accuracy.
- The older `data/public_playable/` pair names its defect in its README and artifact IDs, so it is a disclosed practice pair, not a blinded test.
