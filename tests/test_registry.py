import unittest

from shovel.registry import (
    merge_providers,
    normalize_provider,
    validate,
    normalize_limits,
)


class NormalizeProviderTest(unittest.TestCase):
    def test_infers_gateway_and_slug(self):
        provider = normalize_provider(
            {
                "id": "Zhipu BigModel",
                "base_url": "https://open.bigmodel.cn/api/paas/v4/",
                "env": "ZHIPU_KEY",
                "categories": ["api"],
            }
        )
        self.assertEqual(provider["id"], "zhipu-bigmodel")
        self.assertEqual(provider["base_url"], "https://open.bigmodel.cn/api/paas/v4")
        self.assertTrue(provider["gateway"])
        self.assertEqual(provider["api_style"], "openai")

    def test_no_base_url_is_not_gateway(self):
        provider = normalize_provider({"name": "Some Chat UI", "categories": ["chat"]})
        self.assertFalse(provider["gateway"])
        self.assertEqual(provider["id"], "some-chat-ui")
        self.assertEqual(provider["region"], "unknown")

    def test_access_and_nature_normalization(self):
        provider = normalize_provider(
            {
                "name": "X",
                "categories": ["API"],
                "region": "国内",
                "free_nature": "长期免费",
                "access": {"phone": "required", "foreign_card": "not_required"},
            }
        )
        self.assertEqual(provider["categories"], ["api"])
        self.assertEqual(provider["region"], "cn")
        self.assertEqual(provider["free_nature"], "permanent")
        self.assertEqual(provider["access"]["phone"], "required")
        self.assertEqual(provider["access"]["card"], "not_required")

    def test_free_text_access(self):
        provider = normalize_provider(
            {"name": "Y", "access": "手机号、实名，无需邮箱"}
        )
        self.assertEqual(provider["access"]["phone"], "required")
        self.assertEqual(provider["access"]["realname"], "required")
        self.assertEqual(provider["access"]["email"], "not_required")

    def test_limits(self):
        self.assertEqual(
            normalize_limits({"rpm": "5 RPM", "rpd": "1,000", "tpm": "未知"}),
            {"rpm": 5, "rpd": 1000, "tpm": None, "tpd": None},
        )


class MergeProvidersTest(unittest.TestCase):
    def test_same_id_merges_models_and_sources(self):
        merged = merge_providers(
            [
                {
                    "id": "alpha",
                    "name": "Alpha",
                    "categories": ["api"],
                    "models": [{"id": "m1", "context": 1000}],
                    "sources": ["https://a"],
                }
            ],
            [
                {
                    "id": "alpha",
                    "name": "Alpha",
                    "categories": ["cloud"],
                    "models": [{"id": "m1", "tools": True}, {"id": "m2"}],
                    "sources": ["https://b"],
                }
            ],
        )
        self.assertEqual(len(merged), 1)
        provider = merged[0]
        self.assertEqual(provider["categories"], ["api", "cloud"])
        self.assertEqual(provider["sources"], ["https://a", "https://b"])
        self.assertEqual({m["id"] for m in provider["models"]}, {"m1", "m2"})
        self.assertEqual(provider["models"][0]["context"], 1000)
        self.assertTrue(provider["models"][0]["tools"])

    def test_same_base_url_merges_different_ids(self):
        merged = merge_providers(
            [{"id": "one", "name": "One", "base_url": "https://x/v1"}],
            [{"id": "two", "name": "Two", "base_url": "https://x/v1"}],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "one")
        self.assertEqual(merged[0]["name"], "One")

    def test_same_name_merges_different_ids(self):
        merged = merge_providers(
            [{"id": "cf-token", "name": "Cloudflare Workers AI", "categories": ["api"]}],
            [{"id": "cloudflare-workers-ai", "name": "Cloudflare Workers AI", "categories": ["cloud"]}],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["categories"], ["api", "cloud"])

    def test_same_homepage_merges_catalog_entry(self):
        merged = merge_providers(
            [{
                "id": "aihorde",
                "name": "AI Horde",
                "homepage": "https://aihorde.net",
                "base_url": "https://oai.aihorde.net/v1",
                "keyless": True,
                "gateway": True,
            }],
            [{
                "id": "ai-horde-openai-compatible-front",
                "name": "AI Horde (OpenAI-compatible front)",
                "homepage": "https://aihorde.net/",
                "limits_text": "Queue-based",
            }],
        )
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "aihorde")
        self.assertEqual(merged[0]["limits_text"], "Queue-based")

    def test_verified_at_keeps_latest(self):
        merged = merge_providers(
            [{"id": "x", "name": "X", "verified_at": "2026-09-30"}],
            [{"id": "x", "name": "X", "verified_at": "2026-10-30"}],
        )
        self.assertEqual(merged[0]["verified_at"], "2026-10-30")

    def test_distinct_providers_are_kept(self):
        merged = merge_providers(
            [{"id": "a", "name": "Alpha"}],
            [{"id": "b", "name": "Beta"}],
        )
        self.assertEqual([p["id"] for p in merged], ["a", "b"])


class ValidateTest(unittest.TestCase):
    def test_duplicate_and_gateway_errors(self):
        errors = validate(
            [
                {"id": "a", "name": "A"},
                {"id": "a", "name": "A"},
                {"id": "b", "name": "B", "gateway": True},
                {"id": "c", "name": "C", "models": [{"id": ""}]},
            ]
        )
        self.assertIn("provider id 重复: a", errors)
        self.assertTrue(any("缺少 base_url" in e for e in errors))
        self.assertTrue(any("空模型 id" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
