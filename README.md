# 免费 LLM API 金铲子

> 自动生成于 2026-11-12 00:01:28（UTC+8）。数据源：`config/providers.json`（唯一事实源）+ `data/status.json`（最近探活）。

一个自用的免费 LLM 资源收集、追踪与统一网关：把各家免费额度聚合成 **一个 OpenAI 兼容端点**，客户端只改 `base_url` 就能用。

## 30 秒上手

```bash
# 0) 可选：本地有 refers_template 时补种目录；已带 config/providers.json 可跳过
python -m shovel bootstrap

# 1) 抓公开源 + 探活 + 生成面板/README/CSV
python -m shovel update
python -m shovel probe                 # 只探已配置 key 的渠道 + 免 key 渠道

# 2) 启动统一网关（同时托管面板）
python -m shovel serve

# 3) 任意 OpenAI 客户端指向本地网关
export OPENAI_BASE_URL=http://127.0.0.1:8756/v1
export OPENAI_API_KEY=local
```

密钥只从环境变量读取；复制 `.env.example` 为 `.env` 并填写，或直接 `export`。
不想申请任何 key 也能先用下面的免 key 渠道；拿到 key 后网关会自动把它们加入候选。

## 免 key 开箱即用

- **Pollinations（匿名层）**：`https://text.pollinations.ai/openai`，OpenAI 兼容、无需注册。
  无 SLA、限流随时变化，适合原型。
- **AI Horde**：`https://oai.aihorde.net/v1`，社区众包推理，匿名免 key；
  排队优先级低，最小生成长度 16 tokens。

```bash
curl http://127.0.0.1:8756/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"auto","messages":[{"role":"user","content":"ping"}],"max_tokens":16}'
```

## 常用命令

| 命令 | 作用 |
|---|---|
| `python -m shovel init` | 创建 `config/` 与 `data/` 默认配置 |
| `python -m shovel bootstrap` | 从参考语料播种注册表；只补缺，不覆盖手改字段 |
| `python -m shovel update` | 抓 OpenRouter / Pollinations / AI Horde 等公开源并做快照 diff |
| `python -m shovel probe [--only ID]` | 逐模型探活，写 `data/status.json` 与 uptime |
| `python -m shovel report` | 由 `config/providers.json` 重建 README / CSV / 面板 / RSS |
| `python -m shovel serve [--port 8756]` | 启动 OpenAI 兼容网关 + 本地面板 |
| `python -m shovel doctor [--network]` | 检查密钥、配置、状态新鲜度与外部源可达性 |
| `python -m unittest discover -s tests` | 跑单元测试（零第三方依赖） |

## 目录

| 路径 | 说明 |
|---|---|
| `config/providers.json` | **唯一事实源**，可手工编辑；bootstrap 只补缺 |
| `config/aliases.json` | 模型家族别名（自动生成 + `manual` 手写覆盖） |
| `config/gateway.json` | 网关绑定、默认模型、冷却、候选上限、优先级 |
| `config/sources.json` | 外部发现源（enabled=false 即关闭） |
| `data/` | 可再生运行数据：registry/status/uptime/changes/snapshots（已 gitignore） |
| `site/` | 单文件面板 `index.html` 与 RSS `feed.xml`（已 gitignore，由 report/CI 生成） |
| `free_llm_api.csv` | 可导入 Excel 的扁平目录（已 gitignore，由 report 生成） |

## 接入客户端

任何支持自定义 OpenAI Base URL 的客户端都可用：`http://127.0.0.1:8756/v1`，
API key 任意填（若设置了 `SHOVEL_TOKEN`，则填该值）。模型名可以用：

- `auto`：按健康状态与优先级自动选择；
- 家族别名（如 `qwen`、`deepseek`、`gemini`，见 `config/aliases.json`）；
- 精确模型名（如 `glm-4.7-flash`）；
- `provider/model`（如 `openrouter/qwen/qwen3.8-27b:free`）。

## 统计

- 渠道：**131** 个（可网关 26 个）
- 模型：**110** 条
- 分类：官方 API 免费层 65，云平台 / 聚合平台 32，编程 Agent / CLI / IDE 16，学生 / 教育福利 6，聊天客户端 5，限时活动 / 羊毛 8，每日签到 / 领额度 8，免费算力 3，公益中转 / 灰色渠道（不推荐） 3

## 渠道目录

