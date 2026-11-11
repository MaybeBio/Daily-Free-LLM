import unittest

from shovel.gateway.router import Router


def registry():
    return {
        "providers": [
            {
                "id": "alpha",
                "name": "Alpha",
                "base_url": "https://alpha/v1",
                "env": "ALPHA_KEY",
                "keyless": True,
                "gateway": True,
                "categories": ["api"],
                "models": [
                    {"id": "qwen3", "context": 100000, "tools": True},
                    {"id": "glm", "context": 50000},
                ],
            },
            {
                "id": "beta",
                "name": "Beta",
                "base_url": "https://beta/v1",
                "env": "BETA_KEY",
                "gateway": True,
                "categories": ["api"],
                "models": [{"id": "qwen3", "context": 200000}],
            },
            {
                "id": "chatui",
                "name": "Chat UI",
                "gateway": False,
                "categories": ["chat"],
                "models": [],
            },
        ]
    }


class CandidateTest(unittest.TestCase):
    def make(self, status=None, aliases=None, config=None):
        return Router(
            registry(),
            aliases or {},
            config or {"priority": ["alpha", "beta"], "max_candidates": 6},
            status,
        )

    def test_auto_picks_best_model_per_provider(self):
        router = self.make()
        ids = [(c["provider"], c["model"]) for c in router.candidates("auto")]
        self.assertIn(("alpha", "qwen3"), ids)
        self.assertIn(("beta", "qwen3"), ids)
        self.assertNotIn(("chatui", None), ids)

    def test_provider_model_exact(self):
        router = self.make()
        candidates = router.candidates("beta/qwen3")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["provider"], "beta")

    def test_alias_maps_to_multiple_providers(self):
        router = self.make(
            aliases={"aliases": {"qwen": [
                {"provider": "alpha", "model": "qwen3"},
                {"provider": "beta", "model": "qwen3"},
            ]}}
        )
        self.assertEqual(
            {c["provider"] for c in router.candidates("qwen")}, {"alpha", "beta"}
        )

    def test_manual_alias_overrides_generated(self):
        router = self.make(
            aliases={
                "aliases": {"qwen": [{"provider": "alpha", "model": "qwen3"}]},
                "manual": {"qwen": [{"provider": "beta", "model": "qwen3"}]},
            }
        )
        self.assertEqual([c["provider"] for c in router.candidates("qwen")], ["beta"])

    def test_bare_model_id_searches_all_providers(self):
        router = self.make()
        ids = {c["provider"] for c in router.candidates("qwen3")}
        self.assertEqual(ids, {"alpha", "beta"})

    def test_ok_status_sorts_first(self):
        router = self.make(
            status={"providers": {"beta": {"status": "ok", "models": {}}}}
        )
        self.assertEqual(router.candidates("qwen3")[0]["provider"], "beta")

    def test_unhealthy_provider_is_excluded(self):
        router = self.make(
            status={"providers": {"alpha": {"status": "auth_error", "models": {}}}}
        )
        self.assertEqual(
            [c["provider"] for c in router.candidates("auto")], ["beta"]
        )

    def test_unhealthy_model_is_excluded(self):
        router = self.make(
            status={"providers": {
                "alpha": {"status": "ok", "models": {"qwen3": {"status": "not_found"}}}
            }}
        )
        ids = [(c["provider"], c["model"]) for c in router.candidates("auto")]
        self.assertNotIn(("alpha", "qwen3"), ids)
        self.assertIn(("alpha", "glm"), ids)

    def test_cooldown_failover_then_recovery(self):
        router = self.make(config={"priority": ["alpha", "beta"], "max_candidates": 6,
                                   "cooldown_seconds": 0.05})
        router.mark("beta", "rate_limited")
        self.assertEqual(
            [c["provider"] for c in router.candidates("qwen3")], ["alpha"]
        )
        router.mark("beta", "ok")
        self.assertEqual(
            {c["provider"] for c in router.candidates("qwen3")}, {"alpha", "beta"}
        )

    def test_max_candidates(self):
        router = self.make(config={"priority": [], "max_candidates": 1})
        self.assertEqual(len(router.candidates("auto")), 1)

    def test_budget_blocks_candidate(self):
        class Deny:
            def allow(self, provider, limits):
                return provider != "alpha"

        router = self.make()
        router.budgets = Deny()
        self.assertEqual(
            [c["provider"] for c in router.candidates("auto")], ["beta"]
        )

    def test_unknown_request_returns_empty(self):
        router = self.make()
        self.assertEqual(router.candidates("no-such-model"), [])


if __name__ == "__main__":
    unittest.main()
