from __future__ import annotations

import copy
import re
from pathlib import Path

from . import util

CATEGORY_LABELS = {
    "api": "官方 API 免费层",
    "cloud": "云平台 / 聚合平台",
    "agent": "编程 Agent / CLI / IDE",
    "student": "学生 / 教育福利",
    "chat": "聊天客户端",
    "event": "限时活动 / 羊毛",
    "signin": "每日签到 / 领额度",
    "gpu": "免费算力",
    "gray": "公益中转 / 灰色渠道（不推荐）",
}
VALID_CATEGORIES = set(CATEGORY_LABELS)

FREE_NATURE_LABELS = {
    "permanent": "永久",
    "daily": "每日刷新",
    "monthly": "每月",
    "one_time": "一次性",
    "limited": "限时",
    "student": "学生专属",
    "unknown": "未知",
}

_FREE_NATURE_MAP = {
    "长期免费": "permanent",
    "永久": "permanent",
    "每日刷新": "daily",
    "每日": "daily",
    "每月": "monthly",
    "一次性赠送": "one_time",
    "一次性": "one_time",
    "限时": "limited",
    "学生": "student",
}

_REGION_MAP = {
    "国内": "cn",
    "大陆": "cn",
    "海外": "global",
    "国际": "global",
    "global": "global",
    "cn": "cn",
}


def _norm_access(value) -> dict:
    base = {
        "phone": "unknown",
        "realname": "unknown",
        "card": "unknown",
        "email": "unknown",
        "student": "unknown",
    }
    if isinstance(value, dict):
        for key in ("phone", "realname", "card", "foreign_card", "email", "student"):
            target = "card" if key == "foreign_card" else key
            base[target] = _access_flag(value.get(key))
        return base
    text = str(value or "")
    if not text:
        return base

    def flag(word: str) -> str | None:
        index = text.find(word)
        if index < 0:
            return None
        window = text[max(0, index - 6):index]
        if any(neg in window for neg in ("无需", "不需要", "不需", "免")):
            return "not_required"
        return "required"

    for key, words in (
        ("phone", ("手机号", "手机")),
        ("email", ("邮箱",)),
        ("realname", ("实名",)),
        ("student", ("学生",)),
        ("card", ("外币卡", "信用", "外币")),
    ):
        for word in words:
            result = flag(word)
            if result:
                base[key] = result
                break
    return base


def _access_flag(value) -> str:
    text = str(value or "").strip().lower()
    if text in {"required", "需要", "yes", "true", "required_"}:
        return "required"
    if text in {"not_required", "不需要", "no", "false", "none", "optional"}:
        return "not_required"
    return "unknown"


def _norm_free_nature(value) -> str:
    text = str(value or "").strip()
    if text in FREE_NATURE_LABELS:
        return text
    for key, mapped in _FREE_NATURE_MAP.items():
        if key in text:
            return mapped
    return "unknown"


def _norm_region(value) -> str:
    text = str(value or "").strip()
    return _REGION_MAP.get(text, text if text in {"cn", "global"} else "unknown")


def normalize_limits(raw) -> dict:
    if not isinstance(raw, dict):
        return {"rpm": None, "rpd": None, "tpm": None, "tpd": None}
    return {
        "rpm": util.parse_int(raw.get("rpm")),
        "rpd": util.parse_int(raw.get("rpd")),
        "tpm": util.parse_int(raw.get("tpm")),
        "tpd": util.parse_int(raw.get("tpd")),
    }


def normalize_model(raw) -> dict:
    if isinstance(raw, str):
        raw = {"id": raw}
    model_id = str(raw.get("id") or raw.get("name") or "").strip()
    return {
        "id": model_id,
        "name": raw.get("name") or model_id,
        "context": util.parse_int(raw.get("context")),
        "tools": raw.get("tools"),
        "modalities": list(raw.get("modalities") or ["text"]),
        "note": raw.get("note") or "",
        "status": raw.get("status"),
        "http_status": raw.get("http_status"),
        "latency_ms": raw.get("latency_ms"),
        "checked_at": raw.get("checked_at"),
    }


