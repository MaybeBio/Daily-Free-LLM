from __future__ import annotations

import csv
import html
import io
import json
import re
import subprocess
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from . import util
from .probe import STATUS_LABELS
from .registry import (
    CATEGORY_LABELS,
    FREE_NATURE_LABELS,
    apply_status,
)


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def primary_category(provider: dict) -> str:
    for key in CATEGORY_LABELS:
        if key in provider.get("categories", []):
            return key
    return "api"


def status_of(provider: dict) -> str:
    return provider.get("status") or "untested"


def status_label(provider_or_status) -> str:
    status = status_of(provider_or_status) if isinstance(provider_or_status, dict) else provider_or_status
    return STATUS_LABELS.get(status, "⚪ 未测")


_STATUS_SHORT = {
    "ok": "✅ 可用",
    "rate_limited": "⚠️ 限流",
    "auth_error": "🔑 鉴权",
    "not_found": "❌ 下架",
    "bad_request": "🟠 拒绝",
    "server_error": "🌐 异常",
    "network_error": "📡 断网",
    "skipped": "⏭️ 跳过",
    "error": "❓ 错误",
}


def short_status(provider: dict) -> str:
    return _STATUS_SHORT.get(status_of(provider), "⚪ 未测")


def pages_url() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(util.ROOT), "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", result.stdout.strip())
    if not match:
        return None
    owner, repo = match.groups()
    return f"https://{owner.lower()}.github.io/{repo}/"


def model_text(provider: dict) -> str:
    models = provider.get("models") or []
    if models:
        ids = [m["id"] for m in models]
        if len(ids) <= 4:
            return "、".join(ids)
        return "、".join(ids[:4]) + f" 等 {len(ids)} 款"
    return provider.get("representative_models") or provider.get("notes") or "—"


def limit_text(provider: dict) -> str:
    limits = provider.get("limits") or {}
    parts = []
    for key, label in (("rpm", "RPM"), ("rpd", "RPD"), ("tpm", "TPM"), ("tpd", "TPD")):
        if limits.get(key):
            parts.append(f"{label} {limits[key]}")
    return " / ".join(parts) or provider.get("limits_text") or "未公布"


def access_text(provider: dict) -> str:
    access = provider.get("access") or {}
    parts = []
    for key, label in (
        ("phone", "手机号"), ("email", "邮箱"), ("realname", "实名"),
        ("student", "学生认证"), ("card", "外币卡"),
    ):
        if access.get(key) == "required":
            parts.append(label)
    return "、".join(parts) or "未知"


def _source_links(provider: dict, limit: int = 3) -> str:
    links = provider.get("sources") or []
    if not links:
        return "—"
    pieces = []
    for url in links[:limit]:
        pieces.append(f'<a href="{esc(url)}">{esc(url)}</a>')
    if len(links) > limit:
        pieces.append(f"+{len(links) - limit}")
    return " ".join(pieces)


def _compacted(registry: dict) -> list[dict]:
    providers = []
    for provider in registry.get("providers", []):
        providers.append(
            {
                "id": provider["id"],
                "name": provider.get("name", ""),
                "company": provider.get("provider_company", ""),
                "categories": provider.get("categories", []),
                "category": primary_category(provider),
                "category_label": CATEGORY_LABELS.get(primary_category(provider), ""),
                "region": provider.get("region", "unknown"),
                "free_nature": provider.get("free_nature", "unknown"),
                "free_nature_label": FREE_NATURE_LABELS.get(
                    provider.get("free_nature", "unknown"), "未知"
                ),
                "env": provider.get("env", ""),
                "base_url": provider.get("base_url", ""),
                "keyless": bool(provider.get("keyless")),
                "gateway": bool(provider.get("gateway")),
                "access": access_text(provider),
                "limits": limit_text(provider),
                "models": [m["id"] for m in provider.get("models", [])],
                "model_text": model_text(provider),
                "model_count": len(provider.get("models", [])),
                "representative_models": provider.get("representative_models", ""),
                "usage": provider.get("usage", ""),
                "expiry": provider.get("expiry", ""),
                "risk": provider.get("risk", ""),
                "confidence": provider.get("confidence", ""),
                "verified_at": provider.get("verified_at", ""),
                "status": status_of(provider),
                "status_label": status_label(provider),
                "checked_at": provider.get("checked_at", ""),
                "notes": provider.get("notes", ""),
                "key_url": provider.get("key_url", ""),
                "homepage": provider.get("homepage", ""),
                "sources": provider.get("sources", []),
            }
        )
    return providers


