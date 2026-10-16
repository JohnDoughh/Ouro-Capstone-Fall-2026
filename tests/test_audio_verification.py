"""Synthetic transport/storage tests, never presented as a human listening session."""
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from ouro_eval_lab.api import LabHandler
from ouro_eval_lab.audio_verification import MANIFEST, compare_export, verify_audio_session
from ouro_eval_lab.runner import verify_manifest
from ouro_eval_lab.store import ingest


class AudioVerificationTests(unittest.TestCase):
    def test_http_save_reopen_export_all_three_verdicts_and_detect_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / 'audio.db'
            manifest = verify_manifest(MANIFEST)['manifest']
            ingest(db_path, manifest, MANIFEST.parent)
            defect_by_hash = {a['sha256']: a['defect_present'] for a in manifest['artifacts']}
            handler = type('AudioTestHandler', (LabHandler,), {
                'db_path': db_path, 'log_message': lambda *args: None,
            })
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            expected = []
            seen = set()
            base = f'http://127.0.0.1:{server.server_address[1]}'
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + '/api/saved-annotations?rater=automated-audio')
                self.assertEqual(denied.exception.code, 403)
                # The two-file queue contains one hidden repeat; use it for UNSURE coverage.
                for _ in range(3):
                    with self.assertRaises(urllib.error.HTTPError) as incomplete:
                        urllib.request.urlopen(base + '/api/saved-annotations?rater=automated-audio')
                    self.assertEqual(incomplete.exception.code, 403)
                    with urllib.request.urlopen(base + '/api/next?rater=automated-audio') as response:
                        assignment = json.load(response)['assignment']
                    with closing(sqlite3.connect(db_path)) as db:
                        digest = db.execute('SELECT artifact_sha256 FROM assignments WHERE assignment_id=?',
                                            (assignment['assignment_id'],)).fetchone()[0]
                    verdict = 'UNSURE' if digest in seen else 'HOLD' if defect_by_hash[digest] else 'PASS'
                    seen.add(digest)
                    payload = {
                        'verdict': verdict, 'confidence': {'PASS': 5, 'HOLD': 4, 'UNSURE': 1}[verdict],
                        'severity': {'PASS': 0, 'HOLD': 3, 'UNSURE': 1}[verdict],
                        'reason_codes': [] if verdict == 'PASS' else ['audio_integrity'],
                        'defect_timestamps': '' if verdict == 'PASS' else ' 00:04-00:05 ',
                        'note': '' if verdict == 'PASS' else f'Synthetic automated {verdict}: "tone", evidence\nsecond line — preserved.',
                    }
                    expected.append({'review_label': assignment['review_label'], **payload})
                    request = urllib.request.Request(
                        base + f"/api/annotations/{assignment['assignment_id']}?rater=automated-audio",
                        data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status, 201)
                with urllib.request.urlopen(base + '/api/saved-annotations?rater=automated-audio') as response:
                    self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    reopened = json.load(response)['annotations']
                self.assertEqual(len(reopened), 3)
                for actual, submitted in zip(reopened, expected):
                    for field, value in submitted.items():
                        self.assertEqual(actual[field], value.strip() if field == 'defect_timestamps' else value)
                    self.assertIn(actual['artifact_sha256'], defect_by_hash)
                    self.assertIn(actual['artifact_id'], {'syn-tone-a', 'syn-tone-b'})
                    for hidden in ('defect_family', 'defect_present', 'repeat_group', 'fixture_root'):
                        self.assertNotIn(hidden, actual)
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + '/api/saved-annotations?rater=another-rater')
                self.assertEqual(denied.exception.code, 403)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
            expected_path = root / 'expected.json'
            expected_path.write_text(json.dumps(expected))
            before = db_path.read_bytes()
            pending = verify_audio_session(db_path, root / 'pending', 'automated-audio')
            self.assertEqual(pending['status'], 'pending_manual_review')
            report = verify_audio_session(db_path, root / 'evidence', 'automated-audio', expected_path)
            self.assertEqual(report['status'], 'passed')
            self.assertEqual(db_path.read_bytes(), before, 'Verification must not modify the database')
            self.assertEqual({r['verdict'] for r in report['saved_records']}, {'PASS', 'HOLD', 'UNSURE'})
            for fmt in ('json', 'csv'):
                self.assertTrue(all(c['ok'] for c in report['export_checks'][fmt]))
                content = (root / 'evidence' / f'annotations.{fmt}').read_text()
                corrupted = content.replace('second line', 'changed evidence')
                self.assertTrue(any(not c['ok'] for c in compare_export(report['saved_records'], corrupted, fmt)))
            # Wrong input evidence must not be accepted just because export agrees with storage.
            expected[0]['note'] = 'Different from what was submitted'
            expected_path.write_text(json.dumps(expected))
            mismatch = verify_audio_session(db_path, root / 'mismatch', 'automated-audio', expected_path)
            self.assertEqual(mismatch['status'], 'failed')
            self.assertTrue(any(c['field'] == 'note' and not c['ok'] for c in mismatch['submitted_input_checks']))
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("UPDATE annotations SET confidence=0.5, confidence_scale='legacy-0-1'")
                db.commit()
            invalid = verify_audio_session(db_path, root / 'invalid', 'automated-audio')
            self.assertEqual(invalid['status'], 'failed')

    def test_empty_session_is_pending_and_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / 'missing.db'
            with self.assertRaisesRegex(ValueError, 'existing audio test database'):
                verify_audio_session(missing, root / 'out', 'rater')
            self.assertFalse(missing.exists())
            manifest = verify_manifest(MANIFEST)['manifest']
            ingest(missing, manifest, MANIFEST.parent)
            report = verify_audio_session(missing, root / 'out', 'rater')
            self.assertEqual(report['status'], 'pending_manual_review')
            self.assertEqual(report['saved_records'], [])
            with closing(sqlite3.connect(missing)) as db:
                db.execute("UPDATE artifacts SET relative_path='another.wav'")
                db.commit()
            with self.assertRaisesRegex(ValueError, 'metadata mismatch'):
                verify_audio_session(missing, root / 'out', 'rater')


if __name__ == '__main__':
    unittest.main()