### 官方 API 免费层

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| AI Horde | — | global | 永久 | koboldcpp/Llama-3.2-1B-Instruct、koboldcpp/gemma-4-31B-it、koboldcpp/debug-gemma-4-E2B-Queen-it-qat-q4_0-unquantized.i1-Q4_K_M、koboldcpp/debug-Vesper-26B-A4B-Nocturne.i1-Q4_K_M_hb16 等 15 款 | RPM: Queue-based; anonymous requests have the lowest priority, registered users earn kudos for priority; RPD: No fixed cap (volunteer capacity) | 未知 | 2026-11-11 | ✅ 正常可用 |
| AI21 Labs | — | global | 未知 | 2 个模型，最大上下文 256K，Text | 未公布 | 未知 | — | ⚪ 未测 |
| Agnes AI | — | global | 未知 | Agnes 3.0 Flash, Agnes 2.5 Flash, Agnes Image 2.1 Flash (image) | RPM: About 30 RPM per account (video 2 RPM), per third-party listings; RPD: Not published | 未知 | — | ⚪ 未测 |
| Aion Labs | — | global | 未知 | Aion 2.0, Aion 3.0 Mini, Aion 3.5 Mini | RPM: Not published (daily credit allowance); RPD: Daily free credit allowance (amount not published by Aion Labs) | 未知 | — | ⚪ 未测 |
| Alibaba Cloud Model Studio | — | global | 未知 | 5 个模型，最大上下文 1M，Text, Vision, Code | 未公布 | 未知 | — | ⚪ 未测 |
| Api.Airforce | — | global | 未知 | GPT-OSS 20B, GLM-4.7 Flash, Essential AI RNJ 1, Kimi K2.7 Code | RPM: 1 RPM; RPD: 1,000 requests/day | 未知 | — | ⚪ 未测 |
| Arli AI | — | global | 未知 | Qwen3.5 27B Derestricted | RPM: 1 request at a time; max 12K context tokens; RPD: Limited trial uses per model (about 5 requests per 2 days, per third-party list) | 未知 | — | ⚪ 未测 |
| Cerebras | Cerebras | global | 一次性 | gpt-oss-120b、qwen-3.8-27b | RPM 5 / TPM 30000 / TPD 1000000 | 邮箱 | 2026-10-30 | ⚪ 未测 |
| Chutes.ai | Chutes | global | 每日刷新 | DeepSeek/Qwen/Llama 开源系 | 00:00 UTC 重置；需先充值 5 美元解锁免费档 | 未知 | 2026-10-29 | ⚪ 未测 |
| Cloudflare Workers AI | Cloudflare | global | 永久 | @cf/meta/llama-3.3-70b-instruct-fp8-fast、@cf/qwen/qwen3.8-27b、@cf/openai/gpt-oss-120b、@cf/zai-org/glm-4.7-flash | RPM 300 | 邮箱 | 2026-10-30 | ⚪ 未测 |
| Cohere | Cohere | global | 每月 | Command 系列 / Embed / Rerank | 1000 次/月、20 RPM（chat） | 邮箱 | 2026-10-29 | ⚪ 未测 |
| DeepSeek | — | global | 未知 | 2 个模型，最大上下文 128K，Text | 未公布 | 未知 | — | ⚪ 未测 |
| DeepSeek 官方 API | 深度求索 | cn | 未知 | DeepSeek-V4 系列 | — | 手机号 | 2026-10-30 | ⚪ 未测 |
| FreeInference | — | global | 未知 | GLM-5.3 Flash, DeepSeek V4 Flash, MiniMax M3, Qwen3.6 35B A3B | RPM: Not published (&quot;generous quota&quot;; HTTP 429 when rate-limited); RPD: No published daily cap | 未知 | — | ⚪ 未测 |
| Glhf.chat | — | global | 未知 | 2 个模型，最大上下文 131K，Text | 未公布 | 未知 | — | ⚪ 未测 |
| Gonka Broker | — | global | 未知 | 4 个模型，最大上下文 400K，Multimodal | 未公布 | 未知 | — | ⚪ 未测 |
| Google AI Studio | — | global | 未知 | Gemini 3.8 Flash, Gemma 4 26B A4B IT, Gemma 4 31B IT, Gemini 3 Flash Preview | RPM: Varies by model (per-model limits are now shown only inside AI Studio); RPD: Varies by model. Free: Gemini 3.x Flash / Flash-Lite and Gemini 2.5 Pro/Flash (2.5 redirect to 3.x on Dec 1, 2026); Gemini 3.x Pro and Gemini 4 are paid | 未知 | — | ⚪ 未测 |
| Google Gemini | — | global | 永久 | gemini-3.8-flash、gemini-3.5-flash、gemini-3.1-flash-lite、gemini-2.5-flash | 未公布 | 未知 | 2026-09-30 | ⚪ 未测 |
| Groq | Groq | global | 永久 | openai/gpt-oss-120b、openai/gpt-oss-20b、qwen/qwen3.8-27b | RPM 30 / RPD 1000 / TPM 8000 / TPD 200000 | 邮箱 | 2026-10-30 | ⚪ 未测 |
| Hetzner Inference API | — | global | 未知 | Qwen3.8 27B, Qwen3.6 35B A3B | RPM: 10 requests, 4M input / 100K output tokens per 60s (per API key); RPD: No daily cap published (free while the API is experimental); a Hetzner account with billing details is required and Hetzner may ask for a card or ID to verify it | 未知 | — | ⚪ 未测 |
| Hugging Face | — | global | 未知 | 9 个模型，最大上下文 131K，Text, Vision, Code | 未公布 | 未知 | — | ⚪ 未测 |
| Kilo AI Gateway | — | global | 未知 | Nemotron 3.5 Lightning, Nemotron 3 Nano Omni Reasoning, Dots3-Note Preview, Reflection Beam 1.0 | RPM: 200 requests/hour per IP on free models (anonymous use allowed); RPD: Default free models only | 未知 | — | ⚪ 未测 |
| Kilo Code | — | global | 未知 | 29 个模型，最大上下文 1M，Multimodal | 未公布 | 未知 | — | ⚪ 未测 |
| Kimi 开放平台 | 月之暗面 | cn | 一次性 | kimi-k2 等开源模型 | 仅限 kimi-k2 等开源系列模型抵扣 | 手机号、实名 | 2026-10-30 | ⚪ 未测 |
| LLM.kiwi | — | global | 未知 | Auto router, MiniMax M3, Nemotron 3 Ultra, Nemotron 3 Super | RPM: Baseline rate limits (figures not published); RPD: Not published | 未知 | — | ⚪ 未测 |
| LLM7.io | — | global | 未知 | Nemotron 3 Nano 30B, GLM 5.3 Flash, Mistral Nemo Instruct 2407, Codestral Latest | RPM: 1 req/s, 60/min, 250/hour (free token from dash.llm7.io); RPD: 100,000 tokens per 24h (free token; may be reduced without notice) | 未知 | — | ⚪ 未测 |
| MiniMax | — | cn | 一次性 | MiniMax-M3、MiniMax-M2.7、MiniMax-M2.5 | RPM 20 / TPM 1000000 | 手机号 | 2026-09-30 | ⚪ 未测 |
| Mistral AI | — | global | 永久 | mistral-small-2603、mistral-moderation-2603 | 未公布 | 未知 | 2026-09-30 | ⚪ 未测 |
| Mistral La Plateforme | Mistral AI | global | 每月 | Mistral 全系（Experiment 层） | 第三方口径约 1B tokens/月、500K TPM、1 req/s；部分旗舰模型 403 | 手机号 | 2026-10-30 | ⚪ 未测 |
| Mixlayer | — | global | 未知 | Qwen3.5 4B (free) | RPM: Per-organization, per-model RPM/TPM (values shown in console only); RPD: Not published | 未知 | — | ⚪ 未测 |
| NVIDIA NIM | NVIDIA | global | 永久 | deepseek-ai/deepseek-v4.1-flash、z-ai/glm-5-3、moonshotai/kimi-k3、nvidia/nemotron-3-ultra-550b-a55b 等 5 款 | RPM 40 / RPD 10000 | 邮箱 | 2026-10-29 | ⚪ 未测 |
| Nebius Token Factory | — | global | 一次性 | Qwen/Qwen3-235B-A22B、moonshotai/Kimi-K2.5 | RPM 60 / TPM 400000 | 未知 | 2026-09-30 | ⚪ 未测 |
| Nous Portal | — | global | 未知 | StepFun Step 3.7 Flash, Reflection Beam 1.0, Upstage Solar Mini 4, Crouton Alpha (stealth, free) | RPM: Standard rate limits (figures not published); RPD: Free models only (no monthly credit) | 未知 | — | ⚪ 未测 |
| Novita AI | — | global | 永久 | inclusionai/ling-3.1-flash、inclusionai/ling-3.0-flash-sante、inclusionai/ling-3.0-flash-vl | RPM 30 / TPM 50000000 | 未知 | 2026-09-30 | ⚪ 未测 |
| Nscale | — | global | 未知 | 2 个模型，最大上下文 128K，Text | 未公布 | 未知 | — | ⚪ 未测 |
| OVH AI Endpoints | — | global | 未知 | GPT OSS 120B, BGE-M3 (embeddings), Whisper Large v3 Turbo, Qwen2.5 VL 72B Instruct | RPM: 2 RPM per IP per model (anonymous, free); 400 RPM with a key (pay-as-you-go); RPD: Unspecified | 未知 | — | ⚪ 未测 |
| OVHcloud AI Endpoints | — | global | 未知 | 16 个模型，最大上下文 262K，Multimodal | 未公布 | 未知 | — | ⚪ 未测 |
| Ollama Cloud | — | global | 未知 | Reflection Beam (501B) | RPM: Pay-as-you-go: 3 concurrent requests; only Beam (beam:cloud) is labelled free; RPD: No free monthly allowance any more (starter credits removed); other cloud models are billed per token | 未知 | — | ⚪ 未测 |
| OpenCode Zen | — | global | 未知 | 34 个模型，最大上下文 1M，Multimodal | 未公布 | 未知 | — | ⚪ 未测 |
| OpenRouter | OpenRouter | global | 永久 | openrouter/free、qwen/qwen3.8-27b:free、baidu/ernie-5.5-flash-preview:free、thinkingmachines/inkling-2-small:free 等 17 款 | RPD 50 | 邮箱 | 2026-11-11 | ⚪ 未测 |
| OpenTyphoon (Typhoon API) | — | global | 未知 | Typhoon 2.5 30B A3B Instruct, Typhoon OCR 1.5 | RPM: 5 requests/second, 200 RPM (text models); 20 RPM for OCR; RPD: No daily cap published | 未知 | — | ⚪ 未测 |
| Pollinations (匿名) | — | global | 永久 | openai-fast、openai、gpt-oss、gpt-oss-20b 等 5 款 | RPM: API key required (anonymous access removed); no card; RPD: Free usage paid from Quest Pollen earned in the dashboard | 未知 | 2026-11-11 | ✅ 正常可用 |
| Routeway | — | global | 未知 | DeepSeek V4.1 Flash (free), MiniMax M3.1 Flash (free), Muse Glimmer 30B | RPM: 5 RPM on :free models; RPD: 200 requests/day | 未知 | — | ⚪ 未测 |
| SEA-LION API | — | global | 未知 | Qwen SEA-LION v4.5 27B Instruct, Llama SEA-LION v3.5 70B Reasoning, SEA-Guard (safety), SEA-LION Embedding 600M | RPM: 10 requests/minute per user (increase on request: sealion@aisingapore.org); RPD: Not published | 未知 | — | ⚪ 未测 |
| SambaNova (SambaCloud) | — | global | 永久 | DeepSeek-V3.2、DeepSeek-V3.1、Meta-Llama-3.3-70B-Instruct、gpt-oss-120b | RPM 20 / RPD 20 / TPD 200000 | 未知 | 2026-09-30 | ⚪ 未测 |
| SenseNova (SenseTime) | — | global | 未知 | SenseNova 6.8 Flash Lite | RPM: Not published; RPD: Not published (\&quot;限时放量\&quot; during public beta) | 未知 | — | ⚪ 未测 |
| Together AI | Together AI | global | 永久 | Prism-ML/Ternary-Bonsai-27B、together/Tev1-4B-experimental | 免费端点少且为低配版本 | 邮箱 | 2026-10-29 | ⚪ 未测 |
| Z.ai 国际 API | 智谱AI（国际站） | cn | 永久 | GLM-Flash 系列 | 免费档约 1 并发，偶发 429 | 邮箱 | 2026-10-29 | ⚪ 未测 |
| Zhipu BigModel (China) | — | global | 未知 | GLM-4.7-Flash, GLM-4.5-Flash, GLM-4-Flash-250414, GLM-4.6V-Flash (vision) | RPM: Low concurrency on free Flash models (GLM-4.7-Flash reported at 1 concurrent request); RPD: Not published | 未知 | — | ⚪ 未测 |
| iFlytek Spark Lite | — | global | 未知 | Spark Lite | RPM: Not published on the HTTP doc; RPD: Not published (Lite is free) | 未知 | — | ⚪ 未测 |
| xAI 数据共享赠金 | xAI | global | 未知 | Grok 系列 | — | 未知 | 2026-10-29 | ⚪ 未测 |
| 书生 InternLM 开放平台 | 上海AI实验室 | cn | 永久 | InternLM 系列 | 10 RPM；密钥 6 个月有效 | 实名 | 2026-10-29 | ⚪ 未测 |
| 商汤日日新 | 商汤科技 | cn | 未知 | SenseNova / DeepSeek-V4-flash | 20 个 API key，三模型独立计数 | 手机号 | 2026-11-05 | ⚪ 未测 |
| 智谱 AI (BigModel) | — | cn | 永久 | glm-4.7-flash、glm-4-flash-250414、glm-z1-flash、glm-4v-flash | 未公布 | 手机号 | 2026-09-30 | ⚪ 未测 |
| 月之暗面 Kimi | — | cn | 一次性 | kimi-k3、kimi-k2.5、kimi-k2.7-code | RPM 3 / TPM 500000 / TPD 1500000 | 手机号、实名 | 2026-09-30 | ⚪ 未测 |
| 火山方舟 Volcengine Ark | — | cn | 一次性 | doubao-seed-2-1-pro-260628、doubao-seed-2-1-lite-260915、doubao-seed-2-1-turbo-260628、doubao-seed-2-1-pro-260915 等 7 款 | 未公布 | 实名 | 2026-09-30 | ⚪ 未测 |
| 百川智能 Baichuan | — | cn | 一次性 | Baichuan4-Turbo、Baichuan-M3-Plus | RPM 120 / RPD 300 | 手机号、实名 | 2026-09-30 | ⚪ 未测 |
| 百度千帆 Qianfan | — | cn | 一次性 | ERNIE-4.5-Turbo-128K、ERNIE-4.5-Turbo-32K、DeepSeek-R1、Kimi-K2-Instruct | 未公布 | 实名 | 2026-09-30 | ⚪ 未测 |
| 硅基流动 SiliconFlow | 硅基流动 | cn | 永久 | Qwen/Qwen3-8B、Qwen/Qwen3.5-4B、deepseek-ai/DeepSeek-R1-0528-Qwen3-8B、THUDM/GLM-Z1-9B-0414 | 免费模型名单动态调整，以定价页为准 | 实名 | 2026-10-30 | ⚪ 未测 |
| 腾讯混元 / TokenHub | — | cn | 一次性 | hy4-preview、hy3-preview | 未公布 | 实名 | 2026-09-30 | ⚪ 未测 |
| 讯飞星火 Spark | — | cn | 永久 | lite | 未公布 | 实名 | 2026-09-30 | ⚪ 未测 |
| 阶跃星辰 StepFun | — | cn | 永久 | step-gui | RPM 100 / TPM 500000 | 手机号、实名 | 2026-09-30 | ⚪ 未测 |
| 阿里云百炼 DashScope | — | cn | 一次性 | qwen3.8-max、qwen3.8-flash、qwen-plus、qwen-turbo 等 5 款 | RPM 1200 / TPM 5000000 | 手机号 | 2026-09-30 | ⚪ 未测 |
| 零一万物 Yi | — | cn | 未知 | yi-lightning、yi-vision-v2 | RPM 4 / TPM 32000 | 手机号、实名 | 2026-09-30 | ⚪ 未测 |
| 魔搭 ModelScope | 阿里云 | cn | 永久 | Qwen/Qwen3.8-27B、deepseek-ai/DeepSeek-V4.1-Flash、ZhipuAI/GLM-4.7-Flash、stepfun-ai/Step-3.7-Flash | 每日 2000 次（按模型计，单模型另有动态限额，如 DeepSeek-R1 200 次/日） | 手机号、实名 | 2026-10-30 | ⚪ 未测 |