def normalize_provider(raw: dict) -> dict:
    provider = dict(raw)
    name = str(provider.get("name") or provider.get("id") or "unknown").strip()
    provider["name"] = name
    provider["id"] = util.slugify_id(str(provider.get("id") or name))
    categories = provider.get("categories") or provider.get("category") or ["api"]
    if isinstance(categories, str):
        categories = [categories]
    provider["categories"] = sorted(
        {c for c in categories if c in VALID_CATEGORIES} or {"api"}
    )
    provider["region"] = _norm_region(provider.get("region"))
    provider["base_url"] = str(provider.get("base_url") or "").rstrip("/")
    provider["env"] = str(provider.get("env") or "")
    provider["api_style"] = provider.get("api_style") or (
        "openai" if provider["base_url"] else ""
    )
    provider["keyless"] = bool(provider.get("keyless", False))
    provider["gateway"] = bool(
        provider.get(
            "gateway",
            bool(provider["base_url"] and provider["api_style"] == "openai")
            and (bool(provider["env"]) or provider["keyless"]),
        )
    )
    provider["free_nature"] = _norm_free_nature(provider.get("free_nature"))
    provider["access"] = _norm_access(provider.get("access"))
    provider["limits"] = normalize_limits(provider.get("limits"))
    provider["verified_at"] = str(provider.get("verified_at") or "")
    provider["sources"] = sorted(
        {str(x) for x in (provider.get("sources") or []) if str(x).strip()}
    )
    models = provider.get("models") or []
    if isinstance(models, str):
        models = [{"id": models}]
    provider["models"] = [normalize_model(m) for m in models if m]
    provider.setdefault("headers", {})
    return provider


