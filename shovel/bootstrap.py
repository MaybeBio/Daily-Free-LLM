from __future__ import annotations

import csv
import re
from pathlib import Path

from . import util
from .registry import merge_providers, normalize_limits

CN_ENVS = {
    "ZHIPU_KEY", "MOONSHOT_KEY", "DASHSCOPE_KEY", "SILICONFLOW_KEY", "MODELSCOPE_KEY",
    "HUNYUAN_KEY", "QIANFAN_KEY", "VOLC_ARK_KEY", "SPARK_KEY", "MINIMAX_KEY",
    "STEPFUN_KEY", "YI_KEY", "BAICHUAN_KEY", "DEEPSEEK_KEY",
}
CN_BASE_MARKERS = (
    "bigmodel", "moonshot", "aliyuncs", "siliconflow", "modelscope", "hunyuan",
    "baidubce", "volces", "xf-yun", "minimax", "stepfun", "lingyiwanwu", "baichuan",
)

TRACKER_CATEGORY_MAP = {
    "官方 API 免费层": "api",
    "云平台": "cloud",
    "编程 Agent": "agent",
    "学生": "student",
    "聊天客户端": "chat",
    "限时活动": "event",
    "每日签到": "signin",
    "免费算力": "gpu",
    "公益中转": "gray",
    "灰色渠道": "gray",
}

# 这些渠道在 free-llm-api-list/providers.json 里已有更细的 API 级登记，避免重复。
TRACKER_API_DUPLICATES = (
    "智谱开放平台 bigmodel", "月之暗面 Kimi", "阿里云百炼", "硅基流动",
    "魔搭 ModelScope", "腾讯混元", "百度千帆", "火山方舟", "MiniMax",
    "阶跃星辰", "零一万物", "百川智能", "OpenRouter", "Groq", "Google Gemini",
    "Cerebras", "Mistral", "Together", "NVIDIA NIM", "SambaNova", "Nebius",
    "Novita", "Cloudflare", "讯飞星火",
)

FAMILY_PATTERNS = (
    ("gpt-oss", r"gpt[-_]oss"),
    ("deepseek", r"deepseek"),
    ("qwen", r"qwen"),
    ("kimi", r"kimi|moonshot"),
    ("glm", r"glm|zhipu|z-ai"),
    ("gemini", r"gemini"),
    ("claude", r"claude"),
    ("llama", r"llama|meta-"),
    ("mistral", r"mistral|mixtral"),
    ("minimax", r"minimax"),
    ("step", r"step-|stepfun"),
    ("hunyuan", r"hunyuan|hy\d"),
    ("ernie", r"ernie"),
    ("nemotron", r"nemotron"),
    ("nova", r"nova"),
    ("command", r"command"),
    ("phi", r"phi-"),
    ("gemma", r"gemma"),
)


def _id_from_env(env: str, name: str) -> str:
    value = env.strip().upper()
    for suffix in ("_API_TOKEN", "_API_KEY", "_TOKEN", "_KEY"):
        if value.endswith(suffix):
            value = value[: -len(suffix)]
            break
    return util.slugify_id(value.replace("_", "-") if value else name)


def _region_for(env: str, base_url: str) -> str:
    if env in CN_ENVS or any(marker in base_url for marker in CN_BASE_MARKERS):
        return "cn"
    return "global"


def _short(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s；;，,）)】\]]+", str(text or ""))
    return [url.rstrip("。.；;，,") for url in urls]


