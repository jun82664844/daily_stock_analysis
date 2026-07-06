import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformBackupRestoreDrillV51TestCase(unittest.TestCase):
    def _create_source_db(self, path: Path) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE platform_users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
            conn.execute("CREATE TABLE analysis_history (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
            conn.execute("INSERT INTO platform_users(email) VALUES ('backup-v51@example.com')")
            conn.execute("INSERT INTO analysis_history(code) VALUES ('AAPL')")
            conn.commit()

    def test_sqlite_backup_restore_dry_run_creates_verified_copies_without_mutating_source(self) -> None:
        from src.services.platform_backup import run_sqlite_backup_restore_dry_run

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            source = root / "source.sqlite"
            output_dir = root / "backups"
            self._create_source_db(source)
            source_before = source.read_bytes()

            result = run_sqlite_backup_restore_dry_run(source, output_dir=output_dir, label="v51-test")

            self.assertTrue(result["success"])
            self.assertFalse(result["destructive"])
            self.assertFalse(result["ai_used"])
            self.assertEqual(result["source"]["integrity_check"], "ok")
            self.assertEqual(result["backup"]["integrity_check"], "ok")
            self.assertEqual(result["restored"]["integrity_check"], "ok")
            self.assertEqual(result["row_counts_match"], True)
            self.assertEqual(result["source"]["table_counts"], result["restored"]["table_counts"])
            self.assertTrue(Path(result["backup"]["path"]).exists())
            self.assertTrue(Path(result["restored"]["path"]).exists())
            self.assertEqual(source.read_bytes(), source_before)

    def test_operational_script_and_v51_verifier_are_visible(self) -> None:
        runner = REPO_ROOT / "scripts" / "run_platform_backup_restore_dry_run.py"
        verifier = REPO_ROOT / "scripts" / "verify_platform_backup_restore_drill_v51.py"

        self.assertTrue(runner.exists(), "backup restore dry-run runner is missing")
        self.assertTrue(verifier.exists(), "V51 verifier is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_backup_restore_drill_v51"))

        from scripts.verify_platform_backup_restore_drill_v51 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK")


if __name__ == "__main__":
    unittest.main()