### 云平台 / 聚合平台

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| Amazon Q Developer | AWS | global | 未知 | Claude 系 | — | 未知 | 2026-10-30 | ⚪ 未测 |
| Augment Code Community 层 | Augment | global | 未知 | — | — | 未知 | 2026-10-29 | ⚪ 未测 |
| Gemini CLI | Google | global | 每日刷新 | Gemini Flash / Pro 系 | 官方口径 60 RPM / 1000 请求/日，实测常更低 | 未知 | 2026-10-30 | ⚪ 未测 |
| GitHub Models | GitHub | global | 未知 | 多厂商开源/闭源模型 | — | 未知 | 2026-10-30 | ⚪ 未测 |
| Google AI Plus 学生版 | Google | global | 学生专属 | Gemini Omni / Deep Research 等 | 免费 12 个月；地区与资格以官方学生领取页为准 | 学生认证 | 2026-11-06 | ⚪ 未测 |
| Google Colab | Google | global | 每日刷新 | —（GPU 环境） | 额度不透明；单会话约 9-12 小时，超额可能 24 小时冷却 | 未知 | 2026-10-29 | ⚪ 未测 |
| HuggingFace Inference Providers 免费赠金 | HuggingFace | global | 未知 | 托管的开源模型 | 已无免费额度；PRO $9/月含 $2/月 | 未知 | 2026-11-06 | ⚪ 未测 |
| LLM-Red-Team 逆向 API 系列 | 社区组织 | cn | 未知 | qwen/glm/kimi/doubao-free-api | — | 未知 | 2026-11-06 | ⚪ 未测 |
| Notion 教育版 | Notion | global | 学生专属 | Notion AI（半价） | — | 邮箱 | 2026-10-29 | ⚪ 未测 |
| OpenAI Codex CLI | OpenAI | global | 每日刷新 | GPT-5 系 | 5 小时滚动窗口 + 周上限，额度较轻 | 未知 | 2026-10-30 | ⚪ 未测 |
| Perplexity Education Pro 学生计划 | Perplexity | global | 学生专属 | 多模型搜索 | Education Pro $10/月；免费仅限首月 | 学生认证 | 2026-11-06 | ⚪ 未测 |
| SambaNova Cloud | SambaNova | global | 每日刷新 | Llama/DeepSeek 开源系 | 20 RPM / 20 RPD / 200K tokens·日·模型 | 未知 | 2026-10-30 | ⚪ 未测 |
| ZCode 夜间免费 Flash | 智谱AI | cn | 未知 | GLM-5.3-Flash | — | 未知 | 2026-10-30 | ⚪ 未测 |
| 文心智能体平台（独立接入） | 百度 | cn | 未知 | 文心系列 | — | 未知 | 2026-10-29 | ⚪ 未测 |
| 智谱高校 X 计划 | 智谱AI | cn | 未知 | GLM 系列 | — | 未知 | 2026-10-30 | ⚪ 未测 |
| 火山方舟 | 字节跳动·火山引擎 | cn | 每日刷新 | 豆包全系 | 奖励计划额度 T+1 返还；不抵扣批量推理 | 实名 | 2026-10-30 | ⚪ 未测 |
| 百度千帆 | 百度智能云 | cn | 永久 | ERNIE Speed / Lite / Tiny | Speed-8K/Lite：300 RPM、30 万 TPM；Speed-128K：60 RPM | 实名 | 2026-10-30 | ⚪ 未测 |
| 腾讯 CodeBuddy | 腾讯 | cn | 每月 | DeepSeek-V4 / 混元 | 以当前订阅档位为准 | 未知 | 2026-10-30 | ⚪ 未测 |
| 阿里云 Model Studio 国际站 | 阿里云国际 | global | 一次性 | Qwen 系为主 | 仅新加坡区国际账号 | 未知 | 2026-10-29 | ⚪ 未测 |
| 阿里云百炼 | 阿里云 | cn | 一次性 | Qwen/DeepSeek 等 | 仅实时推理，不含 Batch/微调 | 实名 | 2026-10-31 | ⚪ 未测 |