def _from_api_list() -> list[dict]:
    path = util.REFS_DIR / "free-llm-api-list" / "providers.json"
    if not path.exists():
        return []
    data = util.read_json(path, default={})
    providers = []
    for raw in data.get("providers", []):
        policy = raw.get("policy", {}) or {}
        signup = policy.get("signup", {}) or {}
        limits = policy.get("limits", {}) or {}
        base_url = str(raw.get("base_url") or "")
        env = str(raw.get("env") or "")
        models = [
            {
                "id": m.get("id"),
                "context": m.get("context"),
                "note": m.get("note") or "",
                "modalities": ["text"],
            }
            for m in raw.get("models", [])
            if m.get("id")
        ]
        providers.append(
            {
                "id": _id_from_env(env, raw.get("name", "")),
                "name": raw.get("name"),
                "env": env,
                "base_url": base_url,
                "key_url": raw.get("console") or "",
                "homepage": raw.get("console") or base_url,
                "categories": ["api"],
                "region": _region_for(env, base_url),
                "free_nature": policy.get("free_kind") or "unknown",
                "limits": normalize_limits(limits),
                "access": {
                    "phone": signup.get("phone", "unknown"),
                    "realname": signup.get("realname", "unknown"),
                    "foreign_card": signup.get("foreign_card", "unknown"),
                },
                "verified_at": policy.get("verified_at") or "",
                "confidence": policy.get("confidence") or "",
                "sources": policy.get("sources") or [],
                "notes": _short((policy.get("access") or {}).get("difficulty_reason", "")),
                "policy": policy,
                "requires": raw.get("requires") or [],
                "api_style": "openai",
                "gateway": True,
                "models": models,
            }
        )
    return providers


def _tracker_category(label: str) -> str:
    for key, value in TRACKER_CATEGORY_MAP.items():
        if key in label:
            return value
    return "cloud"


def _is_tracker_api_duplicate(channel: str) -> bool:
    return any(token in channel for token in TRACKER_API_DUPLICATES)


def _from_tracker_csv() -> list[dict]:
    path = util.REFS_DIR / "free-llm-tracker" / "免费渠道种子表.csv"
    if not path.exists():
        return []
    providers = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            channel = (row.get("渠道") or "").strip()
            if not channel:
                continue
            category = _tracker_category(row.get("分类") or "")
            if category == "api" and _is_tracker_api_duplicate(channel):
                continue
            sources = _extract_urls(row.get("来源链接") or "")
            providers.append(
                {
                    "id": util.slugify_id(channel),
                    "name": channel,
                    "provider_company": row.get("提供方") or "",
                    "categories": [category],
                    "region": row.get("地区") or "unknown",
                    "free_nature": row.get("额度性质") or "unknown",
                    "access": row.get("准入门槛") or "",
                    "verified_at": row.get("核实日期") or "",
                    "confidence": row.get("可信度") or "",
                    "sources": sources,
                    "homepage": sources[0] if sources else "",
                    "notes": row.get("免费内容") or "",
                    "representative_models": row.get("代表模型") or "",
                    "limits_text": row.get("限额") or "",
                    "usage": row.get("使用方式") or "",
                    "expiry": row.get("到期时间") or "",
                    "risk": row.get("风险备注") or "",
                    "gateway": False,
                    "models": [],
                }
            )
    return providers


def _from_free_llm_readme() -> list[dict]:
    path = util.REFS_DIR / "Free-LLM" / "README.md"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    providers = []
    row_re = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.+)\|\s*$")
    in_section = False
    for line in lines:
        if line.startswith("## "):
            in_section = "Provider Directory" in line
            continue
        if not in_section:
            continue
        match = row_re.match(line)
        if not match:
            continue
        name, url, rest = match.group(1).strip(), match.group(2).strip(), match.group(3)
        cells = [cell.strip() for cell in rest.split("|")]
        if len(cells) < 5:
            continue
        providers.append(
            {
                "id": util.slugify_id(name),
                "name": name,
                "homepage": url,
                "categories": ["api"],
                "region": "global",
                "access": cells[0],
                "limits_text": f"RPM: {cells[1]}; RPD: {cells[2]}",
                "notes": f"额度性质: {cells[3]}",
                "representative_models": cells[4],
                "sources": [url],
                "gateway": False,
                "models": [],
            }
        )
    return providers


