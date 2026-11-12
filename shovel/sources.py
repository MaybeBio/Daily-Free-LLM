from __future__ import annotations

import html
import json
import re
import time
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


_MIN_ITEMS = {
    "openrouter_models": 1,
    "openai_models": 1,
    "pollinations_models": 1,
    "freellm_net": 20,
    "free_llm_catalog": 50,
    "free_llm_readme": 30,
}


def _fetch(url: str, timeout: float, attempts: int = 3):
    code, body, headers = 0, "", {}
    for attempt in range(attempts):
        code, body, headers = util.http_request("GET", url, timeout=timeout)
        if code and code < 500 and code != 429:
            return code, body, headers
        if attempt + 1 < attempts:
            time.sleep(2 * (attempt + 1))
    return code, body, headers


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


_SECTION_NATURE = {
    "PERMANENT": "permanent",
    "RENEWABLE": "monthly",
    "ONE_TIME": "one_time",
    "LOCAL": "permanent",
}

_SECTION_RE = re.compile(
    r"<!--TABLE:(PERMANENT|RENEWABLE|ONE_TIME|LOCAL):START-->(.*?)"
    r"<!--TABLE:\1:END-->",
    re.S,
)


def _md_cells(line: str) -> list[str]:
    body = line.strip().strip("|")
    return [cell.strip() for cell in body.split("|")]


def _md_link(cell: str) -> tuple[str, str]:
    match = re.search(r"\[([^\]]+)\]\(([^)\s]+)\)", cell)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return _plain(cell), ""


def _plain(cell: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cell)
    return re.sub(r"[`*]", "", text).strip()


def _md_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = _md_cells(line)
        if cells and all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    return rows


def _access_from_card(cell: str) -> dict:
    text = _plain(cell).lower()
    if "card required" in text:
        return {"card": "required"}
    if "phone" in text:
        return {"card": "not_required", "phone": "required"}
    if "registration" in text or "signup" in text:
        return {"card": "not_required", "email": "required"}
    if text in {"no", "none", "no card"}:
        return {"card": "not_required"}
    return {}


def free_llm_providers(
    text: str,
    url: str,
    homepage: str = "https://free-llm.com/",
) -> list[dict]:
    providers: dict[str, dict] = {}

    def entry(name: str, link: str) -> dict:
        key = name.strip().lower()
        if key not in providers:
            providers[key] = {
                "id": util.slugify_id(name),
                "name": name.strip(),
                "homepage": link,
                "base_url": "",
                "key_url": "",
                "categories": ["api"],
                "region": "unknown",
                "free_nature": "unknown",
                "access": {},
                "limits_text": "",
                "representative_models": "",
                "verified_at": "",
                "sources": [homepage, url],
                "notes": "free-llm.com 渠道目录（站点每日同步）",
                "gateway": False,
                "models": [],
            }
        return providers[key]

    quick = re.search(
        r"<!--TABLE:QUICKREF:START-->(.*?)<!--TABLE:QUICKREF:END-->", text, re.S
    )
    if quick:
        for cells in _md_rows(quick.group(1)):
            if len(cells) < 3:
                continue
            name, link = _md_link(cells[0])
            if not name:
                continue
            item = entry(name, link or homepage)
            item["base_url"] = _plain(cells[1])
            key_link = re.search(r"\((https?://[^)]+)\)", cells[2])
            if key_link:
                item["key_url"] = key_link.group(1)

    for section, block in _SECTION_RE.findall(text):
        for cells in _md_rows(block):
            if len(cells) < 6:
                continue
            name, link = _md_link(cells[0])
            if not name:
                continue
            item = entry(name, link or homepage)
            item["free_nature"] = _SECTION_NATURE[section]
            item["access"] = _access_from_card(cells[1])
            limits = [
                _plain(cell)
                for cell in cells[2:5]
                if _plain(cell) not in {"", "-", "—", "–"}
            ]
            item["limits_text"] = "；".join(limits)
            item["representative_models"] = _plain(cells[5])
            if section == "LOCAL":
                item["notes"] = "free-llm.com 本地/自托管目录（无托管端点）"

    return list(providers.values())