### 编程 Agent / CLI / IDE

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| Copilot 学生版 | GitHub / 微软 | global | 学生专属 | Auto + 少量自选 | 2026-03-12 起学生权益缩水，不再送完整 Pro | 未知 | 2026-10-30 | ⚪ 未测 |
| Cursor Hobby | Cursor | global | 每月 | 有限自选 | 官方不公示具体数字 | 邮箱 | 2026-10-30 | ⚪ 未测 |
| Fitten Code / CodeGeeX / Tabnine | 非十 / 智谱 / Tabnine | cn | 永久 | 各自家模型 | 功能有限，无 Agent 级额度 | 未知 | 2026-10-29 | ⚪ 未测 |
| GitHub Copilot Free | GitHub / 微软 | global | 每月 | 自动分配模型（Auto） | 补全 2000/月；聊天次数官方已不再公布固定数字（旧口径 50 次/月） | 未知 | 2026-10-30 | ⚪ 未测 |
| JetBrains AI Free | JetBrains | global | 永久 | 本地模型为主 | 云端额度仅 3 AI Credits/30 天，几乎不够一次 Agent 任务 | 未知 | 2026-10-29 | ⚪ 未测 |
| Kiro | AWS | global | 每月 | Claude 系 | 1 次 Agent 交互 = 1 credit；无 Spec 请求 | 未知 | 2026-10-30 | ⚪ 未测 |
| Qoder | 阿里 | cn | 限时 | Qwen3.8-Flash / GLM | 每日合计可领 600+ Credits；SOTA 资源包次日 12:30 失效、Qwen 包次日 10:00 失效，当天用掉 | 未知 | 2026-11-01 | ⚪ 未测 |
| Qwen Code CLI | 阿里 | cn | 每日刷新 | Qwen3-Coder 系列 | 原 2000 次/日，2026-04-15 政策调整后约 100 次/日 | 未知 | 2026-10-30 | ⚪ 未测 |
| Trae / Trae SOLO | 字节跳动 | cn | 永久 | Doubao-Seed-Code / DeepSeek / Kimi | 无官方固定数字，额度不透明 | 手机号 | 2026-10-30 | ⚪ 未测 |
| Warp | Warp | global | 每月 | 多模型 | 2026 年起转 credit 制 | 邮箱 | 2026-10-29 | ⚪ 未测 |
| Windsurf | Windsurf（原 Codeium） | global | 每日刷新 | SWE 系 | 2026-03-19 起取消月度 Credits，改日/周配额 | 邮箱 | 2026-10-30 | ⚪ 未测 |
| ZCode（智谱编程工具） | 智谱AI | cn | 每日刷新 | GLM-5.3 / GLM-5-turbo / GLM-5.3-Flash | 以客户端与文档为准 | 手机号 | 2026-10-31 | ⚪ 未测 |
| iFlow CLI 心流 | 心流（阿里系） | cn | 永久 | Qwen3-Max / Kimi K2 / Qwen3-Coder | 宣传不限量，无官方限速数字，实际有速率限制 | 未知 | 2026-10-30 | ⚪ 未测 |
| 文心快码 Comate | 百度 | cn | 永久 | 文心大模型 | 高级功能 300 次/周 | 未知 | 2026-10-29 | ⚪ 未测 |
| 通义灵码 | 阿里 | cn | 每月 | Qwen 系列 | 以社区版额度为准 | 未知 | 2026-10-29 | ⚪ 未测 |

