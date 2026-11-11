<h1 align="center">⛏️ 免费 LLM API</h1>

<p align="center">收集、探活、追踪免费 LLM API，聚合成一个本地 OpenAI 兼容端点。</p>

<p align="center"><a href="https://maybebio.github.io/Daily-Free-LLM/"><img alt="panel: live" src="https://img.shields.io/badge/panel-live-5eead4?style=flat-square"></a> <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white&style=flat-square"> <img alt="dependencies: 0" src="https://img.shields.io/badge/dependencies-0-34d399?style=flat-square"> <img alt="OpenAI compatible" src="https://img.shields.io/badge/API-OpenAI%20compatible-10a37f?logo=openai&logoColor=white&style=flat-square"> <img alt="providers: 131" src="https://img.shields.io/badge/providers-131-3b82f6?style=flat-square"> <img alt="models: 110" src="https://img.shields.io/badge/models-110-8b5cf6?style=flat-square"> <img alt="gateway: 26" src="https://img.shields.io/badge/gateway-26-f59e0b?style=flat-square"></p>

<p align="center"><code>free-llm</code> · <code>openai-api</code> · <code>gateway</code> · <code>zero-dependency</code> · <code>self-hosted</code></p>

## 快速开始

```bash
python -m shovel update    # 抓取公开源并做差异追踪
python -m shovel probe     # 探活已配置 key + 免 key 渠道
python -m shovel serve     # 网关和面板都在 127.0.0.1:8756
```

- 网关：`http://127.0.0.1:8756/v1`（OpenAI 兼容）
- 面板：[在线](https://maybebio.github.io/Daily-Free-LLM/) / [本地](http://127.0.0.1:8756/)
- 密钥只从环境变量读取，参考 `.env.example`

没有 key 也能先用：Pollinations `https://text.pollinations.ai/openai`，AI Horde `https://oai.aihorde.net/v1`。

## 客户端

base URL 填 `http://127.0.0.1:8756/v1`，API key 任意填（设了 `SHOVEL_TOKEN` 就填它）。model 可用 `auto`、家族别名（如 `qwen`）、精确模型名，或 `provider/model`。

```bash
curl http://127.0.0.1:8756/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","messages":[{"role":"user","content":"ping"}],"max_tokens":16}'
```

其他命令：`report` 重建 README/CSV/面板，`doctor` 检查配置，`bootstrap` 补种目录，`python -m unittest discover -s tests` 跑测试。

## 概览

**131** 渠道 · **110** 模型 · **26** 可网关

`api` 65 · `cloud` 32 · `agent` 16 · `student` 6 · `chat` 5 · `event` 8 · `signin` 8 · `gpu` 3 · `gray` 3

## 完整目录在哪

- 面板：可搜索、按分类/地区/状态筛选，并直接复制客户端配置
- `free_llm_api.csv`：扁平表，适合 Excel 或脚本处理
- `site/feed.xml`：新增/移除订阅

## 说明

- README 只做入口；全量渠道与实时状态以上面的面板/CSV 为准。
- `verified_at` 按渠道记录，没有全表统一的核实日期。
- 灰色渠道只做风险记录，不进入网关。
- `config/providers.json` 是唯一事实源；README、CSV、面板、RSS 都由 `report` 重建。

## 最近变更

- `2026-11-11T15:53:41Z` AI Horde 免 key 模型目录：+2 / -0

<sub>自动生成于 2026-11-12 00:42:18（UTC+8）· 数据源 `config/providers.json` + `data/status.json`</sub>

