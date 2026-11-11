# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Self-use "shovel" for free LLM APIs: discover and track free providers/models, probe availability, and expose everything through one local OpenAI-compatible gateway plus a static dashboard/catalog. No third-party Python dependencies; everything is standard library (Python >= 3.10).

## Commands

```bash
python -m shovel init          # create config/ and data/ defaults
python -m shovel bootstrap     # seed registry from refers_template (fills gaps only)
python -m shovel bootstrap --force  # rebuild registry from seeds (discards manual fields)
python -m shovel update        # fetch public sources, snapshot + diff
python -m shovel probe         # probe configured keys + keyless providers
python -m shovel probe --only pollinations,aihorde --timeout 60
python -m shovel report        # regenerate README / CSV / site/ from config + status
python -m shovel serve         # gateway + dashboard on 127.0.0.1:8756
python -m shovel doctor --network
python -m unittest discover -s tests
python -m unittest tests.test_router -v
```

There is no build step, linter, or formatter configured. `python -m compileall shovel tests` is a quick syntax check.

## Architecture

Data flows one way; do not hand-edit derived artifacts:

```
refers_template/ + public sources
        │ bootstrap / update
        ▼
config/providers.json  (single source of truth, hand-editable)
config/aliases.json    (generated model-family aliases + preserved manual overrides)
        │ registry.build_registry()
        ▼
data/registry.json ──► probe ──► data/status.json / data/uptime.jsonl
        │                              │
        └──────── render ──────────────┴──► README.md, free_llm_api.csv, site/index.html, site/feed.xml
        │
        └──► gateway.server (Router + Budgets + SQLite data/gateway.db)
```

- `shovel/util.py`: paths, atomic writes, JSON/JSONL, timestamps, env loading, `http_request` (returns `(status, body, headers)`, never raises for HTTP/network errors).
- `shovel/registry.py`: normalization, dedupe/merge, validation, `build_registry`, status overlay. Merge precedence: same `base_url`, then same normalized `name`, then same `id`. Existing non-empty fields win; model lists union; `categories`/`sources` union; `verified_at` keeps latest.
- `shovel/bootstrap.py`: one-time seeders from the reference corpora (`_from_api_list`, `_from_tracker_csv`, `_from_free_llm_readme`, `_from_awesome_readme`, `_keyless_providers`) plus alias generation.
- `shovel/sources.py`: external discovery. Source kinds: `openrouter_models` (zero prompt+completion price only), `openai_models`, `pollinations_models` (bare list + anonymous tier + aliases), `html`. Discovered providers merge into `config/providers.json`; every fetch is snapshotted and diffed.
- `shovel/diff.py`: normalized line diff (volatile counters stripped) → `data/changes.jsonl`, `data/history.jsonl`.
- `shovel/probe.py`: per-model `POST /chat/completions` (`max_tokens` defaults to 1, honors provider `probe_max_tokens`, e.g. AI Horde needs 16), status classification, optional tool-call probe, provider aggregation, writes status + compact uptime record.
- `shovel/gateway/router.py`: resolves `auto` / family alias / exact model / `provider/model`; filters unhealthy providers/models, cooldowns, and budgets; sorts by ok-status, configured priority, latency, context.
- `shovel/gateway/server.py`: `ThreadingHTTPServer`; `/v1/models`, `/v1/chat/completions` (JSON and SSE passthrough), `/healthz`, `/stats`, `/`, `/feed.xml`. Upstream 429/5xx/network errors fail over to the next candidate. Optional `SHOVEL_TOKEN` bearer auth.
- `shovel/gateway/budgets.py`: SQLite rolling-window rpm/rpd/tpm/tpd checks and usage recording. Conservative: a request that would exceed a limit is refused.
- `shovel/render.py`: all derived artifacts, including the single-file dark dashboard with embedded JSON payload.

## Data and configuration conventions

- `config/providers.json` is authoritative. `data/` and `site/` are gitignored and reproducible.
- Keys are read only from environment variables (loaded from optional `.env`). Never write keys to config, data, SQLite, logs, or commits.
- Per-item `verified_at`; never derive a table-wide verification date.
- `free_nature`: `permanent|daily|monthly|one_time|limited|student|unknown`; categories: `api|cloud|agent|student|chat|event|signin|gpu|gray`.
- `gray` (公益中转/灰色渠道) entries are catalogued for risk awareness but must not be gateway candidates.
- Keyless providers are not guaranteed forever: Pollinations' anonymous endpoint moved from `gen.pollinations.ai/v1` (now 401) to `text.pollinations.ai/openai`; AI Horde is `oai.aihorde.net/v1`. Re-verify endpoints before documenting them as keyless.

## Reference corpora (`refers_template/`)

Vendored, read-only, gitignored. Mine schemas and pipelines; never edit.

| Corpus | Contribution |
|---|---|
| `free-llm-api-list/` | Verified provider schema (`policy.signup/limits/access`, per-item `verified_at`), probe/status pipeline. |
| `free-llm-tracker/` | 92-channel CSV + embedded `DATA`; categories and non-API routes (chat/student/event/signin/gpu/gray). |
| `free-llm-daily/` | Daily summary generation patterns. |
| `awesome-freellm-apis/`, `Free-LLM/` | Overseas provider catalogs, limits, key links. |
| `UNION_ALL/one-api`, `UNION_ALL/free-one-api`, `freellmapi/` | Gateway semantics (OpenAI compatibility, load balancing, heartbeat, auto-disable). Do not import their code or dependencies. |

## Process rules inherited from references

1. Verification dates are per-item, never per-table.
2. Derived artifacts must be rebuilt from one source of truth (CI runs `report`).
3. Normalize before diffing; only real additions/removals should surface.
4. Fetch success != valid content; validate semantics.
5. Changing a field requires auditing every consumer (README, CSV, dashboard payload, filters, fetch, gateway).
6. Version numbers and quotas decay fastest; prefer official docs over roundups.
7. No unverifiable claims: delete or mark them unverified.