### 学生 / 教育福利

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| Azure for Students | 微软 | global | 学生专属 | Azure AI 服务 | 额度 12 个月内用完即止 | 邮箱、学生认证 | 2026-10-29 | ⚪ 未测 |
| GitHub Student Developer Pack | GitHub | global | 学生专属 | Copilot Student 等 | 包内各权益有效期不同 | 学生认证 | 2026-10-30 | ⚪ 未测 |
| 华为云沃土云创 | 华为云 | cn | 学生专属 | —（云资源为主） | 以活动页为准 | 学生认证 | 2026-10-29 | ⚪ 未测 |
| 腾讯云学生优惠 | 腾讯云 | cn | 学生专属 | —（云资源） | 以学生页为准 | 学生认证 | 2026-10-29 | ⚪ 未测 |
| 豆包学生权益 | 字节跳动 | cn | 学生专属 | 豆包 2.1 Pro 等 | 每账号限一次；权益内容以 App 内展示为准 | 学生认证 | 2026-10-30 | ⚪ 未测 |
| 阿里云云工开物 | 阿里云 | cn | 学生专属 | 百炼全系（抵扣） | 300 元/年 | 学生认证 | 2026-10-30 | ⚪ 未测 |

### 聊天客户端

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| DeepSeek App / 网页版 | 深度求索 | cn | 永久 | DeepSeek-V4 / R 系推理 | 高峰期限流 | 手机号 | 2026-10-29 | ⚪ 未测 |
| Kimi App / 网页版 | 月之暗面 | cn | 永久 | Kimi 主力模型 | 高峰期限速 | 手机号 | 2026-10-29 | ⚪ 未测 |
| 智谱清言 | 智谱AI | cn | 永久 | GLM 主力模型 | 高级模型功能部分需会员 | 手机号 | 2026-10-29 | ⚪ 未测 |
| 腾讯元宝 | 腾讯 | cn | 永久 | 混元 / DeepSeek | — | 未知 | 2026-10-29 | ⚪ 未测 |
| 豆包 App / 网页版 | 字节跳动 | cn | 永久 | 豆包主力模型 | 免费版额度低于会员（学生认证可到 2.5 倍，见学生区） | 手机号 | 2026-10-29 | ⚪ 未测 |

