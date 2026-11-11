import tempfile
import unittest
from pathlib import Path

from shovel.gateway.budgets import Budgets


class BudgetsTest(unittest.TestCase):
    def setUp(self):
        self.db = Budgets(Path(tempfile.mkdtemp()) / "test.db")

    def test_rpm_allows_up_to_limit(self):
        limits = {"rpm": 5}
        for _ in range(5):
            self.assertTrue(self.db.allow("p", limits))
            self.db.record("p", "m", "ok")
        self.assertFalse(self.db.allow("p", limits))

    def test_rpd_counts_only_today(self):
        limits = {"rpd": 1000}
        self.assertTrue(self.db.allow("p", limits))

    def test_token_limit(self):
        limits = {"tpm": 100}
        self.assertTrue(self.db.allow("p", limits, estimate_tokens=50))
        self.db.record("p", "m", "ok", 30, 20)
        self.assertFalse(self.db.allow("p", limits, estimate_tokens=60))
        self.assertTrue(self.db.allow("p", limits, estimate_tokens=40))

    def test_no_limits_always_allowed(self):
        self.assertTrue(self.db.allow("p", {}))

    def test_stats(self):
        self.db.record("p", "m", "ok", 10, 20)
        self.db.record("q", "m", "ok", 5, 5)
        stats = self.db.stats()
        self.assertEqual(stats["p"], {"requests": 1, "tokens": 30})
        self.assertEqual(stats["q"], {"requests": 1, "tokens": 10})

    def test_provider_isolation(self):
        self.db.record("p", "m", "ok")
        self.db.record("p", "m", "ok")
        self.assertFalse(self.db.allow("p", {"rpm": 2}))
        self.assertTrue(self.db.allow("q", {"rpm": 2}))


if __name__ == "__main__":
    unittest.main()
