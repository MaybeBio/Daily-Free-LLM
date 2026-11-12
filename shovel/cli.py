from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from . import bootstrap as bootstrap_mod
from . import diff, probe, registry as registry_mod, render, sources, util

DEFAULT_SOURCES = {
    "note": "外部发现源。enabled=false 的源不会抓取。",
    "sources": [
        {
            "id": "openrouter-models",
            "name": "OpenRouter 免费模型目录",
            "kind": "openrouter_models",
            "url": "https://openrouter.ai/api/v1/models",
            "enabled": True,
        },
        {
            "id": "pollinations-models",
            "name": "Pollinations 匿名模型目录",
            "kind": "pollinations_models",
            "url": "https://text.pollinations.ai/models",
            "tier": "anonymous",
            "enabled": True,
            "provider": {
                "id": "pollinations",
                "name": "Pollinations (匿名)",
                "base_url": "https://text.pollinations.ai/openai",
                "keyless": True,
                "homepage": "https://pollinations.ai",
                "free_nature": "permanent",
                "notes": "匿名层免 key，直接走 OpenAI 兼容端点；无 SLA，适合原型与轻量使用。",
            },
        },
        {
            "id": "aihorde-models",
            "name": "AI Horde 免 key 模型目录",
            "kind": "openai_models",
            "url": "https://oai.aihorde.net/v1/models",
            "enabled": True,
            "provider": {
                "id": "aihorde",
                "name": "AI Horde",
                "base_url": "https://oai.aihorde.net/v1",
                "keyless": True,
                "homepage": "https://aihorde.net",
                "free_nature": "permanent",
                "probe_max_tokens": 16,
                "notes": "社区众包推理，匿名免 key；排队优先级低，最小生成长度 16 tokens。",
            },
        },
        {
            "id": "freellm-net",
            "name": "freellm.net 免费模型目录",
            "kind": "freellm_net",
            "url": "https://freellm.net/models/",
            "providers_url": "https://freellm.net/providers/",
            "enabled": True,
        },
        {
            "id": "free-llm-com",
            "name": "free-llm.com 渠道目录",
            "kind": "free_llm_readme",
            "url": "https://raw.githubusercontent.com/nejib1/Free-LLM/main/README.md",
            "homepage": "https://free-llm.com/",
            "enabled": True,
        },
        {
            "id": "free-llm-catalog",
            "name": "free-llm.com 官方 JSON 目录",
            "kind": "free_llm_catalog",
            "url": "https://free-llm.com/catalog.json",
            "enabled": True,
        },
    ],
}

DEFAULT_GATEWAY = {
    "note": "本地单用户网关。密钥只从环境变量读取，绝不写入磁盘。",
    "host": "127.0.0.1",
    "port": 8756,
    "default_model": "auto",
    "timeout_seconds": 60,
    "stream_timeout_seconds": 120,
    "cooldown_seconds": 60,
    "max_candidates": 6,
    "auth_token_env": "SHOVEL_TOKEN",
    "verbose": False,
    "priority": [
        "openrouter", "groq", "gemini", "zhipu", "dashscope", "siliconflow",
        "modelscope", "moonshot", "cerebras", "mistral", "together", "nvidia",
        "sambanova", "novita", "nebius", "cloudflare", "hunyuan", "qianfan",
        "volc-ark", "spark", "minimax", "stepfun", "yi", "baichuan", "pollinations",
    ],
}

DEFAULT_ALIASES = {
    "note": "由 bootstrap/update 自动生成；可在 manual 下手写覆盖。",
    "aliases": {},
}


def ensure_configs(force: bool = False) -> None:
    util.ensure_dirs()
    defaults = {
        "providers.json": {
            "schema_version": 1,
            "updated_at": util.now_utc(),
            "note": "唯一事实源。可手动编辑。",
            "providers": [],
        },
        "sources.json": DEFAULT_SOURCES,
        "gateway.json": DEFAULT_GATEWAY,
        "aliases.json": DEFAULT_ALIASES,
    }
    for name, content in defaults.items():
        path = util.CONFIG_DIR / name
        if force or not path.exists():
            util.write_json(path, content)

    sources_path = util.CONFIG_DIR / "sources.json"
    document = util.read_json(sources_path, default={"sources": []})
    known = {item.get("id") for item in document.get("sources", [])}
    added = [s for s in DEFAULT_SOURCES["sources"] if s.get("id") not in known]
    if added:
        document.setdefault("sources", []).extend(added)
        util.write_json(sources_path, document)