def render_readme(
    registry: dict,
    status: dict | None,
    changes: list[dict] | None,
    path: Path | None = None,
) -> str:
    path = path or (util.ROOT / "README.md")
    badge_specs = [
        ("Python 3.10+", "Python-3.10%2B-3776AB?logo=python&logoColor=white"),
        ("dependencies: 0", "dependencies-0-34d399"),
        ("OpenAI compatible", "API-OpenAI%20compatible-10a37f?logo=openai&logoColor=white"),
    ]
    panel = pages_url()
    panel_badge = (
        f'<a href="{panel}"><img alt="panel: live" '
        'src="https://img.shields.io/badge/panel-live-5eead4?style=flat-square"></a>'
        if panel else ""
    )
    badges = " ".join(
        filter(None, [panel_badge] + [
            f'<img alt="{alt}" src="https://img.shields.io/badge/{path}'
            f'{"&" if "?" in path else "?"}style=flat-square">'
            for alt, path in badge_specs
        ])
    )
    lines = [
        '<h1 align="center">⛏️ 免费 LLM API</h1>',
        "",
        '<p align="center">收集、探活、追踪免费 LLM API，聚合成一个本地 OpenAI 兼容端点。</p>',
        "",
        f'<p align="center">{badges}</p>',
        "",
        '<p align="center"><code>free-llm</code> · <code>openai-api</code> · '
        '<code>gateway</code> · <code>zero-dependency</code> · <code>self-hosted</code></p>',
        "",
        "## 快速开始",
        "",
        "```bash",
        "python -m shovel update    # 抓取公开源并做差异追踪",
        "python -m shovel probe     # 探活已配置 key + 免 key 渠道",
        "python -m shovel serve     # 网关和面板都在 127.0.0.1:8756",
        "```",
        "",
        "- 网关：`http://127.0.0.1:8756/v1`（OpenAI 兼容）",
        (
            f"- 面板：[在线]({panel}) / [本地](http://127.0.0.1:8756/)"
            if panel else "- 面板：`http://127.0.0.1:8756/`"
        ),
        "- 密钥只从环境变量读取，参考 `.env.example`",
        "",
        "没有 key 也能先用：Pollinations `https://text.pollinations.ai/openai`，"
        "AI Horde `https://oai.aihorde.net/v1`。",
        "",
        "## 客户端",
        "",
        "base URL 填 `http://127.0.0.1:8756/v1`，API key 任意填（设了 `SHOVEL_TOKEN` 就填它）。"
        "model 可用 `auto`、家族别名（如 `qwen`）、精确模型名，或 `provider/model`。",
        "",
        "```bash",
        "curl http://127.0.0.1:8756/v1/chat/completions \\",
        "  -H 'Content-Type: application/json' \\",
        "  -d '{\"model\":\"auto\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":16}'",
        "```",
        "",
        "其他命令：`report` 重建 README/CSV/面板，`doctor` 检查配置，"
        "`bootstrap` 补种目录，`python -m unittest discover -s tests` 跑测试。",
        "",
    ]
    lines += [
        "## 数据在哪",
        "",
        (
            f"- [在线面板]({panel})：搜索、筛选、实时状态"
            if panel else "- 面板：`http://127.0.0.1:8756/`（本地运行 `serve`）"
        ),
        "- [完整注册表](config/providers.json)：合并后的渠道与模型数据",
        "- [每日归档](data/daily/)：每天一个目录，含 `summary.json` 和当日各源快照",
        "- [最新快照](data/snapshots/)：每个源最近一次快照，供下一次 diff 使用",
        "- [变更记录](data/changes.jsonl) / [历史统计](data/history.jsonl)",
        "- `free_llm_api.csv`：扁平表，适合 Excel 或脚本处理",
        "- [RSS](site/feed.xml)：新增/移除订阅",
        "",
        "## 说明",
        "",
        "- README 只做入口，不记录具体渠道数据；数据以面板和上面仓库内的文件为准。",
        "- `verified_at` 按渠道记录，没有全表统一的核实日期。",
        "- 灰色渠道只做风险记录，不进入网关。",
        "- `config/providers.json` 是唯一事实源；README、CSV、面板、RSS 都由 `report` 重建。",
        "",
        "<sub>由 `report` 自动生成。</sub>",
        "",
    ]

    text = "\n".join(lines) + "\n"
    util.atomic_write(path, text)
    return text


