from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import util
from .diff import append_changes, normalize_lines, update_snapshot


def strip_html(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    return "\n".join(normalize_lines(text))


def _zero(value) -> bool:
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def openrouter_free_models(payload: dict) -> list[dict]:
    models = []
    for item in payload.get("data", []):
        pricing = item.get("pricing") or {}
        if not (_zero(pricing.get("prompt")) and _zero(pricing.get("completion"))):
            continue
        architecture = item.get("architecture") or {}
        modalities = architecture.get("input_modalities") or ["text"]
        models.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or item.get("id"),
                "context": item.get("context_length")
                or (item.get("top_provider") or {}).get("context_length"),
                "tools": "tools" in (item.get("supported_parameters") or []),
                "modalities": modalities,
                "note": "OpenRouter 免费模型（prompt/completion 单价均为 0）",
            }
        )
    return [m for m in models if m.get("id")]


def _openrouter_provider(models: list[dict], url: str) -> dict:
    return {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env": "OPENROUTER_KEY",
        "key_url": "https://openrouter.ai/keys",
        "homepage": "https://openrouter.ai",
        "categories": ["api"],
        "region": "global",
        "free_nature": "permanent",
        "verified_at": util.today_iso(),
        "sources": [url],
        "notes": "免费模型目录由 OpenRouter /models 实时发现，仅保留输入输出单价均为 0 的模型。",
        "headers": {
            "HTTP-Referer": "http://localhost",
            "X-Title": "freellm-shovel",
        },
        "gateway": True,
        "models": models,
    }


def _catalog_models(payload, tier: str | None = None, with_aliases: bool = False) -> list[dict]:
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    models: list[dict] = []
    seen: set[str] = set()

    def add(model_id: str, item: dict, note: str = "") -> None:
        if not model_id or model_id in seen:
            return
        seen.add(model_id)
        architecture = item.get("architecture") or {}
        models.append(
            {
                "id": model_id,
                "name": item.get("name") or model_id,
                "context": item.get("context_length")
                or (item.get("top_provider") or {}).get("context_length"),
                "tools": bool(item.get("tools")) or "tools" in (item.get("supported_parameters") or []),
                "modalities": architecture.get("input_modalities")
                or item.get("input_modalities")
                or ["text"],
                "note": note,
            }
        )

    for item in items:
        if not isinstance(item, dict):
            continue
        if tier and item.get("tier") != tier:
            continue
        model_id = item.get("id") or item.get("name")
        add(str(model_id or ""), item)
        if with_aliases:
            for alias in item.get("aliases") or []:
                add(str(alias), item, f"{model_id} 的别名")
    return models


def _catalog_provider(source: dict, models: list[dict], url: str) -> dict:
    meta = dict(source.get("provider") or {})
    provider = {
        "id": meta.get("id") or source.get("id") or util.slugify_id(source.get("name", "")),
        "name": meta.get("name") or source.get("name") or source.get("id"),
        "base_url": meta.get("base_url") or url.rsplit("/models", 1)[0],
        "env": meta.get("env") or "",
        "keyless": bool(meta.get("keyless", False)),
        "key_url": meta.get("key_url") or "",
        "homepage": meta.get("homepage") or "",
        "categories": meta.get("categories") or ["api"],
        "region": meta.get("region") or "global",
        "free_nature": meta.get("free_nature") or "permanent",
        "verified_at": meta.get("verified_at") or util.today_iso(),
        "sources": [url],
        "notes": meta.get("notes") or "模型目录由公开 /models 端点实时发现。",
        "headers": meta.get("headers") or {},
        "gateway": True,
        "models": models,
    }
    for key, value in meta.items():
        if key not in provider:
            provider[key] = value
    return provider


def update_external(
    registry: dict,
    sources_path: Path | None = None,
    snapshot_dir: Path | None = None,
    changes_path: Path | None = None,
    timeout: float = 20.0,
) -> tuple[list[dict], list[dict], list[dict]]:
    sources_path = sources_path or (util.CONFIG_DIR / "sources.json")
    changes_path = changes_path or (util.DATA_DIR / "changes.jsonl")
    config = util.read_json(sources_path, default={"sources": []})
    discovered: list[dict] = []
    changes: list[dict] = []
    reports: list[dict] = []

    for source in config.get("sources", []):
        if not source.get("enabled", True):
            continue
        source_id = source.get("id") or util.slugify_id(source.get("name", ""))
        kind = source.get("kind", "text")
        url = source.get("url", "")
        code, body, _ = util.http_request("GET", url, timeout=timeout)
        if code == 0 or code >= 400:
            util.log(f"源 {source_id} 抓取失败: HTTP {code}")
            reports.append(
                {"id": source_id, "name": source.get("name", source_id), "ok": False,
                 "error": f"HTTP {code}"}
            )
            continue

        if kind in {"openrouter_models", "openai_models", "pollinations_models"}:
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                util.log(f"源 {source_id} 返回的不是合法 JSON")
                reports.append(
                    {"id": source_id, "name": source.get("name", source_id),
                     "ok": False, "error": "invalid json"}
                )
                continue
            if kind == "openrouter_models":
                models = openrouter_free_models(payload)
                provider = _openrouter_provider(models, url)
            else:
                models = _catalog_models(
                    payload,
                    tier=source.get("tier"),
                    with_aliases=kind == "pollinations_models",
                )
                provider = _catalog_provider(source, models, url)
            discovered.append(provider)
            snapshot = "\n".join(sorted(m["id"] for m in models))
            count = len(models)
        elif kind == "html":
            snapshot = strip_html(body)
            count = len(snapshot.splitlines())
        else:
            snapshot = body
            count = len(normalize_lines(body))

        diff = update_snapshot(source_id, snapshot, snapshot_dir)
        record = append_changes(
            changes_path, source_id, source.get("name", source_id), diff
        )
        if record:
            changes.append(record)
        reports.append(
            {
                "id": source_id,
                "name": source.get("name", source_id),
                "ok": True,
                "items": count,
                "baseline": diff.get("baseline", False),
                "added": diff.get("added_count", 0),
                "removed": diff.get("removed_count", 0),
            }
        )

    return discovered, changes, reports