def _load_registry() -> dict:
    return registry_mod.build_registry()


def _report(registry: dict, status: dict | None = None) -> dict:
    changes = util.read_jsonl(util.DATA_DIR / "changes.jsonl")[-20:]
    return render.render_all(registry, status, changes)


def cmd_init(args) -> int:
    ensure_configs(force=args.force)
    util.log(f"配置目录: {util.CONFIG_DIR}")
    util.log(f"数据目录: {util.DATA_DIR}")
    return 0


def cmd_bootstrap(args) -> int:
    ensure_configs()
    bootstrap_mod.bootstrap(force=args.force)
    registry = _load_registry()
    if not args.no_report:
        _report(registry)
    util.log(f"注册表: {registry['stats']['providers']} 渠道 / {registry['stats']['models']} 模型")
    return 0


def cmd_update(args) -> int:
    ensure_configs()
    config_path = util.CONFIG_DIR / "providers.json"
    document = util.read_json(config_path, default={"providers": []})
    existing = document.get("providers", [])
    if not existing:
        util.log("注册表为空，先执行 bootstrap 播种。")
        bootstrap_mod.bootstrap()
        document = util.read_json(config_path, default={"providers": []})
        existing = document.get("providers", [])

    registry = _load_registry()
    discovered, changes, reports = sources.update_external(
        registry, timeout=args.timeout
    )
    if discovered:
        merged = registry_mod.merge_providers(existing, discovered)
        util.write_json(
            config_path,
            {
                "schema_version": 1,
                "updated_at": util.now_utc(),
                "note": document.get("note", ""),
                "providers": merged,
            },
        )
        bootstrap_mod.write_aliases(merged)
    registry = _load_registry()

    util.write_json(
        util.DAILY_DIR / util.today_iso() / "summary.json",
        {
            "date": util.today_iso(),
            "generated_at": util.now_utc(),
            "registry": registry.get("stats", {}),
            "sources": reports,
            "changes": changes,
        },
    )

    diff.append_history(
        util.DATA_DIR / "history.jsonl",
        {
            "at": util.now_cst(),
            "providers": registry["stats"]["providers"],
            "models": registry["stats"]["models"],
            "sources": reports,
            "changes": [
                {"source": c["source"], "added": c["added_count"], "removed": c["removed_count"]}
                for c in changes
            ],
        },
    )
    for report in reports:
        if report.get("ok"):
            util.log(
                f"{report['name']}: {report.get('items', 0)} 条"
                + ("（基线）" if report.get("baseline") else
                   f"，+{report.get('added', 0)} / -{report.get('removed', 0)}")
            )
        else:
            util.log(f"{report['name']}: 失败 {report.get('error')}")
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::warning::{report['name']}: {report.get('error')}")
    if not args.no_report:
        _report(registry)
    return 0


def cmd_probe(args) -> int:
    ensure_configs()
    registry = _load_registry()
    only = [item.strip() for item in (args.only or "").split(",") if item.strip()] or None
    if not only:
        available = [
            p for p in registry.get("providers", [])
            if p.get("gateway") and (p.get("keyless") or os.environ.get(p.get("env", "")))
        ]
        if not available:
            util.log(
                "没有可用密钥。可先 `python -m shovel probe --only pollinations` "
                "验证免 key 端点，或填写 .env 后再探。"
            )
    status = probe.run_probe(
        registry,
        only=only,
        timeout=args.timeout,
        workers=args.workers,
        tools=args.tools,
    )
    util.log(f"探活摘要: {status.get('summary')}")
    if not args.no_report:
        _report(registry, status)
    return 0


def cmd_report(args) -> int:
    ensure_configs()
    registry = _load_registry()
    status = util.read_json(util.DATA_DIR / "status.json", default=None)
    result = _report(registry, status)
    util.log(f"README: {result['readme']}")
    util.log(f"CSV: {result['csv']}")
    util.log(f"面板: {result['site']}")
    return 0