_CATALOG_CATEGORIES = {
    "API": ["api"],
    "Trial Credits": ["api"],
    "Proxy": ["cloud"],
    "Local": ["chat"],
}


def _catalog_nature(raw: dict) -> str:
    if str(raw.get("free_tier") or "") == "trial_credits":
        return "one_time"
    category = str(raw.get("category") or "")
    if category == "permanent":
        return "permanent"
    if category == "renewable":
        text = f"{raw.get('daily_limit') or ''} {raw.get('rate_limit') or ''}".lower()
        if re.search(r"month|4 weeks|7-day|weekly", text):
            return "monthly"
        return "daily"
    if category == "trial_credit":
        return "one_time"
    return "unknown"


def _catalog_access(raw: dict) -> dict:
    requirement = str(raw.get("signup_requirement") or "").lower()
    access = {}
    if requirement == "phone_verification":
        access["phone"] = "required"
    elif requirement == "credit_card":
        access["card"] = "required"
    return access


def free_llm_catalog(payload, url: str = "https://free-llm.com/catalog.json") -> list[dict]:
    providers = payload.get("providers", []) if isinstance(payload, dict) else payload
    entries = []
    for raw in providers or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        pid = str(raw.get("slug") or util.slugify_id(name)).strip()
        if not name or not pid:
            continue
        models = []
        for item in raw.get("models") or []:
            if isinstance(item, str):
                item = {"id": item}
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": str(item.get("name") or model_id).strip(),
                    "context": item.get("context"),
                }
            )
        limits = []
        for key in ("rate_limit", "daily_limit"):
            text = str(raw.get(key) or "").strip()
            if text and text.lower() not in {"not published", "n/a", "none", "-"}:
                limits.append(text)
        if raw.get("credits"):
            credit = str(raw["credits"]).strip()
            if raw.get("credits_duration"):
                credit = f"{credit}（{raw['credits_duration']}）"
            limits.append(credit)
        entry = {
            "id": pid,
            "name": name,
            "homepage": str(raw.get("website") or "").strip(),
            "base_url": str(raw.get("base_url") or "").strip().rstrip("/"),
            "categories": _CATALOG_CATEGORIES.get(str(raw.get("type") or "API"), ["api"]),
            "free_nature": _catalog_nature(raw),
            "access": _catalog_access(raw),
            "limits_text": "；".join(limits),
            "models": models,
            "verified_at": "",
            "sources": [url],
            "notes": "free-llm.com 官方 JSON 目录（含免费模型与限额）",
        }
        entries.append(entry)
    return entries


_FREELLM_ATTR = re.compile(r'data-([a-z0-9-]+)="([^"]*)"')


def freellm_models(text: str) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for raw_attrs, body in re.findall(
        r'<tr class="model-row[^"]*"([^>]*)>(.*?)</tr>', text, re.S
    ):
        data = {key: html.unescape(value) for key, value in _FREELLM_ATTR.findall(raw_attrs)}
        href = re.match(r"/models/([^/]+)/", data.get("href", ""))
        slug = (
            href.group(1)
            if href
            else data.get("provider-slug") or util.slugify_id(data.get("provider", ""))
        )
        if not slug:
            continue
        group = groups.setdefault(
            slug,
            {
                "slug": slug,
                "name": data.get("provider") or slug,
                "models": [],
                "tier": "unknown",
            },
        )
        link = re.search(
            r'<a href="/models/' + re.escape(slug) + r'/[^"]+"[^>]*>([^<]+)</a>',
            body,
        )
        model_id = html.unescape(link.group(1)).strip() if link else data.get("name", "")
        if not model_id or " " in model_id:
            group.setdefault("representative", []).append(
                model_id or data.get("name") or ""
            )
            if data.get("tier-type"):
                group["tier"] = data["tier-type"]
            continue
        context = data.get("context") or ""
        group["models"].append(
            {
                "id": model_id,
                "name": data.get("name") or model_id,
                "context": int(context) if context.isdigit() else None,
                "modalities": [
                    part
                    for part in (data.get("modality") or "text").split(",")
                    if part
                ],
                "note": f"freellm.net 目录（{data.get('tier-type') or 'unknown'} 层）",
            }
        )
        if data.get("tier-type"):
            group["tier"] = data["tier-type"]
    return groups


