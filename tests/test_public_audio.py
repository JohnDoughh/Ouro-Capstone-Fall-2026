import hashlib
import importlib.util
import json
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler, parse_byte_range
from ouro_eval_lab.runner import verify_manifest
from ouro_eval_lab.store import ingest

ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "data" / "public_audio"
MANIFEST = AUDIO / "manifest.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_public_audio_pair", ROOT / "scripts" / "generate_public_audio_pair.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pcm(path: Path) -> tuple[int, list[int]]:
    with wave.open(str(path), "rb") as stream:
        assert stream.getnchannels() == 1 and stream.getsampwidth() == 2
        rate = stream.getframerate()
        raw = stream.readframes(stream.getnframes())
    return rate, list(struct.unpack(f"<{len(raw) // 2}h", raw))


class PublicAudioPairTests(unittest.TestCase):
    def test_generator_reproduces_pinned_bytes(self):
        generator = _load_generator()
        manifest = json.loads(MANIFEST.read_text())
        pinned = {item["relative_path"]: item["sha256"] for item in manifest["artifacts"]}
        with tempfile.TemporaryDirectory() as directory:
            for name, dropout in (("clean.wav", False), ("dropout.wav", True)):
                digest = generator.write(Path(directory) / name, dropout)
                self.assertEqual(digest, pinned[name], name)

    def test_manifest_verifies(self):
        self.assertEqual(verify_manifest(MANIFEST)["verified"], 2)

    def test_audible_everywhere_except_the_one_second_dropout(self):
        rate, clean = _pcm(AUDIO / "clean.wav")
        _, dropout = _pcm(AUDIO / "dropout.wav")
        self.assertEqual(rate, 16000)
        self.assertEqual(len(clean), 168000)  # 10.500 s
        self.assertEqual(len(dropout), 168000)
        start, end = 4 * rate, 5 * rate
        self.assertTrue(all(value == 0 for value in dropout[start:end]))
        self.assertEqual(dropout[:start], clean[:start])
        self.assertEqual(dropout[end:], clean[end:])
        # Every 100 ms window outside the dropout is loud (peak well above -30 dBFS).
        for offset in range(0, len(clean), rate // 10):
            window = clean[offset:offset + rate // 10]
            self.assertGreater(max(abs(v) for v in window), 1000, offset)
        self.assertGreaterEqual(max(abs(v) for v in clean), 7900)


class ByteRangeTests(unittest.TestCase):
    def test_parse(self):
        self.assertIsNone(parse_byte_range(None, 10))
        self.assertEqual(parse_byte_range("bytes=0-1", 10), (0, 1))
        self.assertEqual(parse_byte_range("bytes=0-", 10), (0, 9))
        self.assertEqual(parse_byte_range("bytes=5-99", 10), (5, 9))
        self.assertEqual(parse_byte_range("bytes=-3", 10), (7, 9))
        self.assertEqual(parse_byte_range("bytes=-30", 10), (0, 9))
        self.assertEqual(parse_byte_range("bytes=10-", 10), "unsatisfiable")
        self.assertEqual(parse_byte_range("bytes=-0", 10), "unsatisfiable")
        self.assertIsNone(parse_byte_range("bytes=0-1,4-5", 10))
        self.assertIsNone(parse_byte_range("items=0-1", 10))
        self.assertIsNone(parse_byte_range("bytes=4-2", 10))
        self.assertIsNone(parse_byte_range("bytes=x-2", 10))


class AudioServingTests(unittest.TestCase):
    def test_lab_serves_verified_audio_with_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "lab.db"
            verified = verify_manifest(MANIFEST)
            self.assertEqual(ingest(db_path, verified["manifest"], MANIFEST.parent), 2)
            handler = type("TestHandler", (LabHandler,), {"db_path": db_path, "log_message": lambda *a: None})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"
                pinned = {item["sha256"] for item in verified["manifest"]["artifacts"]}
                with urllib.request.urlopen(f"{base}/api/next?rater=audio-check") as response:
                    assignment = json.loads(response.read())["assignment"]
                self.assertEqual(assignment["mime_type"], "audio/wav")
                url = base + assignment["media_url"]
                with urllib.request.urlopen(url) as response:
                    body = response.read()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Content-Type"], "audio/wav")
                    self.assertEqual(response.headers["Accept-Ranges"], "bytes")
                self.assertIn(hashlib.sha256(body).hexdigest(), pinned)
                request = urllib.request.Request(url, headers={"Range": "bytes=0-1"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.headers["Content-Range"], f"bytes 0-1/{len(body)}")
                    self.assertEqual(response.read(), body[:2])
                request = urllib.request.Request(url, headers={"Range": f"bytes={len(body)}-"})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request)
                self.assertEqual(caught.exception.code, 416)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
