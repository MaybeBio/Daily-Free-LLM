import unittest

from shovel import sources
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


FREE_LLM_README = """
<!--TABLE:PERMANENT:START-->
| Provider | Credit Card? | Rate Limit | Daily Limit | Monthly Limit | Key Models |
|:---|:---:|:---|:---|:---|:---|
| [Groq](https://console.groq.com/) | No | 30 RPM | 1,000 requests/day | Free Forever | GPT-OSS 120B, Qwen3.8 27B |
| [Mistral (La Plateforme)](https://console.mistral.ai/) | Phone verification | 1 request/second | - | Free | Mistral Small |
<!--TABLE:PERMANENT:END-->
<!--TABLE:ONE_TIME:START-->
| Provider | Credit Card? | Rate Limit | Daily Limit | Monthly Limit | Key Models |
|:---|:---:|:---|:---|:---|:---|
| [Together AI](https://api.together.xyz/) | Card required | 60 RPM | - | One-time credit | Llama 3.3 |
<!--TABLE:ONE_TIME:END-->
<!--TABLE:QUICKREF:START-->
| Provider | Base URL | Get API Key |
|:---|:---|:---|
| [Groq](https://console.groq.com/) | `https://api.groq.com/openai/v1` | [Get Key →](https://console.groq.com/keys) |
| [OpenRouter](https://openrouter.ai/) | `https://openrouter.ai/api/v1` | [Get Key →](https://openrouter.ai/keys) |
<!--TABLE:QUICKREF:END-->
"""

FREELLM_MODELS = """
<tr class="model-row clickable-row" data-href="/models/agnes-ai/agnes-2-0-flash" data-name="agnes-2.0-flash" data-provider="Agnes AI" data-provider-slug="agnes-ai" data-modality="text,vision,reasoning" data-context="256000" data-tier-type="permanent">
<td><a href="/models/agnes-ai/agnes-2-0-flash" class="model-link">agnes-2.0-flash</a></td><td class="mono">30 RPM</td></tr>
<tr class="model-row clickable-row" data-href="/models/groq/gpt-oss-120b" data-name="gpt-oss-120b" data-provider="Groq" data-provider-slug="groq" data-modality="text" data-context="131072" data-tier-type="permanent">
<td><a href="/models/groq/gpt-oss-120b" class="model-link">gpt-oss-120b</a></td><td class="mono">30 RPM</td></tr>
<tr class="model-row clickable-row" data-href="/models/openrouter/baidu-ernie-5-5" data-name="baidu: ernie 5.5 (free)" data-provider="OpenRouter" data-provider-slug="openrouter" data-modality="text" data-context="131072" data-tier-type="permanent">
<td><a href="/models/openrouter/baidu-ernie-5-5" class="model-link">Baidu: ERNIE 5.5 (free)</a></td><td class="mono">20 RPM</td></tr>
"""

FREE_LLM_CATALOG = {
    "provider_count": 3,
    "providers": [
        {
            "slug": "groq",
            "name": "Groq",
            "type": "API",
            "website": "https://groq.com",
            "base_url": "https://api.groq.com/openai/v1",
            "free_tier": "truly_free",
            "category": "permanent",
            "signup_requirement": "no",
            "verified": True,
            "rate_limit": "30 RPM",
            "daily_limit": "1,000 requests/day",
            "credits": None,
            "credits_duration": None,
            "models": [
                {"id": "gpt-oss-120b", "name": "GPT-OSS 120B", "context": "131K"}
            ],
        },
        {
            "slug": "zro",
            "name": "ZRO",
            "type": "Proxy",
            "website": "https://zro.ai",
            "base_url": "https://api.zro.ai/v1",
            "free_tier": "truly_free",
            "category": "renewable",
            "signup_requirement": "phone_verification",
            "verified": False,
            "rate_limit": "",
            "daily_limit": "Resets every day",
            "credits": None,
            "credits_duration": None,
            "models": [{"id": "zro-flash", "name": "ZRO Flash", "context": "1M"}],
        },
        {
            "slug": "ollama",
            "name": "Ollama",
            "type": "Local",
            "website": "https://ollama.com",
            "base_url": "http://localhost:11434",
            "free_tier": "truly_free",
            "category": None,
            "signup_requirement": "registration",
            "verified": False,
            "rate_limit": "",
            "daily_limit": "",
            "credits": None,
            "credits_duration": None,
            "models": [{"id": "llama3", "name": "Llama 3", "context": None}],
        },
    ],
}


class FreeLlmCatalogTest(unittest.TestCase):
    def setUp(self):
        self.providers = sources.free_llm_catalog(FREE_LLM_CATALOG)

    def test_provider_fields(self):
        groq = next(p for p in self.providers if p["id"] == "groq")
        self.assertEqual(groq["base_url"], "https://api.groq.com/openai/v1")
        self.assertEqual(groq["free_nature"], "permanent")
        self.assertEqual(groq["categories"], ["api"])
        self.assertIn("30 RPM", groq["limits_text"])
        self.assertIn("1,000 requests/day", groq["limits_text"])
        self.assertEqual(groq["models"][0]["id"], "gpt-oss-120b")
        self.assertEqual(groq["models"][0]["context"], "131K")

    def test_free_nature_and_categories(self):
        zro = next(p for p in self.providers if p["id"] == "zro")
        self.assertEqual(zro["free_nature"], "daily")
        self.assertEqual(zro["categories"], ["cloud"])
        self.assertEqual(zro["access"]["phone"], "required")
        ollama = next(p for p in self.providers if p["id"] == "ollama")
        self.assertEqual(ollama["categories"], ["chat"])
        self.assertNotIn("gateway", ollama)