def freellm_provider(detail: str) -> dict:
    data = {key: html.unescape(value) for key, value in _FREELLM_ATTR.findall(detail)}
    flat = re.sub(r"\s+", " ", strip_html(detail))
    access: dict[str, str] = {}
    if "Credit Card Not required" in flat:
        access["card"] = "not_required"
    elif re.search(r"Credit Card\s+Required", flat):
        access["card"] = "required"
    if "Phone Verification Not required" in flat:
        access["phone"] = "not_required"
    elif re.search(r"Phone Verification\s+Required", flat):
        access["phone"] = "required"
    key_tag = re.search(r"<a[^>]*action-key[^>]*>", detail)
    key = re.search(r'href="([^"]+)"', key_tag.group(0)) if key_tag else None
    limit = re.search(r"Primary Limit (.{1,80}?) Context Range", flat)
    return {
        "base_url": data.get("endpoint") or "",
        "homepage": data.get("homepage") or "",
        "key_url": html.unescape(key.group(1)) if key else "",
        "access": access,
        "limits_text": limit.group(1).strip() if limit else "",
        "openai": bool(re.search(r"OpenAI Compatible\s+Yes", flat)),
    }


def freellm_provider_index(text: str) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for raw_attrs, body in re.findall(
        r'<tr class="provider-row[^"]*"([^>]*)>(.*?)</tr>', text, re.S
    ):
        data = {key: html.unescape(value) for key, value in _FREELLM_ATTR.findall(raw_attrs)}
        slug = str(data.get("href", "")).split("/providers/")[-1].strip("/")
        if not slug:
            continue
        link = re.search(
            r'<a href="/providers/' + re.escape(slug) + r'"[^>]*>([^<]+)</a>', body
        )
        entries[slug] = {
            "name": html.unescape(link.group(1)).strip() if link else slug,
            "tier": data.get("tier-type") or "unknown",
        }
    return entries


_FREELLM_TIER = {
    "permanent": "permanent",
    "trial": "limited",
    "daily": "daily",
    "monthly": "monthly",
    "one_time": "one_time",
}


def freellm_providers(
    groups: dict[str, dict],
    details: dict[str, str],
    url: str,
) -> list[dict]:
    providers = []
    for slug, group in groups.items():
        detail = freellm_provider(details.get(slug, ""))
        tier = _FREELLM_TIER.get(group.get("tier", ""), "limited")
        provider = {
            "id": slug,
            "name": group["name"],
            "base_url": detail["base_url"],
            "env": "",
            "keyless": False,
            "key_url": detail["key_url"],
            "homepage": detail["homepage"],
            "api_style": "openai" if detail["openai"] else "",
            "categories": ["api"],
            "region": "unknown",
            "free_nature": tier,
            "access": detail["access"],
            "limits_text": detail["limits_text"],
            "representative_models": ", ".join(
                sorted(set(group.get("representative") or []))
            ),
            "verified_at": "",
            "sources": [url, f"https://freellm.net/providers/{slug}"],
            "notes": "freellm.net 免费/试用模型目录（含站点实测状态）",
            "models": group["models"],
        }
        if not detail["openai"] or not detail["base_url"]:
            provider["gateway"] = False
        providers.append(provider)
    return providers


def _provider_snapshot(providers: list[dict]) -> str:
    lines = []
    for provider in providers:
        models = ",".join(sorted(m.get("id", "") for m in provider.get("models", [])))
        lines.append(
            "|".join(
                [
                    str(provider.get("id", "")),
                    str(provider.get("name", "")),
                    str(provider.get("base_url", "")),
                    str(provider.get("free_nature", "")),
                    str(provider.get("limits_text", "")),
                    models,
                ]
            )
        )
    return "\n".join(sorted(lines))


