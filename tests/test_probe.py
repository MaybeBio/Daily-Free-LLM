import tempfile
import unittest
from pathlib import Path
from unittest import mock

from shovel import probe


class ClassifyTest(unittest.TestCase):
    def test_status_mapping(self):
        cases = {
            200: "ok",
            401: "auth_error",
            403: "auth_error",
            404: "not_found",
            429: "rate_limited",
            500: "server_error",
            502: "server_error",
            0: "network_error",
            418: "error",
        }
        for code, expected in cases.items():
            with self.subTest(code=code):
                self.assertEqual(probe.classify(code), expected)

    def test_400_quota_is_rate_limited(self):
        self.assertEqual(
            probe.classify(400, '{"error":{"message":"quota exceeded"}}'),
            "rate_limited",
        )
        self.assertEqual(
            probe.classify(400, '{"error":{"message":"invalid model"}}'),
            "bad_request",
        )


class ProbeModelTest(unittest.TestCase):
    def test_skips_without_key(self):
        result = probe.probe_model(
            {"id": "p", "env": "MISSING_KEY", "base_url": "https://x/v1"},
            {"id": "m"},
        )
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["model"], "m")

    def test_placeholder_base_url_skips(self):
        result = probe.probe_model(
            {
                "id": "cf",
                "env": "CF_KEY",
                "base_url": "https://api/{CF_ACCOUNT}/v1",
                "keyless": True,
            },
            {"id": "m"},
        )
        self.assertEqual(result["status"], "skipped")

    def test_uses_provider_min_max_tokens(self):
        provider = {
            "id": "horde",
            "keyless": True,
            "base_url": "https://x/v1",
            "probe_max_tokens": 16,
        }
        with mock.patch.object(probe.util, "http_request", return_value=(200, "{}", {})) as call:
            result = probe.probe_model(provider, {"id": "m"})
        self.assertEqual(result["status"], "ok")
        payload = call.call_args.kwargs["data"].decode()
        self.assertIn('"max_tokens": 16', payload)

    def test_tools_result(self):
        provider = {"id": "p", "keyless": True, "base_url": "https://x/v1"}
        body = (
            '{"choices":[{"message":{"tool_calls":[{"id":"1","type":"function",'
            '"function":{"name":"ping","arguments":"{}"}}]}}]}'
        )
        with mock.patch.object(probe.util, "http_request", return_value=(200, body, {})):
            result = probe.probe_model(provider, {"id": "m"}, tools=True)
        self.assertTrue(result["tools"])


class RunProbeTest(unittest.TestCase):
    def test_missing_keys_do_not_crash(self):
        tmp = Path(tempfile.mkdtemp())
        registry = {
            "providers": [
                {
                    "id": "p",
                    "name": "P",
                    "env": "MISSING_KEY",
                    "base_url": "https://x/v1",
                    "models": [{"id": "m1"}],
                }
            ]
        }
        doc = probe.run_probe(
            registry,
            status_path=tmp / "status.json",
            uptime_path=tmp / "uptime.jsonl",
        )
        self.assertEqual(
            doc["providers"]["p"]["models"]["m1"]["status"], "skipped"
        )


if __name__ == "__main__":
    unittest.main()