def _merge_model(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "modalities":
            merged[key] = sorted(set(merged.get(key) or []) | set(value or []))
        elif key == "note":
            merged[key] = merged.get(key) or value
        elif merged.get(key) in (None, "", [], {}) and value not in (None, "", [], {}):
            merged[key] = value
    return merged


def merge_provider(existing: dict, incoming: dict) -> dict:
    merged = dict(existing)
    for key, value in incoming.items():
        if key == "models":
            by_id = {m["id"]: m for m in merged.get("models", []) if m.get("id")}
            for model in value:
                if model["id"] in by_id:
                    by_id[model["id"]] = _merge_model(by_id[model["id"]], model)
                elif model["id"]:
                    by_id[model["id"]] = model
            merged["models"] = list(by_id.values())
        elif key == "categories":
            merged[key] = sorted(set(merged.get(key) or []) | set(value or []))
        elif key == "sources":
            merged[key] = sorted(set(merged.get(key) or []) | set(value or []))
        elif key == "access":
            merged[key] = {
                k: (merged.get(key, {}).get(k, "unknown")
                    if merged.get(key, {}).get(k, "unknown") != "unknown"
                    else v)
                for k, v in value.items()
            }
        elif key == "limits":
            merged[key] = {
                k: (merged.get(key, {}).get(k) or v) for k, v in value.items()
            }
        elif key == "verified_at":
            merged[key] = max(merged.get(key) or "", value or "")
        elif merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def _homepage_key(provider: dict) -> str:
    return str(provider.get("homepage") or "").strip().rstrip("/").lower()


_NAME_ALIASES = {
    "zhipu bigmodel": "zhipu",
    "智谱 ai": "zhipu",
    "z.ai": "zai",
    "z.ai 国际 api": "zai",
    "google ai studio": "gemini",
    "google gemini": "gemini",
    "mistral ai": "mistral",
    "mistral la plateforme": "mistral",
    "deepseek 官方 api": "deepseek",
    "hugging face": "huggingface",
    "huggingface inference providers 免费赠金": "huggingface",
    "qwen": "alibaba",
    "alibaba cloud model studio": "alibaba",
    "阿里云 model studio 国际站": "alibaba",
    "月之暗面 kimi": "moonshot",
    "kimi 开放平台": "moonshot",
}


def _name_key(name: str) -> str:
    text = re.sub(r"\([^)]*\)|（[^）]*）", "", str(name or ""))
    text = re.sub(r"\s+", " ", text).strip().lower()
    return _NAME_ALIASES.get(text, text)


def merge_providers(*groups) -> list[dict]:
    by_id: dict[str, dict] = {}
    base_to_id: dict[str, str] = {}
    home_to_id: dict[str, str] = {}
    name_to_id: dict[str, str] = {}
    order: list[str] = []
    for group in groups:
        for raw in group or []:
            provider = normalize_provider(raw)
            key = provider["id"]
            name_key = _name_key(provider["name"])
            home_key = _homepage_key(provider)
            alias = None
            if provider["base_url"]:
                alias = base_to_id.get(provider["base_url"])
            if not (alias and alias in by_id) and home_key:
                alias = home_to_id.get(home_key)
            if not (alias and alias in by_id):
                alias = name_to_id.get(name_key)
            if alias and alias in by_id:
                key = alias
                provider["id"] = key
            if key in by_id:
                by_id[key] = merge_provider(by_id[key], provider)
            else:
                by_id[key] = provider
                order.append(key)
            if provider["base_url"]:
                base_to_id.setdefault(provider["base_url"], key)
            if home_key:
                home_to_id.setdefault(home_key, key)
            name_to_id.setdefault(name_key, key)
    return [by_id[key] for key in order]


def validate(providers: list[dict]) -> list[str]:
    errors = []
    ids = set()
    for provider in providers:
        pid = provider.get("id")
        if not pid:
            errors.append("provider 缺少 id")
            continue
        if pid in ids:
            errors.append(f"provider id 重复: {pid}")
        ids.add(pid)
        if not provider.get("name"):
            errors.append(f"provider {pid} 缺少 name")
        if provider.get("gateway") and not provider.get("base_url"):
            errors.append(f"provider {pid} 标记为 gateway 但缺少 base_url")
        for model in provider.get("models", []):
            if not model.get("id"):
                errors.append(f"provider {pid} 存在空模型 id")
    return errors


def build_registry(config_path: Path | None = None, output_path: Path | None = None) -> dict:
    config_path = config_path or (util.CONFIG_DIR / "providers.json")
    output_path = output_path or (util.DATA_DIR / "registry.json")
    config = util.read_json(config_path, default={"providers": []})
    raw = config.get("providers", []) if isinstance(config, dict) else config
    providers = merge_providers(raw)
    errors = validate(providers)
    if errors:
        util.log("注册表校验警告:\n  " + "\n  ".join(errors))
    stats = {
        "providers": len(providers),
        "models": sum(len(p.get("models", [])) for p in providers),
        "gateway_providers": sum(1 for p in providers if p.get("gateway")),
        "categories": {
            key: sum(1 for p in providers if key in p.get("categories", []))
            for key in CATEGORY_LABELS
        },
    }
    registry = {
        "schema_version": 1,
        "generated_at": util.now_utc(),
        "stats": stats,
        "providers": providers,
    }
    util.write_json(output_path, registry)
    return registry


def provider_index(registry: dict) -> dict[str, dict]:
    return {p["id"]: p for p in registry.get("providers", [])}


def apply_status(registry: dict, status: dict | None) -> dict:
    result = copy.deepcopy(registry)
    if not status:
        return result
    per_provider = status.get("providers", {})
    for provider in result.get("providers", []):
        entry = per_provider.get(provider["id"])
        if not entry:
            continue
        provider["status"] = entry.get("status")
        provider["checked_at"] = entry.get("checked_at") or status.get("generated_at")
        models = entry.get("models", {})
        for model in provider.get("models", []):
            info = models.get(model["id"])
            if info:
                for key in ("status", "http_status", "latency_ms", "checked_at", "message"):
                    if key in info:
                        model[key] = info[key]
    return result
