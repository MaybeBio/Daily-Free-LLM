import csv
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from shovel import render

REGISTRY = {
    "stats": {
        "providers": 2,
        "models": 2,
        "gateway_providers": 1,
        "categories": {"api": 1, "chat": 1},
    },
    "providers": [
        {
            "id": "alpha",
            "name": "Alpha",
            "provider_company": "Alpha Inc",
            "categories": ["api"],
            "region": "global",
            "free_nature": "permanent",
            "env": "ALPHA_KEY",
            "base_url": "https://alpha/v1",
            "keyless": False,
            "gateway": True,
            "access": {"phone": "required"},
            "limits": {"rpm": 5, "rpd": 1000},
            "models": [{"id": "qwen3", "context": 32768}],
            "verified_at": "2026-10-30",
            "sources": ["https://alpha"],
            "notes": "测试渠道",
        },
        {
            "id": "chat",
            "name": "</script><script>alert(1)</script>",
            "provider_company": "",
            "categories": ["chat"],
            "region": "unknown",
            "free_nature": "unknown",
            "gateway": False,
            "models": [],
            "representative_models": "Grok",
            "notes": "",
        },
    ],
}

CHANGES = [
    {
        "at": "2026-11-11 12:00:00",
        "source": "openrouter-models",
        "name": "OpenRouter",
        "added_count": 2,
        "removed_count": 0,
        "added": ["a", "b"],
        "removed": [],
    }
]


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.result = render.render_all(REGISTRY, None, CHANGES, self.tmp)

    def test_files_written(self):
        for name in ("README.md", "free_llm_api.csv", "site/index.html", "site/feed.xml"):
            self.assertTrue((self.tmp / name).exists(), name)

    def test_readme_contains_usage_and_catalog(self):
        text = (self.tmp / "README.md").read_text(encoding="utf-8")
        self.assertIn("python -m shovel serve", text)
        self.assertIn("Alpha", text)
        self.assertIn("2026-10-30", text)

    def test_csv_rows_match_providers(self):
        with (self.tmp / "free_llm_api.csv").open(encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        self.assertEqual(rows[0][0], "分类")
        self.assertEqual(len(rows), len(REGISTRY["providers"]) + 1)
        ids = {row[1] for row in rows[1:]}
        self.assertIn("Alpha", ids)

    def test_payload_escapes_script_close(self):
        html = (self.tmp / "site/index.html").read_text(encoding="utf-8")
        marker = 'type="application/json">'
        start = html.index(marker) + len(marker)
        end = html.index("</script>", start)
        blob = html[start:end]
        self.assertIn("<\\/script>", blob)
        payload = json.loads(blob)
        names = {p["name"] for p in payload["providers"]}
        self.assertIn("</script><script>alert(1)</script>", names)

    def test_feed_is_valid_rss(self):
        tree = ET.parse(self.tmp / "site/feed.xml")
        root = tree.getroot()
        self.assertEqual(root.tag, "rss")
        items = root.findall("./channel/item")
        self.assertEqual(len(items), 1)
        self.assertIn("OpenRouter", items[0].findtext("title"))

    def test_status_applied(self):
        status = {
            "generated_at": "2026-11-11T00:00:00Z",
            "providers": {
                "alpha": {
                    "status": "ok",
                    "models": {"qwen3": {"status": "ok", "latency_ms": 120}},
                }
            },
        }
        tmp = Path(tempfile.mkdtemp())
        text = render.render_readme(REGISTRY, status, CHANGES, tmp / "README.md")
        self.assertIn("正常可用", text)


if __name__ == "__main__":
    unittest.main()