### 限时活动 / 羊毛

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| AutoClaw 周活动 | 智谱 Z.AI | cn | 限时 | GLM-5.3-Flash 等 | 本周积分须在 11 月 8 日 23:59 前用完；加码积分 24 小时有效 | 未知 | 2026-11-04 | ⚪ 未测 |
| SenseNova 6.8 Flash 限免 | 商汤科技 | cn | 限时 | SenseNova 6.8 Flash（正式版） | 限免期至 2026-12-01，范围以小浣熊内公告为准 | 未知 | 2026-11-05 | ⚪ 未测 |
| Trae 每日签到积分 | 字节跳动 | cn | 每日刷新 | Trae 内置模型 | 积分有效期 31 个自然日，优先消耗最先过期的积分 | 未知 | 2026-11-04 | ⚪ 未测 |
| ZCode Global Build（每日 3 亿） | 智谱AI | cn | 限时 | GLM-5.3-Flash | 每天 19:00 起领取；使用窗口当晚 23:00–次日 09:00（共 10 小时）；需 ZCode 客户端 v3.10+ | 手机号 | 2026-10-31 | ⚪ 未测 |
| 千问办公 0.01 元月卡 | 阿里（千问办公） | cn | 限时 | 千问办公全系（积分制） | 仅限此前无订阅记录的新购用户，限购 1 件；兑换码一次性、无自动续费 | 未知 | 2026-11-04 | ⚪ 未测 |
| 智谱开放平台活动页 | 智谱AI | cn | 未知 | GLM 系列 | 以活动页实时内容为准 | 未知 | 2026-10-31 | ⚪ 未测 |
| 社区传闻渠道 | 各平台 | cn | 未知 | — | — | 未知 | 2026-10-29 | ⚪ 未测 |
| 阿里云百炼新客返券 | 阿里云 | cn | 限时 | 百炼全系 | 返券比例以活动页为准 | 实名 | 2026-10-29 | ⚪ 未测 |