def cmd_serve(args) -> int:
    ensure_configs()
    from .gateway.server import App, run_server

    registry = _load_registry()
    status = util.read_json(util.DATA_DIR / "status.json", default=None)
    aliases = util.read_json(util.CONFIG_DIR / "aliases.json", default={})
    config = util.read_json(util.CONFIG_DIR / "gateway.json", default=DEFAULT_GATEWAY)
    if not (util.SITE_DIR / "index.html").exists():
        render.render_all(registry, status, util.read_jsonl(util.DATA_DIR / "changes.jsonl")[-20:])
    if args.host:
        config["host"] = args.host
    if args.port:
        config["port"] = args.port
    app = App(registry, status, aliases, config, util.SITE_DIR)
    run_server(app)
    return 0


def cmd_doctor(args) -> int:
    ensure_configs()
    registry = _load_registry()
    stats = registry.get("stats", {})
    util.log(f"渠道 {stats.get('providers', 0)} / 模型 {stats.get('models', 0)} / "
             f"可网关 {stats.get('gateway_providers', 0)}")

    gateways = [p for p in registry.get("providers", []) if p.get("gateway")]
    if not gateways:
        util.log("警告: 没有可网关渠道，请先 bootstrap。")
    for provider in gateways:
        env = provider.get("env") or ""
        ready = bool(provider.get("keyless")) or bool(os.environ.get(env))
        util.log(
            f"  {'OK ' if ready else 'MISS'} {provider['name']:32} "
            f"{env or '(keyless)':24} {provider.get('base_url', '')}"
        )

    status_path = util.DATA_DIR / "status.json"
    if status_path.exists():
        age = datetime.now() - datetime.fromtimestamp(status_path.stat().st_mtime)
        util.log(f"status.json 年龄: {age.total_seconds() / 3600:.1f} 小时")
        if age.total_seconds() > 48 * 3600:
            util.log("提示: 状态超过 48 小时未更新，建议运行 probe。")
    else:
        util.log("status.json 不存在（尚未探活）。")

    if not util.REFS_DIR.exists():
        util.log("提示: refers_template/ 不存在，bootstrap 只能使用已固化的 config/providers.json。")

    if args.network:
        config = util.read_json(util.CONFIG_DIR / "sources.json", default={"sources": []})
        for source in config.get("sources", []):
            if not source.get("enabled", True):
                continue
            code, _, _ = util.http_request("GET", source.get("url", ""), timeout=args.timeout)
            util.log(f"  源 {source.get('id')}: HTTP {code}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shovel",
        description="免费 LLM API：追踪、探活、统一 OpenAI 兼容网关。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="创建配置与数据目录")
    init.add_argument("--force", action="store_true", help="覆盖默认配置")
    init.set_defaults(func=cmd_init)

    boot = sub.add_parser("bootstrap", help="从 refers_template 播种注册表")
    boot.add_argument("--force", action="store_true", help="重建注册表（丢弃已有非空字段）")
    boot.add_argument("--no-report", action="store_true")
    boot.set_defaults(func=cmd_bootstrap)

    update = sub.add_parser("update", help="抓外部源、差异追踪并更新目录")
    update.add_argument("--timeout", type=float, default=20.0)
    update.add_argument("--no-report", action="store_true")
    update.set_defaults(func=cmd_update)

    probe_cmd = sub.add_parser("probe", help="探活已配置密钥的模型")
    probe_cmd.add_argument("--only", default="", help="逗号分隔的 provider id / env")
    probe_cmd.add_argument("--timeout", type=float, default=15.0)
    probe_cmd.add_argument("--workers", type=int, default=8)
    probe_cmd.add_argument("--tools", action="store_true", help="额外探测工具调用")
    probe_cmd.add_argument("--no-report", action="store_true")
    probe_cmd.set_defaults(func=cmd_probe)

    report = sub.add_parser("report", help="生成 README / CSV / 面板 / RSS")
    report.set_defaults(func=cmd_report)

    serve = sub.add_parser("serve", help="启动统一网关与本地面板")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.set_defaults(func=cmd_serve)

    doctor = sub.add_parser("doctor", help="检查配置、密钥与状态")
    doctor.add_argument("--network", action="store_true", help="额外检查外部源可达性")
    doctor.add_argument("--timeout", type=float, default=10.0)
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    sys.setrecursionlimit(10000)
    util.load_env_file()
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
