# Fictional playable visual pair

These independently created 8-second videos are public-safe teaching material. They are **not Ouro media, AVC inputs, AVC findings, or human research evidence**. The soundtrack is a synthesized tone with no speech. No person, customer product, client, or brand appears.

The clean and defective clips have the same simple visual story: a messy desk, a fictional Orbit Tray, a product use beat, and an invitation to explore the tray. In `label_defect.mp4` only, the visible tray name changes from **ORBIT TRAY** to **ORBIT TRY** during `[2.500, 3.500)` seconds. `fictional_reference.png` shows the fictional approved name; its digest is in `reference.sha256`. That reference is for a later comparison stage; keep it and this README away from a viewer during an initial blinded viewing. The defect family and truth also appear in `manifest.json`, which must remain separate from blinded viewers.

Use these clips to check that the lab can load and play video, verify bytes, record a human decision and localize a visible label error. They cannot test natural speech, caption synchronization, voice identity, lip sync, actual advertising effectiveness, or AVC accuracy. Team B's independent synthetic audio example and Team C's separate intent protocol serve different questions.

For a fresh local demonstration, from the repository root:

```sh
python3 -m ouro_eval_lab.cli verify --manifest data/public_playable/manifest.json
python3 -m ouro_eval_lab.cli ingest --db data/playable-demo.db --manifest data/public_playable/manifest.json
python3 -m ouro_eval_lab.cli serve --db data/playable-demo.db --port 8080
```

Open the local browser lab, use a fictional rater ID, and play the assigned clip. This is a synthetic development demo only. Research with real participants still requires the separately documented FIU review gates. No evaluator output is included for these clips; never treat the fixture's seeded label as an AVC verdict or probability.

To regenerate, install Pillow and FFmpeg, then run `python3 scripts/generate_playable_visual_demo.py --out /tmp/orbit-reproduction`. The committed files were made with Python 3.12, Pillow 12.3.0, FFmpeg 6.1.1 and DejaVu Sans. Re-encoded MP4 bytes may differ on other encoder versions, so verify the committed media against the committed manifest before using it. The seed is `20260923`; the PNG and MP4 hashes are pinned in the manifest/reference digest.