### 每日签到 / 领额度

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| Accio Work | 阿里巴巴国际站 | cn | 每日刷新 | 阿里系模型 | 每日 20 Credits 量级小，适合轻量体验 | 未知 | 2026-11-04 | ⚪ 未测 |
| Agent2API（签到聚合工具） | 开源（aimod-cc） | cn | 永久 | 聚合各平台已接入模型 | 工具本身免费开源（Windows 桌面版 / Docker） | 未知 | 2026-11-04 | ⚪ 未测 |
| MonkeyCode | 长亭科技 | cn | 每日刷新 | MiniMax M2.7 / Qwen3.5-plus 等免费标记模型 | 共享池耗尽后按算力扣费；免费模型名单动态调整 | 未知 | 2026-11-04 | ⚪ 未测 |
| WorkBuddy 每日活跃奖励 | 字节跳动（火山引擎） | cn | 每日刷新 | 豆包 / 火山方舟系模型 | Free 100 积分/月；每日活跃奖励每账号每日最多 1 次 | 未知 | 2026-11-06 | ⚪ 未测 |
| 办公小浣熊 | 商汤科技 | cn | 每日刷新 | 日日新系模型 | 免费版积分按次消耗，以官方积分规则为准 | 未知 | 2026-11-06 | ⚪ 未测 |
| 百度搭子 / 库库AI | 百度 | cn | 每日刷新 | 文心系模型 | 以活动页为准 | 未知 | 2026-11-01 | ⚪ 未测 |
| 豆包每日签到活动 | 字节跳动 | cn | 限时 | 豆包主力模型 | 活动制，签到与里程碑规则以 App 内活动页为准 | 未知 | 2026-11-01 | ⚪ 未测 |