def render_csv(
    registry: dict,
    status: dict | None,
    path: Path | None = None,
) -> str:
    path = path or (util.ROOT / "free_llm_api.csv")
    data = apply_status(registry, status)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([
        "分类", "渠道", "提供方", "地区", "免费性质", "密钥变量", "BaseURL",
        "模型数", "代表模型", "限额", "使用方式", "到期", "准入门槛", "状态",
        "核实日期", "来源链接", "备注",
    ])
    for provider in data.get("providers", []):
        writer.writerow([
            CATEGORY_LABELS.get(primary_category(provider), ""),
            provider.get("name", ""),
            provider.get("provider_company", ""),
            provider.get("region", ""),
            FREE_NATURE_LABELS.get(provider.get("free_nature", "unknown"), "未知"),
            provider.get("env", ""),
            provider.get("base_url", ""),
            len(provider.get("models", [])),
            model_text(provider),
            limit_text(provider),
            provider.get("usage", ""),
            provider.get("expiry", ""),
            access_text(provider),
            status_label(provider),
            provider.get("verified_at", ""),
            "；".join(provider.get("sources", [])),
            provider.get("notes", ""),
        ])
    text = buffer.getvalue()
    util.atomic_write(path, text)
    return text


def _payload(registry: dict, status: dict | None, changes: list[dict] | None) -> dict:
    data = apply_status(registry, status)
    return {
        "generated_at": util.now_cst(),
        "generated_at_utc": util.now_utc(),
        "stats": data.get("stats", {}),
        "categories": CATEGORY_LABELS,
        "providers": _compacted(data),
        "changes": (changes or [])[-20:],
        "status_summary": (status or {}).get("summary", {}),
    }


