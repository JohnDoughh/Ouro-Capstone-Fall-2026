# Public synthetic audio pair (clean + 1-second dropout)

Two short WAV files for checking that the lab loads, verifies and **audibly plays** audio, and for practicing audio-dropout review. They are public-safe teaching material. They are **not Ouro media, AVC inputs, AVC findings, or human research evidence**, and they are not any team's own dropout example.

This is a disclosed practice pair, not a blinded evaluation item: the defect below is stated openly so anyone can check that their setup works. Do not use it to measure rater accuracy.

| File | SHA-256 | Bytes | Format | Duration |
|---|---|---|---|---|
| `clean.wav` | `a8ea9c518d49ca1f029a98bf777d4460c4f2c6a96b087ee732e4b3fe7d705aa7` | 336044 | PCM 16-bit, mono, 16 kHz | 10.500 s |
| `dropout.wav` | `9f4f1593b2b5c7f24495f9e1f12d55920cde80d8608916bbb5d70d72e8d10478` | 336044 | PCM 16-bit, mono, 16 kHz | 10.500 s |

The sound is a continuous synthetic triangle-wave tone that alternates between 400 Hz and 500 Hz every 0.5 s. Its peak is about -12 dBFS, so it is clearly audible at normal volume. There is no speech, music, person, product or brand.

`dropout.wav` is byte-identical to `clean.wav` except for exactly **1.000 s of digital silence at [4.000, 5.000) s** (samples 64000–79999). It has hard edges and no fade.

## Check the bytes

```sh
cd data/public_audio && sha256sum -c audio.sha256 && cd ../..
python3 -m ouro_eval_lab.cli verify --manifest data/public_audio/manifest.json
```

To rebuild the files from scratch and confirm they match the pinned digests (standard library only, integer arithmetic, same bytes on every platform):

```sh
python3 scripts/generate_public_audio_pair.py --out /tmp/public_audio_rebuild
```

## Load and play in the lab

From the repository root:

```sh
python3 -m ouro_eval_lab.cli ingest --db data/audio-demo.db --manifest data/public_audio/manifest.json
python3 -m ouro_eval_lab.cli serve --db data/audio-demo.db --port 8080
```

Open `http://127.0.0.1:8080`, enter a fictional rater ID, and press play on the audio player. The lab re-checks each file's SHA-256 before serving it. It also answers byte-range requests, which Safari and iOS need before they will play media. Use a new `--db` file for this pair so it does not mix with the video demo.

## Limits

These files can test loading, hash verification, playback, and hearing and localizing one gross dropout. They cannot test natural speech, captions, voice identity, lip sync, audio-video synchronization, real advertising, or AVC accuracy.

The fictional video pair in `data/public_playable/` has only a very quiet intermittent tone (peak about -33 dBFS, 0.25 s every 2 s). Use this pair for audio.