def update_external(
    registry: dict,
    sources_path: Path | None = None,
    snapshot_dir: Path | None = None,
    changes_path: Path | None = None,
    timeout: float = 20.0,
    daily_dir: Path | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    sources_path = sources_path or (util.CONFIG_DIR / "sources.json")
    changes_path = changes_path or (util.DATA_DIR / "changes.jsonl")
    archive_dir = (daily_dir or util.DAILY_DIR) / util.today_iso() / "snapshots"
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
        code, body, _ = _fetch(url, timeout)
        if code == 0 or code >= 400:
            util.log(f"源 {source_id} 抓取失败: HTTP {code}")
            reports.append(
                {"id": source_id, "name": source.get("name", source_id), "ok": False,
                 "error": f"HTTP {code}"}
            )
            continue

        found: list[dict] = []
        if kind == "freellm_net":
            groups = freellm_models(body)
            index_code, index_body, _ = _fetch(
                source.get("providers_url") or "https://freellm.net/providers/",
                timeout,
            )
            if index_code == 200:
                for slug, meta in freellm_provider_index(index_body).items():
                    group = groups.setdefault(
                        slug, {"slug": slug, "name": meta["name"], "models": [], "tier": meta["tier"]}
                    )
                    if not group.get("models"):
                        group["name"] = meta["name"]
                        group["tier"] = meta["tier"]
            details: dict[str, str] = {}
            for slug in groups:
                detail_code, detail_body, _ = _fetch(
                    f"https://freellm.net/providers/{slug}", timeout, attempts=2
                )
                if detail_code == 200:
                    details[slug] = detail_body
            found = freellm_providers(groups, details, url)
            snapshot = _provider_snapshot(found)
            count = len(found)
            model_count = sum(len(p.get("models") or []) for p in found)
            if model_count < 50:
                util.log(f"源 {source_id} 模型行异常: {model_count}")
                reports.append(
                    {"id": source_id, "name": source.get("name", source_id),
                     "ok": False, "error": f"模型行异常: {model_count}"}
                )
                continue
        elif kind == "free_llm_catalog":
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                util.log(f"源 {source_id} 返回的不是合法 JSON")
                reports.append(
                    {"id": source_id, "name": source.get("name", source_id),
                     "ok": False, "error": "invalid json"}
                )
                continue
            found = free_llm_catalog(payload, url)
            snapshot = _provider_snapshot(found)
            count = len(found)
        elif kind == "free_llm_readme":
            found = free_llm_providers(
                body, url, source.get("homepage") or "https://free-llm.com/"
            )
            snapshot = _provider_snapshot(found)
            count = len(found)
        elif kind in {"openrouter_models", "openai_models", "pollinations_models"}:
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
            found = [provider]
            snapshot = "\n".join(sorted(m["id"] for m in models))
            count = len(models)
        elif kind == "html":
            snapshot = strip_html(body)
            count = len(snapshot.splitlines())
        else:
            snapshot = body
            count = len(normalize_lines(body))

        minimum = _MIN_ITEMS.get(kind)
        if minimum is not None and count < minimum:
            util.log(f"源 {source_id} 内容异常: {count} < {minimum}")
            reports.append(
                {"id": source_id, "name": source.get("name", source_id),
                 "ok": False, "error": f"内容异常: {count} < {minimum}"}
            )
            continue

        diff = update_snapshot(
            source_id, snapshot, snapshot_dir, archive_dir=archive_dir
        )
        if diff.get("anomaly"):
            util.log(
                f"源 {source_id} 内容骤降: {diff['previous_items']} -> {diff['items']}，保留旧快照"
            )
            reports.append(
                {"id": source_id, "name": source.get("name", source_id),
                 "ok": False,
                 "error": f"内容骤降: {diff['previous_items']} -> {diff['items']}"}
            )
            continue

        discovered.extend(found)
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