FREELLM_DETAIL = """
<button type="button" class="client-import-trigger" data-slug="agnes-ai" data-name="Agnes AI"
 data-endpoint="https://apihub.agnes-ai.com/v1" data-homepage="https://agnes-ai.com/doc"></button>
<a href="https://platform.agnes-ai.com/settings/apiKeys" class="action-btn action-key">Get API Key</a>
<div>OpenAI Compatible <strong>Yes</strong></div>
<div>Credit Card <strong>Not required</strong></div>
<div>Phone Verification <strong>Not required</strong></div>
<div>Primary Limit 30 RPM</div><div>Context Range 4K – 256K</div>
"""


class FreeLlmReadmeTest(unittest.TestCase):
    def setUp(self):
        self.providers = sources.free_llm_providers(
            FREE_LLM_README, "https://raw.example/readme"
        )

    def test_limits_and_access(self):
        groq = next(p for p in self.providers if p["name"] == "Groq")
        self.assertEqual(groq["base_url"], "https://api.groq.com/openai/v1")
        self.assertEqual(groq["key_url"], "https://console.groq.com/keys")
        self.assertEqual(groq["free_nature"], "permanent")
        self.assertEqual(groq["access"]["card"], "not_required")
        self.assertIn("30 RPM", groq["limits_text"])
        self.assertIn("GPT-OSS 120B", groq["representative_models"])

        mistral = next(p for p in self.providers if p["name"].startswith("Mistral"))
        self.assertEqual(mistral["access"]["phone"], "required")
        self.assertIn("1 request/second", mistral["limits_text"])

    def test_one_time_section(self):
        together = next(p for p in self.providers if p["name"] == "Together AI")
        self.assertEqual(together["free_nature"], "one_time")
        self.assertEqual(together["access"]["card"], "required")

    def test_quickref_only_provider_is_kept(self):
        openrouter = next(p for p in self.providers if p["name"] == "OpenRouter")
        self.assertEqual(openrouter["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(openrouter["free_nature"], "unknown")

    def test_catalog_entries_are_not_gateways(self):
        for provider in self.providers:
            self.assertFalse(provider["gateway"], provider["id"])
            self.assertEqual(provider["models"], [])


class FreeLlmNetTest(unittest.TestCase):
    def test_models_group_by_provider(self):
        groups = sources.freellm_models(FREELLM_MODELS)
        self.assertEqual(set(groups), {"agnes-ai", "groq", "openrouter"})
        agnes = groups["agnes-ai"]
        self.assertEqual(agnes["name"], "Agnes AI")
        self.assertEqual(agnes["tier"], "permanent")
        model = agnes["models"][0]
        self.assertEqual(model["id"], "agnes-2.0-flash")
        self.assertEqual(model["context"], 256000)
        self.assertIn("vision", model["modalities"])

    def test_display_names_are_not_model_ids(self):
        groups = sources.freellm_models(FREELLM_MODELS)
        self.assertEqual(groups["openrouter"]["models"], [])
        self.assertIn("Baidu: ERNIE 5.5 (free)", groups["openrouter"]["representative"])

    def test_detail_fields(self):
        detail = sources.freellm_provider(FREELLM_DETAIL)
        self.assertEqual(detail["base_url"], "https://apihub.agnes-ai.com/v1")
        self.assertEqual(
            detail["key_url"], "https://platform.agnes-ai.com/settings/apiKeys"
        )
        self.assertEqual(detail["access"]["card"], "not_required")
        self.assertEqual(detail["limits_text"], "30 RPM")
        self.assertTrue(detail["openai"])

    def test_provider_index(self):
        index = sources.freellm_provider_index(
            '<tr class="provider-row clickable-row" data-href="/providers/cerebras" '
            'data-tier-type="permanent"><td><a href="/providers/cerebras">Cerebras</a>'
            "</td></tr>"
        )
        self.assertEqual(index["cerebras"]["name"], "Cerebras")
        self.assertEqual(index["cerebras"]["tier"], "permanent")

    def test_provider_from_groups_and_details(self):
        groups = sources.freellm_models(FREELLM_MODELS)
        providers = sources.freellm_providers(
            groups, {"agnes-ai": FREELLM_DETAIL}, "https://freellm.net/models/"
        )
        agnes = next(p for p in providers if p["id"] == "agnes-ai")
        self.assertEqual(agnes["base_url"], "https://apihub.agnes-ai.com/v1")
        self.assertEqual(agnes["free_nature"], "permanent")
        self.assertEqual(agnes["api_style"], "openai")
        groq = next(p for p in providers if p["id"] == "groq")
        self.assertEqual(groq["base_url"], "")
        self.assertFalse(groq["gateway"])


if __name__ == "__main__":
    unittest.main()
