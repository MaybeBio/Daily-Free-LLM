from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import util

STATUS_LABELS = {
    "ok": "✅ 正常可用",
    "rate_limited": "⚠️ 限流 / 额度耗尽",
    "not_found": "❌ 模型已下架",
    "auth_error": "🔑 密钥失效 / 权限变更",
    "bad_request": "🟠 请求被拒（参数或模型不被支持）",
    "server_error": "🌐 服务端异常",
    "network_error": "📡 网络超时或不可达",
    "skipped": "⏭️ 未配置密钥",
    "error": "❓ 其他错误",
}

_PRECEDENCE = [
    "ok", "rate_limited", "bad_request", "server_error",
    "network_error", "auth_error", "not_found", "error", "skipped",
]

_QUOTA_HINTS = (
    "quota", "rate limit", "too many requests", "insufficient", "exceeded",
    "额度", "限流", "余额不足", "配额", "超出",
)


def _message(code: int, body: str) -> str:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return re.sub(r"\s+", " ", str(body or "")).strip()[:180]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)[:180]
        if error:
            return str(error)[:180]
        for key in ("message", "detail", "msg"):
            if data.get(key):
                return str(data[key])[:180]
    return re.sub(r"\s+", " ", str(body or "")).strip()[:180]


def _quota_hint(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(hint in lowered for hint in _QUOTA_HINTS)


def classify(code: int, body: str = "") -> str:
    if code == 200:
        return "ok"
    if code in (401, 403):
        return "auth_error"
    if code == 404:
        return "not_found"
    if code == 429:
        return "rate_limited"
    if code == 400:
        return "rate_limited" if _quota_hint(body) else "bad_request"
    if 500 <= code < 600:
        return "server_error"
    if code == 0:
        return "network_error"
    return "error"


def _headers(provider: dict, key: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    for name, value in (provider.get("headers") or {}).items():
        headers[str(name)] = util.expand_env(str(value))
    return headers


def _key_for(provider: dict) -> str:
    env = provider.get("env") or ""
    return os.environ.get(env, "") if env else ""


def _base_url(provider: dict) -> str:
    base = util.expand_env(str(provider.get("base_url") or "")).rstrip("/")
    return base


def probe_model(provider: dict, model: dict, timeout: float = 15.0, tools: bool = False) -> dict:
    model_id = model.get("id", "")
    key = _key_for(provider)
    base = _base_url(provider)
    if not key and not provider.get("keyless"):
        return {
            "status": "skipped",
            "message": f"未配置 {provider.get('env') or '密钥'}",
            "checked_at": util.now_utc(),
            "model": model_id,
        }
    if not base or re.search(r"\{[A-Z0-9_]+\}", base):
        return {
            "status": "skipped",
            "message": "base_url 含未解析占位符",
            "checked_at": util.now_utc(),
            "model": model_id,
        }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": int(provider.get("probe_max_tokens") or 1),
        "stream": False,
    }
    if tools:
        payload["max_tokens"] = 8
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Return pong",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    url = base + "/chat/completions"
    started = time.monotonic()
    code, body, _ = util.http_request(
        "POST",
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(provider, key),
        timeout=timeout,
    )
    latency = int((time.monotonic() - started) * 1000)
    status = classify(code, body)
    result = {
        "status": status,
        "http_status": code or None,
        "latency_ms": latency,
        "message": "" if status == "ok" else _message(code, body),
        "checked_at": util.now_utc(),
        "model": model_id,
    }
    if tools and status == "ok":
        try:
            data = json.loads(body)
            message = (data.get("choices") or [{}])[0].get("message") or {}
            result["tools"] = bool(message.get("tool_calls"))
        except (json.JSONDecodeError, IndexError, AttributeError, TypeError):
            result["tools"] = False
    return result


def _aggregate(statuses: list[str]) -> str:
    for status in _PRECEDENCE:
        if status in statuses:
            return status
    return "unknown"


def _selected(provider: dict, only: list[str] | None) -> bool:
    if not only:
        return True
    pid = provider.get("id", "").lower()
    env = (provider.get("env") or "").lower()
    return any(token.lower() in {pid, env} for token in only)


def _append_uptime(path: Path, record: dict, keep: int = 1000) -> None:
    records = util.read_jsonl(path)
    records.append(record)
    records = records[-keep:]
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    util.atomic_write(path, text)


def run_probe(
    registry: dict,
    only: list[str] | None = None,
    timeout: float = 15.0,
    workers: int = 8,
    tools: bool = False,
    status_path: Path | None = None,
    uptime_path: Path | None = None,
) -> dict:
    status_path = status_path or (util.DATA_DIR / "status.json")
    uptime_path = uptime_path or (util.DATA_DIR / "uptime.jsonl")
    providers = registry.get("providers", [])
    provider_results: dict[str, dict] = {}
    all_results: list[dict] = []

    for provider in providers:
        if not _selected(provider, only):
            continue
        if not provider.get("env") and not provider.get("keyless"):
            if only:
                provider_results[provider["id"]] = {
                    "status": "skipped",
                    "checked_at": util.now_utc(),
                    "models": {},
                }
            continue
        models = provider.get("models", [])
        if not models:
            continue
        entries: dict[str, dict] = {}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(probe_model, provider, model, timeout, tools): model
                for model in models
            }
            for future in as_completed(futures):
                model = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "status": "error",
                        "message": str(exc)[:180],
                        "checked_at": util.now_utc(),
                        "model": model.get("id", ""),
                    }
                entries[result["model"]] = result
                all_results.append({**result, "provider": provider["id"]})
        provider_results[provider["id"]] = {
            "status": _aggregate([r["status"] for r in entries.values()]),
            "checked_at": util.now_utc(),
            "models": entries,
        }
        util.log(
            f"{provider['name']}: {provider_results[provider['id']]['status']} "
            f"({len(entries)} 模型)"
        )

    counts: dict[str, int] = {}
    for result in all_results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1
    summary = {
        "providers_checked": len(provider_results),
        "models_checked": len(all_results),
        "status_counts": counts,
    }
    document = {
        "generated_at": util.now_utc(),
        "generated_at_cst": util.now_cst(),
        "summary": summary,
        "providers": provider_results,
    }
    util.write_json(status_path, document)

    uptime = {
        "t": util.now_cst("%Y-%m-%d %H:%M"),
        "p": {
            pid: [
                entry["status"],
                sum(1 for m in entry["models"].values() if m["status"] == "ok"),
                sum(1 for m in entry["models"].values() if m["status"] == "rate_limited"),
                sum(1 for m in entry["models"].values() if m["status"] == "auth_error"),
                sum(1 for m in entry["models"].values() if m["status"] == "not_found"),
                sum(1 for m in entry["models"].values()
                    if m["status"] in {"server_error", "network_error", "error", "bad_request"}),
            ]
            for pid, entry in provider_results.items()
        },
    }
    _append_uptime(uptime_path, uptime)
    return document
