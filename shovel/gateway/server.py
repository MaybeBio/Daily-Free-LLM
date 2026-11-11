from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import util
from ..registry import apply_status
from .budgets import Budgets
from .router import Router


def _retry_after(headers) -> float | None:
    if not headers:
        return None
    value = headers.get("Retry-After")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class App:
    def __init__(
        self,
        registry: dict,
        status: dict | None,
        aliases: dict | None,
        config: dict | None,
        site_dir: Path | None = None,
    ) -> None:
        self.registry = registry
        self.status = status or {}
        self.aliases = aliases or {}
        self.config = config or {}
        self.budgets = Budgets()
        self.router = Router(registry, aliases, config, status, self.budgets)
        self.timeout = float(self.config.get("timeout_seconds", 60))
        self.stream_timeout = float(self.config.get("stream_timeout_seconds", 120))
        self.auth_env = self.config.get("auth_token_env", "SHOVEL_TOKEN")
        self.site_dir = Path(site_dir or util.SITE_DIR)
        self.verbose = bool(self.config.get("verbose", False))

    def models_payload(self) -> dict:
        data = apply_status(self.registry, self.status)
        entries = []
        seen = set()
        created = int(time.time())
        for provider in data.get("providers", []):
            if not provider.get("gateway"):
                continue
            for model in provider.get("models", []):
                model_id = model["id"]
                if model_id in seen:
                    continue
                seen.add(model_id)
                entries.append(
                    {
                        "id": model_id,
                        "object": "model",
                        "created": created,
                        "owned_by": provider["id"],
                        "provider": provider["id"],
                        "context_length": model.get("context"),
                        "status": model.get("status") or "untested",
                    }
                )
        for alias in (self.aliases.get("aliases") or {}):
            if alias in seen:
                continue
            seen.add(alias)
            entries.append(
                {
                    "id": alias,
                    "object": "model",
                    "created": created,
                    "owned_by": "alias",
                    "provider": "alias",
                    "context_length": None,
                    "status": "alias",
                }
            )
        return {"object": "list", "data": entries}


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, app: App) -> None:
        self.app = app
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "freellm-shovel/0.1"

    def log_message(self, fmt: str, *args) -> None:
        if getattr(self.server, "app", None) and self.server.app.verbose:
            super().log_message(fmt, *args)

    @property
    def app(self) -> App:
        return self.server.app

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_error_json(self, code: int, message: str) -> None:
        self._send_json(code, {"error": {"message": message, "type": "shovel_error"}})

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_error_json(404, f"not found: {path.name}")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _authorized(self) -> bool:
        token = os.environ.get(self.app.auth_env, "")
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        return header.startswith("Bearer ") and header[7:] == token

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_error_json(400, "请求体不是合法 JSON")
            return None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path in {"/v1/models", "/models"} and not self._authorized():
            self._send_error_json(401, "unauthorized")
            return
        if path in {"/v1/models", "/models"}:
            self._send_json(200, self.app.models_payload())
        elif path == "/healthz":
            stats = self.app.registry.get("stats", {})
            self._send_json(
                200, {"ok": True, **stats, "usage": self.app.budgets.stats()}
            )
        elif path == "/stats":
            self._send_json(
                200,
                {
                    "registry": self.app.registry.get("stats", {}),
                    "usage": self.app.budgets.stats(),
                    "cooldowns": {
                        pid: round(until - time.monotonic(), 1)
                        for pid, until in self.app.router.cooldowns.items()
                        if until > time.monotonic()
                    },
                },
            )
        elif path in {"/", "/index.html"}:
            self._send_file(self.app.site_dir / "index.html", "text/html; charset=utf-8")
        elif path == "/feed.xml":
            self._send_file(self.app.site_dir / "feed.xml", "application/rss+xml; charset=utf-8")
        else:
            self._send_error_json(404, f"unknown path: {path}")

    def do_POST(self) -> None:
        if not self._authorized():
            self._send_error_json(401, "unauthorized")
            return
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in {"/v1/chat/completions", "/chat/completions"}:
            self._chat_completions()
        else:
            self._send_error_json(404, f"unknown path: {path}")

    def _upstream_headers(self, candidate: dict, stream: bool) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
        }
        key = os.environ.get(candidate["env"], "") if candidate.get("env") else ""
        if key:
            headers["Authorization"] = f"Bearer {key}"
        for name, value in (candidate.get("headers") or {}).items():
            headers[str(name)] = util.expand_env(str(value))
        return headers

    def _chat_completions(self) -> None:
        body = self._read_json()
        if body is None:
            return
        requested = str(
            body.get("model")
            or self.app.config.get("default_model")
            or "auto"
        )
        stream = bool(body.get("stream", False))
        candidates = self.app.router.candidates(requested)
        if not candidates:
            self._send_error_json(
                503,
                f"没有可用候选：{requested}（可能未配置密钥、全部限流或模型不存在）",
            )
            return

        last_error = (503, f"所有候选都失败：{requested}")
        for candidate in candidates:
            key = os.environ.get(candidate["env"], "") if candidate.get("env") else ""
            if not key and not candidate.get("keyless"):
                continue
            upstream = dict(body)
            upstream["model"] = candidate["model"]
            url = candidate["base_url"] + "/chat/completions"
            timeout = self.app.stream_timeout if stream else self.app.timeout
            request = urllib.request.Request(
                url,
                data=json.dumps(upstream, ensure_ascii=False).encode("utf-8"),
                headers=self._upstream_headers(candidate, stream),
                method="POST",
            )
            try:
                response = urllib.request.urlopen(request, timeout=timeout)
            except urllib.error.HTTPError as exc:
                text = exc.read().decode("utf-8", "replace") if exc.fp else ""
                status = exc.code
                if status == 429:
                    kind = "rate_limited"
                elif status in (401, 403):
                    kind = "auth_error"
                elif status >= 500:
                    kind = "server_error"
                else:
                    kind = "bad_request"
                self.app.router.mark(candidate["provider"], kind, _retry_after(exc.headers))
                util.log(
                    f"上游失败 {candidate['provider']}/{candidate['model']}: "
                    f"HTTP {status} {text[:120]}"
                )
                last_error = (status, text or f"HTTP {status}")
                continue
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                self.app.router.mark(candidate["provider"], "network_error")
                util.log(
                    f"上游网络失败 {candidate['provider']}/{candidate['model']}: {exc}"
                )
                last_error = (502, str(exc))
                continue

            self.app.router.mark(candidate["provider"], "ok")
            if stream:
                self._stream_response(response, candidate, body, requested)
            else:
                self._json_response(response, candidate, requested)
            return

        code = last_error[0] if 400 <= last_error[0] < 600 else 502
        self._send_error_json(code, last_error[1][:400])

    def _json_response(self, response, candidate: dict, requested: str) -> None:
        raw = response.read()
        text = raw.decode("utf-8", "replace")
        prompt_tokens = len(json.dumps(self._messages_hint(requested))) // 4
        try:
            data = json.loads(text)
            usage = data.get("usage") or {}
            self.app.router.record(
                candidate["provider"],
                candidate["model"],
                "ok",
                usage.get("prompt_tokens", prompt_tokens),
                usage.get("completion_tokens", 0),
            )
        except json.JSONDecodeError:
            self.app.router.record(
                candidate["provider"], candidate["model"], "bad_response", prompt_tokens, 0
            )
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Shovel-Provider", candidate["provider"])
        self.send_header("X-Shovel-Model", candidate["model"])
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def _messages_hint(requested: str) -> list:
        return [{"role": "user", "content": "x" * 40}]

    def _stream_response(self, response, candidate: dict, body: dict, requested: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Shovel-Provider", candidate["provider"])
        self.send_header("X-Shovel-Model", candidate["model"])
        self._cors()
        self.end_headers()
        self.close_connection = True
        try:
            for line in response:
                self.wfile.write(line)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            response.close()
            prompt_tokens = len(json.dumps(body.get("messages", []))) // 4
            self.app.router.record(
                candidate["provider"], candidate["model"], "ok", prompt_tokens, 0
            )


def run_server(app: App, host: str | None = None, port: int | None = None) -> None:
    host = host or app.config.get("host", "127.0.0.1")
    port = int(port or app.config.get("port", 8756))
    server = GatewayServer((host, port), app)
    util.log(f"网关已启动: http://{host}:{port}/v1  （面板 GET /，健康检查 /healthz）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        util.log("网关已停止")
    finally:
        server.server_close()
