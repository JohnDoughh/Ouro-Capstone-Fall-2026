import sqlite3
import tempfile
import unittest
from pathlib import Path

from ouro_eval_lab.store import connect


class DatabaseLifetimeTests(unittest.TestCase):
    def test_commit_closes_even_when_connection_and_cursor_remain_referenced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lab.db"
            with connect(path) as db:
                db.execute("CREATE TABLE observations (value TEXT)")
                db.execute("INSERT INTO observations VALUES ('original')")
                cursor = db.execute("SELECT * FROM observations")
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute("SELECT 1")
            with self.assertRaises(sqlite3.ProgrammingError):
                cursor.fetchone()
            with connect(path) as reopened:
                self.assertEqual(reopened.execute("SELECT value FROM observations").fetchone()[0], "original")
            path.unlink()  # On Windows this also requires the file handle to be closed.

    def test_exception_rolls_back_and_closes_without_swallowing_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lab.db"
            with connect(path) as db:
                db.execute("CREATE TABLE observations (value TEXT)")
            with self.assertRaisesRegex(ValueError, "stop"):
                with connect(path) as failed:
                    failed.execute("INSERT INTO observations VALUES ('not saved')")
                    raise ValueError("stop")
            with self.assertRaises(sqlite3.ProgrammingError):
                failed.execute("SELECT 1")
            with connect(path) as reopened:
                self.assertEqual(reopened.execute("SELECT count(*) FROM observations").fetchone()[0], 0)
            path.unlink()

    def test_direct_connection_remains_usable_until_explicitly_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / "manual.db")
            try:
                self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                db.execute("CREATE TABLE observations (value TEXT)")
                db.commit()
                self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 0)
            finally:
                db.close()