### 免费算力

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| Kaggle Notebooks | Kaggle（Google） | global | 未知 | —（GPU/TPU 环境） | 单会话最长约 12 小时 | 手机号、邮箱 | 2026-10-29 | ⚪ 未测 |
| 百度飞桨 AI Studio | 百度 | cn | 每日刷新 | —（GPU 环境） | 算力卡按项目消耗 | 未知 | 2026-10-29 | ⚪ 未测 |

### 公益中转 / 灰色渠道（不推荐）

| 渠道 | 提供方 | 地区 | 免费性质 | 免费模型 / 内容 | 限额 | 门槛 | 核实 | 状态 |
|---|---|---|---|---|---|---|---|---|
| ChatGPT 镜像站清单 | 社区维护 | cn | 永久 | GPT 镜像 | 站点流动性极大 | 未知 | 2026-10-29 | ⚪ 未测 |
| chatanywhere 公益免费 API | 社区公益 | cn | 未知 | GPT / DeepSeek 系 | 低速率；模型池有限 | 未知 | 2026-10-29 | ⚪ 未测 |
| gpt4free | xtekky（开源） | global | 永久 | 逆向各网页版 | provider 频繁失效 | 未知 | 2026-10-29 | ⚪ 未测 |

## 统一网关

`python -m shovel serve` 后：

- `GET /v1/models`：列出已登记模型与别名。
- `POST /v1/chat/completions`：支持 `stream: true`；按别名或 `provider/model` 路由，遇到 429/5xx/超时自动切换下一家。
- `GET /`：本地面板；`GET /healthz`：健康检查。

模型别名示例（自动生成，见 `config/aliases.json`）：`deepseek`，`ernie`，`gemini`，`gemma`，`glm`，`gpt-oss`，`hunyuan`，`kimi`，`llama`，`minimax`，`mistral`，`nemotron`，`qwen`，`step`

## 数据口径

- 每条渠道保留自己的 `verified_at`；表格里不存在「全表最后核实日」这种伪口径。
- 派生产物（README / CSV / 面板 / RSS）全部由 `config/providers.json` 与 `data/status.json` 生成，可随时重建。
- 灰色/公益中转渠道仅记录与标注风险，不进入网关、不推荐使用。

## 最近变更

- `2026-11-11T15:53:41Z` **AI Horde 免 key 模型目录**：+2 / -0