def _from_awesome_readme() -> list[dict]:
    path = util.REFS_DIR / "awesome-freellm-apis" / "README.md"
    if not path.exists():
        return []
    providers = []
    row_re = re.compile(
        r"^\| ([^|]+) \| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|.*href=\"([^\"]+)\""
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = row_re.match(line)
        if not match:
            continue
        name, count, access, context, modality, url = (g.strip() for g in match.groups())
        providers.append(
            {
                "id": util.slugify_id(name),
                "name": name,
                "homepage": url,
                "categories": ["api"],
                "region": "global",
                "access": access,
                "notes": f"{count} 个模型，最大上下文 {context}，{modality}",
                "sources": [url],
                "gateway": False,
                "models": [],
            }
        )
    return providers


def _keyless_providers() -> list[dict]:
    return [
        {
            "id": "pollinations",
            "name": "Pollinations (匿名)",
            "homepage": "https://pollinations.ai",
            "base_url": "https://text.pollinations.ai/openai",
            "env": "",
            "keyless": True,
            "categories": ["api"],
            "region": "global",
            "free_nature": "permanent",
            "verified_at": util.today_iso(),
            "sources": ["https://text.pollinations.ai/models"],
            "notes": "匿名层免 key，直接走 OpenAI 兼容端点；无 SLA，适合原型与轻量使用。",
            "gateway": True,
            "models": [
                {"id": "openai-fast", "note": "GPT-OSS 20B 推理模型（OVH）"},
                {"id": "openai", "note": "openai-fast 的别名"},
            ],
        },
        {
            "id": "aihorde",
            "name": "AI Horde",
            "homepage": "https://aihorde.net",
            "base_url": "https://oai.aihorde.net/v1",
            "env": "",
            "keyless": True,
            "probe_max_tokens": 16,
            "categories": ["api"],
            "region": "global",
            "free_nature": "permanent",
            "verified_at": util.today_iso(),
            "sources": ["https://oai.aihorde.net/v1/models"],
            "notes": "社区众包推理，匿名免 key；排队优先级低，最小生成长度 16 tokens。",
            "gateway": True,
            "models": [
                {"id": "koboldcpp/Llama-3.2-1B-Instruct", "context": 12288},
                {"id": "koboldcpp/gemma-4-31B-it", "context": 32768},
            ],
        },
    ]


def family_of(model_id: str) -> str | None:
    lowered = model_id.lower()
    for family, pattern in FAMILY_PATTERNS:
        if re.search(pattern, lowered):
            return family
    return None


def build_aliases(providers: list[dict]) -> dict[str, list[dict]]:
    aliases: dict[str, list[dict]] = {}
    for provider in providers:
        if not provider.get("gateway"):
            continue
        for model in provider.get("models", []):
            family = family_of(model.get("id", ""))
            if not family:
                continue
            aliases.setdefault(family, []).append(
                {"provider": provider["id"], "model": model["id"]}
            )
    for value in aliases.values():
        value.sort(key=lambda item: (item["provider"], item["model"]))
    return aliases


def write_aliases(providers: list[dict], path: Path | None = None, force: bool = False) -> dict:
    path = path or (util.CONFIG_DIR / "aliases.json")
    generated = build_aliases(providers)
    existing = util.read_json(path, default={}) if path.exists() and not force else {}
    manual = existing.get("manual") if isinstance(existing, dict) else None
    document = {
        "generated_at": util.now_utc(),
        "note": "aliases 由 bootstrap 生成并随更新刷新；manual 中的同名别名优先。",
        "aliases": generated,
    }
    if manual:
        document["manual"] = manual
    util.write_json(path, document)
    return document


def bootstrap(
    force: bool = False,
    config_path: Path | None = None,
    aliases_path: Path | None = None,
) -> dict:
    config_path = config_path or (util.CONFIG_DIR / "providers.json")
    existing_doc = util.read_json(config_path, default={})
    existing = existing_doc.get("providers", []) if isinstance(existing_doc, dict) else existing_doc
    seeded = (
        _keyless_providers()
        + _from_api_list()
        + _from_tracker_csv()
        + _from_free_llm_readme()
        + _from_awesome_readme()
    )
    if force:
        providers = merge_providers(seeded)
    else:
        providers = merge_providers(existing, seeded)
    document = {
        "schema_version": 1,
        "updated_at": util.now_utc(),
        "note": "唯一事实源。可手动编辑；bootstrap 只补缺，不覆盖已有非空字段（--force 除外）。",
        "providers": providers,
    }
    util.write_json(config_path, document)
    aliases = write_aliases(providers, path=aliases_path, force=force)
    util.log(
        f"播种完成: {len(providers)} 个渠道, "
        f"{sum(len(p.get('models', [])) for p in providers)} 个模型, "
        f"{len(aliases['aliases'])} 个模型家族别名"
    )
    return document
