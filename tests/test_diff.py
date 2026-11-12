import tempfile
import unittest
from pathlib import Path

from shovel.diff import update_snapshot


class SnapshotGuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_baseline_then_diff(self):
        first = update_snapshot("src", "\n".join(f"m{i}" for i in range(30)), self.dir)
        self.assertTrue(first["baseline"])
        second = update_snapshot(
            "src", "\n".join(f"m{i}" for i in range(30)) + "\nm30", self.dir
        )
        self.assertFalse(second["baseline"])
        self.assertEqual(second["added"], ["m30"])
        self.assertEqual(second["removed_count"], 0)

    def test_sudden_drop_is_not_written(self):
        original = "\n".join(f"m{i}" for i in range(30))
        update_snapshot("src", original, self.dir)
        result = update_snapshot("src", "m0\nm1\nm2", self.dir)
        self.assertTrue(result["anomaly"])
        self.assertEqual(result["previous_items"], 30)
        self.assertEqual((self.dir / "src.txt").read_text(encoding="utf-8"), original)

    def test_daily_archive_is_written(self):
        archive = self.dir / "daily" / "2026-11-13"
        update_snapshot("src", "a\nb", self.dir, archive_dir=archive)
        self.assertEqual((archive / "src.txt").read_text(encoding="utf-8"), "a\nb")

    def test_anomaly_does_not_touch_archive(self):
        archive = self.dir / "daily" / "2026-11-13"
        original = "\n".join(f"m{i}" for i in range(30))
        update_snapshot("src", original, self.dir, archive_dir=archive)
        update_snapshot("src", "m0", self.dir, archive_dir=archive)
        self.assertEqual((archive / "src.txt").read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
