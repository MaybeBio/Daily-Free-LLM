import unittest

from shovel.sources import _catalog_models, _catalog_provider, openrouter_free_models


class OpenRouterTest(unittest.TestCase):
    def test_only_zero_priced_models(self):
        payload = {
            "data": [
                {
                    "id": "free/model:free",
                    "pricing": {"prompt": "0", "completion": "0"},
                    "context_length": 32768,
                    "supported_parameters": ["tools"],
                    "architecture": {"input_modalities": ["text"]},
                },
                {
                    "id": "paid/model",
                    "pricing": {"prompt": "0.001", "completion": "0.002"},
                },
                {
                    "id": "half-free",
                    "pricing": {"prompt": "0", "completion": "0.001"},
                },
            ]
        }
        models = openrouter_free_models(payload)
        self.assertEqual([m["id"] for m in models], ["free/model:free"])
        self.assertTrue(models[0]["tools"])
        self.assertEqual(models[0]["context"], 32768)

    def test_zero_string_variants(self):
        payload = {"data": [
            {"id": "a", "pricing": {"prompt": "0.0", "completion": "0.00"}},
            {"id": "b", "pricing": {"prompt": "0", "completion": "0"}},
        ]}
        self.assertEqual(len(openrouter_free_models(payload)), 2)


class CatalogTest(unittest.TestCase):
    def test_bare_list_with_tier_and_aliases(self):
        payload = [
            {
                "name": "openai-fast",
                "tier": "anonymous",
                "aliases": ["openai", "gpt-oss"],
                "input_modalities": ["text"],
                "tools": True,
            },
            {"name": "paid-model", "tier": "seed"},
        ]
        models = _catalog_models(payload, tier="anonymous", with_aliases=True)
        self.assertEqual(
            {m["id"] for m in models}, {"openai-fast", "openai", "gpt-oss"}
        )
        self.assertTrue(all(m["tools"] for m in models))

    def test_openai_shape(self):
        payload = {"data": [
            {
                "id": "koboldcpp/Llama-3.2-1B-Instruct",
                "context_length": 12288,
                "architecture": {"input_modalities": ["text"]},
            }
        ]}
        models = _catalog_models(payload)
        self.assertEqual(models[0]["id"], "koboldcpp/Llama-3.2-1B-Instruct")
        self.assertEqual(models[0]["context"], 12288)

    def test_catalog_provider_meta(self):
        source = {
            "id": "horde-source",
            "name": "Horde source",
            "provider": {
                "id": "aihorde",
                "name": "AI Horde",
                "base_url": "https://oai.aihorde.net/v1",
                "keyless": True,
                "probe_max_tokens": 16,
            },
        }
        provider = _catalog_provider(source, [{"id": "m"}], "https://oai.aihorde.net/v1/models")
        self.assertEqual(provider["id"], "aihorde")
        self.assertTrue(provider["keyless"])
        self.assertEqual(provider["probe_max_tokens"], 16)
        self.assertTrue(provider["gateway"])
        self.assertEqual(provider["sources"], ["https://oai.aihorde.net/v1/models"])

    def test_catalog_provider_infers_base_url(self):
        provider = _catalog_provider(
            {"id": "x"}, [{"id": "m"}], "https://example.com/v1/models"
        )
        self.assertEqual(provider["base_url"], "https://example.com/v1")


if __name__ == "__main__":
    unittest.main()