_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>免费 LLM API</title>
<style>
:root{
  --bg:#0b1020;--panel:#121a33;--panel2:#0f1730;--line:#22304f;
  --text:#e8eefc;--muted:#8fa0bf;--acc:#5eead4;--acc2:#fbbf24;
  --ok:#34d399;--warn:#fbbf24;--bad:#f87171;--dim:#64748b;
}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 10% -10%,#1a2a55 0,transparent 55%),
radial-gradient(900px 500px at 100% 0,#132347 0,transparent 50%),var(--bg);
color:var(--text);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:28px 18px 60px}
header{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;justify-content:space-between}
h1{font-size:30px;margin:0;letter-spacing:.5px}
h1 span{color:var(--acc)}
.sub{color:var(--muted);margin-top:6px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}
.stat{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
border-radius:14px;padding:14px 16px}
.stat b{display:block;font-size:24px;color:var(--acc)}
.stat small{color:var(--muted)}
.toolbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:18px 0}
input,select{background:#0c142b;color:var(--text);border:1px solid var(--line);
border-radius:10px;padding:9px 12px;font:inherit;outline:none}
input{flex:1 1 260px;min-width:200px}
input:focus,select:focus{border-color:#3b6ea5}
.tabs{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 18px}
.tab{cursor:pointer;border:1px solid var(--line);background:#0d1530;color:var(--muted);
padding:7px 12px;border-radius:999px;font-size:13px;user-select:none}
.tab.on{background:rgba(94,234,212,.12);border-color:#2f8f83;color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:10px;
transition:transform .15s,border-color .15s}
.card:hover{transform:translateY(-2px);border-color:#34507d}
.card h3{margin:0;font-size:17px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);
color:var(--muted);white-space:nowrap}
.b-ok{color:var(--ok);border-color:rgba(52,211,153,.4);background:rgba(52,211,153,.08)}
.b-warn{color:var(--warn);border-color:rgba(251,191,36,.4);background:rgba(251,191,36,.08)}
.b-bad{color:var(--bad);border-color:rgba(248,113,113,.4);background:rgba(248,113,113,.08)}
.b-dim{color:var(--dim)}
.meta{color:var(--muted);font-size:13px;display:flex;flex-wrap:wrap;gap:10px}
.kv{display:grid;grid-template-columns:76px 1fr;gap:4px 10px;font-size:13px}
.kv dt{color:var(--muted)}
.kv dd{margin:0;overflow-wrap:anywhere}
code{background:#0a1229;border:1px solid var(--line);padding:1px 6px;border-radius:6px;font-size:12px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
button{cursor:pointer;background:#12204a;color:var(--text);border:1px solid var(--line);
border-radius:9px;padding:6px 10px;font:inherit;font-size:12px}
button:hover{border-color:#3b6ea5}
.links a{color:#7dd3fc;font-size:12px;text-decoration:none}
.links a:hover{text-decoration:underline}
.empty{color:var(--muted);padding:30px;text-align:center;border:1px dashed var(--line);border-radius:14px}
footer{margin-top:36px;color:var(--muted);font-size:12px}
.changes{margin-top:26px;border-top:1px solid var(--line);padding-top:18px}
.changes h2{font-size:18px;margin:0 0 10px}
.changes ul{margin:0;padding-left:18px;color:var(--muted)}
#toast{position:fixed;right:18px;bottom:18px;background:#132347;border:1px solid #2f8f83;
color:var(--acc);padding:10px 14px;border-radius:10px;opacity:0;transition:opacity .2s;
pointer-events:none}
#toast.on{opacity:1}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>免费 LLM <span>API</span></h1>
    <div class="sub" id="sub"></div>
  </div>
  <div class="sub" id="gen"></div>
</header>
<div class="stats" id="stats"></div>
<div class="toolbar">
  <input id="q" placeholder="搜索渠道 / 提供方 / 模型 / 备注…">
  <select id="region"><option value="all">全部地区</option><option value="cn">国内</option>
    <option value="global">海外</option><option value="unknown">未知</option></select>
  <select id="status"><option value="all">全部状态</option><option value="ok">正常</option>
    <option value="limited">限流/额度</option><option value="untested">未测</option>
    <option value="bad">异常</option></select>
</div>
<div class="tabs" id="tabs"></div>
<div class="grid" id="grid"></div>
<div class="changes"><h2>最近变更</h2><ul id="changes"></ul></div>
<footer>数据来自 config/providers.json 与 data/status.json；由 python -m shovel report 生成。
灰色渠道仅记录风险，不进入网关。</footer>
</div>
<div id="toast"></div>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const P = JSON.parse(document.getElementById('payload').textContent);
const CAT = P.categories, D = P.providers;
const $ = (x) => document.querySelector(x);
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const S = {q:'', cat:'all', region:'all', status:'all'};
function toast(msg){const t=$('#toast');t.textContent=msg;t.classList.add('on');
  clearTimeout(t._i);t._i=setTimeout(()=>t.classList.remove('on'),1400)}
async function copy(text){try{await navigator.clipboard.writeText(text);toast('已复制')}
  catch(e){toast('复制失败：'+e.message)}}
function statusClass(s){
  if(s==='ok') return 'b-ok';
  if(s==='rate_limited'||s==='bad_request') return 'b-warn';
  if(s==='untested') return 'b-dim';
  return 'b-bad';
}
function statusGroup(s){
  if(s==='ok') return 'ok';
  if(s==='rate_limited'||s==='bad_request') return 'limited';
  if(s==='untested') return 'untested';
  return 'bad';
}
function matches(p){
  if(S.cat!=='all' && p.category!==S.cat && !p.categories.includes(S.cat)) return false;
  if(S.region!=='all' && p.region!==S.region) return false;
  if(S.status!=='all' && statusGroup(p.status)!==S.status) return false;
  if(!S.q) return true;
  const hay = [p.name,p.company,p.model_text,p.notes,p.usage,p.env,p.base_url,
    p.representative_models].join(' ').toLowerCase();
  return S.q.toLowerCase().split(/\\s+/).filter(Boolean).every(t=>hay.includes(t));
}
function snippet(p){
  return `# ${p.name}\\nexport OPENAI_BASE_URL=http://127.0.0.1:8756/v1\\n` +
    `export OPENAI_API_KEY=local\\n# model: ${(p.models[0]||'auto')}\\n` +
    (p.env ? `# upstream env: ${p.env}\\n` : '');
}
function card(p){
  const links = (p.sources||[]).slice(0,3).map(u=>
    `<a href="${esc(u)}" target="_blank" rel="noopener">来源</a>`).join(' ');
  const keyLink = p.key_url ? `<a href="${esc(p.key_url)}" target="_blank" rel="noopener">拿 key</a>` : '';
  return `<article class="card">
    <h3>${esc(p.name)}
      <span class="badge ${statusClass(p.status)}">${esc(p.status_label)}</span>
      ${p.gateway?'<span class="badge b-ok">可网关</span>':''}
      ${p.keyless?'<span class="badge">免 key</span>':''}
    </h3>
    <div class="meta">
      <span>${esc(p.category_label)}</span>
      <span>${p.region==='cn'?'国内':'海外'}</span>
      <span>${esc(p.free_nature_label)}</span>
      ${p.verified_at?`<span>核实 ${esc(p.verified_at)}</span>`:''}
    </div>
    <dl class="kv">
      <dt>模型</dt><dd>${esc(p.model_text)}</dd>
      <dt>限额</dt><dd>${esc(p.limits)}</dd>
      <dt>门槛</dt><dd>${esc(p.access)}</dd>
      ${p.usage?`<dt>用法</dt><dd>${esc(p.usage)}</dd>`:''}
      ${p.expiry?`<dt>到期</dt><dd>${esc(p.expiry)}</dd>`:''}
      ${p.env?`<dt>密钥</dt><dd><code>${esc(p.env)}</code></dd>`:''}
      ${p.base_url?`<dt>Base</dt><dd><code>${esc(p.base_url)}</code></dd>`:''}
    </dl>
    ${p.notes?`<div class="meta">${esc(p.notes)}</div>`:''}
    ${p.risk?`<div class="meta" style="color:#fca5a5">风险：${esc(p.risk)}</div>`:''}
    <div class="links">${links} ${keyLink}</div>
    <div class="actions">
      ${p.base_url?`<button data-copy="${esc(p.base_url)}">复制 BaseURL</button>`:''}
      ${p.gateway?`<button data-copy="${esc(snippet(p))}">复制客户端配置</button>`:''}
    </div>
  </article>`;
}
function render(){
  const items = D.filter(matches);
  $('#grid').innerHTML = items.length ? items.map(card).join('') :
    '<div class="empty">没有匹配的渠道，试试清空筛选。</div>';
  $('#sub').textContent = `当前显示 ${items.length} / ${D.length} 个渠道`;
  document.querySelectorAll('[data-copy]').forEach(b=>
    b._h || (b._h=1, b.addEventListener('click',()=>copy(b.dataset.copy))));
}
function init(){
  const stats = P.stats || {};
  const cards = [
    ['渠道', stats.providers || D.length],
    ['模型', stats.models || 0],
    ['可网关', stats.gateway_providers || 0],
    ['本次变更', (P.changes||[]).length],
  ];
  $('#stats').innerHTML = cards.map(([k,v])=>
    `<div class="stat"><b>${v}</b><small>${k}</small></div>`).join('');
  $('#gen').textContent = `生成于 ${P.generated_at} (UTC+8)`;
  const tabs = [['all','全部'], ...Object.entries(CAT).map(([k,v])=>[k,v])];
  $('#tabs').innerHTML = tabs.map(([k,v])=>{
    const n = k==='all' ? D.length : D.filter(p=>p.categories.includes(k)).length;
    return `<span class="tab ${k==='all'?'on':''}" data-cat="${k}">${v} <small>${n}</small></span>`;
  }).join('');
  $('#tabs').addEventListener('click', e=>{
    const t = e.target.closest('.tab'); if(!t) return;
    S.cat = t.dataset.cat;
    document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x===t));
    render();
  });
  $('#q').addEventListener('input', e=>{S.q=e.target.value; render();});
  $('#region').addEventListener('change', e=>{S.region=e.target.value; render();});
  $('#status').addEventListener('change', e=>{S.status=e.target.value; render();});
  const ch = (P.changes||[]);
  $('#changes').innerHTML = ch.length ? ch.slice().reverse().map(c=>
    `<li><b>${esc(c.name||c.source)}</b>　+${c.added_count||0} / -${c.removed_count||0}
     <span style="opacity:.7">${esc(c.at||'')}</span></li>`).join('') :
    '<li>暂无变更记录。</li>';
  render();
}
init();
</script>
</body>
</html>
"""


def render_site(
    registry: dict,
    status: dict | None,
    changes: list[dict] | None,
    out_dir: Path | None = None,
) -> Path:
    out_dir = out_dir or util.SITE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(registry, status, changes)
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html_text = _HTML.replace("__PAYLOAD__", blob)
    path = out_dir / "index.html"
    util.atomic_write(path, html_text)
    render_feed(changes, out_dir / "feed.xml")
    return path


def render_feed(changes: list[dict] | None, path: Path) -> str:
    now = format_datetime(datetime.now(timezone.utc))
    items = []
    for change in (changes or [])[-20:][::-1]:
        title = f"{change.get('name', change.get('source'))}: +{change.get('added_count', 0)} / -{change.get('removed_count', 0)}"
        details = []
        if change.get("added"):
            details.append("新增：" + "；".join(change["added"][:10]))
        if change.get("removed"):
            details.append("移除：" + "；".join(change["removed"][:10]))
        items.append(
            "<item>"
            f"<title>{esc(title)}</title>"
            f"<description>{esc(' '.join(details) or '无细节')}</description>"
            f"<pubDate>{now}</pubDate>"
            f"<guid isPermaLink=\"false\">{esc(change.get('source',''))}-{esc(change.get('at',''))}</guid>"
            "</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        "<title>免费 LLM API · 变更</title>"
        "<link>https://freellm.local/</link>"
        "<description>免费 LLM 渠道与模型目录的每日变更</description>"
        f"<lastBuildDate>{now}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    util.atomic_write(path, xml)
    return xml


def render_all(
    registry: dict,
    status: dict | None,
    changes: list[dict] | None,
    root: Path | None = None,
) -> dict:
    root = root or util.ROOT
    readme = render_readme(registry, status, changes, root / "README.md")
    csv_text = render_csv(registry, status, root / "free_llm_api.csv")
    site = render_site(registry, status, changes, root / "site")
    return {
        "readme": str(root / "README.md"),
        "csv": str(root / "free_llm_api.csv"),
        "site": str(site),
        "readme_chars": len(readme),
        "csv_rows": csv_text.count("\n"),
    }
