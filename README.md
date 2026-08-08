# 📈 A股智能分析系统

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)

> 🤖 基于 AI 大模型的 A 股自选股智能分析系统，每日自动分析并推送「决策仪表盘」到企业微信 / Bark（iOS）

![运行效果演示](./sources/2026-01-10_155341_daily_analysis.gif)

## ✨ 功能特性

### 🎯 核心功能
- **AI 决策仪表盘** - 一句话核心结论 + 精确买卖点位 + 检查清单
- **多维度分析** - 技术面 + 筹码分布 + 舆情情报 + 实时行情
- **大盘复盘** - 每日市场概览、板块涨跌、北向资金
- **定时推送** - 支持企业微信机器人 / Bark 自动推送
- **👥 多用户推送** - 每个用户独立配置推送范围（大盘/指定个股/全部），互不影响
- **🔑 Tavily 多 Key 轮换** - 配额用尽自动切换下一个 Key，搜索不断流
- **零成本部署** - GitHub Actions 免费运行，无需服务器
- **🔗 OpenAI 兼容 API** - 支持 OpenAI / DeepSeek / 通义千问 / Moonshot / 智谱 GLM 等，一键切换模型
- **🔄 多模型支持** - 任意 OpenAI 格式 API 均可接入（DeepSeek、通义千问等）

### 📊 数据来源
- **行情数据**: AkShare（免费，主源）、Tushare（免费积分）、Baostock（免费）、YFinance（免费）；实时行情含腾讯兜底
- **新闻搜索**: Tavily（免费 1000 次/月）、SerpAPI（免费 100 次/月）
- **AI 分析**: 
  - OpenAI 兼容 API（OpenAI / DeepSeek / 通义千问 / Moonshot 等），格式统一、切换只需改配置

### 🛡️ 交易理念内置
- ❌ **严禁追高** - 乖离率 > 5% 自动标记「危险」
- ✅ **趋势交易** - MA5 > MA10 > MA20 多头排列
- 📍 **精确点位** - 买入价、止损价、目标价
- 📋 **检查清单** - 每项条件用 ✅⚠️❌ 标记

## 🚀 快速开始

### 方式一：GitHub Actions（推荐，零成本）

**无需服务器，每天自动运行！**

#### 1. Fork 本仓库

点击右上角 `Fork` 按钮

#### 2. 配置 Secrets

进入你 Fork 的仓库 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Secret 名称 | 说明 | 必填 |
|------------|------|:----:|
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（OpenAI/DeepSeek/通义千问/GLM 等） | ✅ |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址（如 `https://api.deepseek.com/v1`） | ✅ |
| `OPENAI_MODEL` | 模型名称（按供应商文档填写，如 `deepseek-chat`/`glm-4-flash`） | ✅ |
| `WECHAT_WEBHOOK_URL` | 企业微信机器人 Webhook | 二选一* |
| `BARK_DEVICE_KEY` | Bark 设备 Key（iOS 推送） | 二选一* |
| `STOCK_LIST` | 自选股代码，如 `600519,300750,002594` | ✅ |
| `TAVILY_API_KEY_1` | Tavily Key（一个 key 一个 secret，最多 4 个自动轮询） | 推荐 |
| `TAVILY_API_KEYS` | Tavily Key（逗号分隔单行，兼容格式） | 可选 |
| `BARK_KEY_USER_A/B/C/D` | 多用户推送设备 Key（与 `push_config.yaml` 占位符对应，未配置的用户自动跳过） | 可选 |
| `ANALYZE_REQUESTED_ONLY` | 按需分析开关（`true` 只分析用户请求的股票） | 可选 |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/) Key | 可选 |
| `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro/) Token | 可选 |

> *注：`WECHAT_WEBHOOK_URL` 和 `BARK_DEVICE_KEY` 至少配置一个（推送渠道互相独立，可同时配置）
>
> **多用户推送**：`push_config.yaml` 需随仓库提交（device_key 用 `${ENV}` 占位符，无明文 Key），
> 每个用户在仓库 Secrets 中添加对应的 `BARK_KEY_USER_X`，workflow 已预置 A/B/C/D 映射。

#### 3. 启用 Actions

进入 `Actions` 标签 → 点击 `I understand my workflows, go ahead and enable them`

#### 4. 手动测试

`Actions` → `每日股票分析` → `Run workflow` → 选择模式 → `Run workflow`

#### 5. 完成！

默认每个工作日 **18:00（北京时间）** 自动执行

### 方式二：本地运行

```bash
# 克隆仓库
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
vim .env  # 填入你的 API Key

# 运行（src layout）
export PYTHONPATH=src                                  # Windows: set PYTHONPATH=src
python -m stock_analysis.main                          # 完整分析
python -m stock_analysis.main --market-review          # 仅大盘复盘
python -m stock_analysis.main --schedule               # 定时任务模式
```

### 方式三：Docker 部署

```bash
# 配置环境变量
cp .env.example .env
vim .env

# 一键启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 📱 推送效果

### 决策仪表盘（标准推送模板）
```
🎯 2026-01-10 决策仪表盘
3只 | 🟢买入:1 🟡观望:2 🔴卖出:0

🟢 贵州茅台(600519) | 买入 | 评分75 | 看多

📊 实时行情: 现价 1309.22(+0.05%) | 量比 0.63 | 换手 0.2% | PE 19.79 | PB 7.03 | 市值 16366亿
📈 技术面: 均线 多头排列 | 乖离 -0.46%✅ | 趋势分 68 | 信号 持有
📰 茅台发布一季报经营数据公告
💡 结论: 回踩MA5可分批介入
📌 理由: 缩量回踩MA5支撑，乖离率安全，多头排列
📍 买: 理想买入点：1309.00元（MA5附近）；损: 止损位：1290.00元；标: 目标位：1400.00元
⚠️ 提示: 注意解禁风险
---（股票过多时整股截断，评分低的先省略）
```

### 大盘复盘
```
🎯 2026-01-10 大盘复盘

📊 主要指数
- 上证指数: 3250.12 (🟢+0.85%)
- 深证成指: 10521.36 (🟢+1.02%)
- 创业板指: 2156.78 (🟢+1.35%)

📈 市场概况
上涨: 3920 | 下跌: 1349 | 涨停: 155 | 跌停: 3

🔥 板块表现
领涨: 互联网服务、文化传媒、小金属
领跌: 保险、航空机场、光伏设备
```

## ⚙️ 配置说明

### 1. 创建 .env 环境文件

`.env` 是系统的**唯一环境配置入口**，保存在项目根目录（已被 `.gitignore` 忽略，不会提交泄露）。

```bash
# 第一步：从模板创建（模板在 .env.example，已含全部配置项和注释）
cp .env.example .env

# 第二步：编辑填入真实配置
vim .env    # Windows: notepad .env
```

配置加载优先级：**系统环境变量 > .env 文件 > 代码默认值**。

> 多用户推送（push_config.yaml）中的 `${ENV}` 占位符同样读取 `.env` 中的变量。

### 2. 配置清单

#### 🔴 必填（不配置系统无法运行）

| 变量 | 说明 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | AI API Key（OpenAI 兼容，任一家供应商） | `sk-xxxxxxxx` |
| `OPENAI_BASE_URL` | AI API 地址 | `https://api.deepseek.com/v1` |
| `OPENAI_MODEL` | 模型名称（按供应商文档） | `deepseek-chat` |
| `STOCK_LIST` | 自选股代码（逗号分隔） | `600519,300750` |

**OpenAI 兼容 API 供应商对照**：

| 供应商 | BASE_URL | MODEL 示例 |
|--------|----------|-----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| OpenAI 官方 | `https://api.openai.com/v1` | `gpt-4o-mini` |

#### 🟢 推荐（建议配置，提升分析质量）

| 变量 | 说明 | 示例 |
|------|------|------|
| `TAVILY_API_KEYS` | 新闻搜索（免费 1000 次/月，支持多 Key 逗号分隔自动轮换） | `tvly-key1,tvly-key2` |
| `BARK_DEVICE_KEY` | Bark iOS 推送设备 Key（通知渠道，二选一或同时配企微） | `esAPi6th...` |
| `WECHAT_WEBHOOK_URL` | 企业微信机器人 Webhook（通知渠道，二选一或同时配 Bark） | `https://qyapi...` |

> 通知渠道：`BARK_DEVICE_KEY` 和 `WECHAT_WEBHOOK_URL` **至少配置一个**，两个渠道互相独立。

#### ⚪ 可选（按需配置）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BARK_SERVER_URL` | `https://api.day.app` | Bark 服务器（自建可改） |
| `BARK_GROUP` | `股票分析` | iOS 通知分组 |
| `BARK_KEY_USER_A/B/C...` | 无 | 多用户推送占位符（配合 push_config.yaml） |
| `SERPAPI_KEYS` | 无 | 备用搜索引擎（免费 100 次/月） |
| `TUSHARE_TOKEN` | 无 | Tushare 数据源（免费积分制） |
| `OPENAI_REQUEST_DELAY` | `2.0` | AI 请求间隔（秒），防限流 |
| `OPENAI_MAX_RETRIES` | `5` | AI 最大重试次数 |
| `OPENAI_RETRY_DELAY` | `5.0` | AI 重试基础延时（秒） |
| `SCHEDULE_ENABLED` | `false` | 是否启用定时任务 |
| `SCHEDULE_TIME` | `18:00` | 每日执行时间 |
| `MARKET_REVIEW_ENABLED` | `true` | 是否启用大盘复盘 |
| `LOG_DIR` | `./logs` | 日志目录 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `MAX_WORKERS` | `3` | 并发线程数（低并发防封禁） |
| `DEBUG` | `false` | 调试模式 |

### 3. 验证配置

```bash
# 检查配置是否完整（会列出缺失/警告项）
PYTHONPATH=src python scripts/check_env.py
```

### 4. 定时配置（GitHub Actions）

编辑 `.github/workflows/daily_analysis.yml`:

```yaml
schedule:
  # UTC 时间，北京时间 = UTC + 8
  - cron: '0 10 * * 1-5'   # 周一到周五 18:00（北京时间）
```

| 北京时间 | UTC cron |
|---------|----------|
| 09:30 | `'30 1 * * 1-5'` |
| 15:00 | `'0 7 * * 1-5'` |
| 18:00 | `'0 10 * * 1-5'` |

## 👥 多用户推送（push_config.yaml）

不同用户可以收到不同的推送内容（支持全 A 股，不限于 STOCK_LIST）：

```yaml
users:
  - name: 用户A-大盘
    device_key: ${BARK_KEY_USER_A}   # 支持 ${ENV} 占位符（本地 .env / GHA secrets）
    group: 大盘走势
    push_market: true                 # 接收大盘复盘
    stocks: []                        # 不接收个股

  - name: 用户B-个股
    device_key: ${BARK_KEY_USER_B}
    group: 个股分析
    push_market: false
    stocks: ['600519', '300750']    # 指定个股（⚠️ 代码必须用引号包裹）；"all" = 全部自选股
```

- 复制 `push_config.example.yaml` 为 `push_config.yaml` 使用
- 用户指定的股票**自动纳入分析范围**（A 股任意 6 位代码）
- 每个用户独立推送，失败互不影响；无 `push_config.yaml` 时回退 .env 单 key 配置
- Bark 推送使用**标准推送模板**，股票过多时**整股截断**（评分低的先丢，不拆分单只股票）

### ⚡ 按需分析（省 API 额度）

默认分析 STOCK_LIST 全量（多用户共享一次结果）。如果只想分析用户实际请求的股票（避免多余查询）：

```bash
# .env 中开启
ANALYZE_REQUESTED_ONLY=true
```

- 分析范围 = 各用户 `stocks` 并集（`stocks: all` 会拉入全部 STOCK_LIST）
- 无用户请求个股时跳过个股分析（只跑大盘复盘）
- `false`（默认）保持全量分析 + 合并用户股票

### 📋 标准推送模板（每只股票）

```
🟢 名称(代码) | 操作建议 | 评分 | 趋势
📊 实时行情: 现价 | 量比 | 换手 | PE | PB | 市值
📈 技术面: 均线 | 乖离率 | 趋势分 | 信号
📰 最新新闻 / 🚨 风险 / ✨ 利好
💡 结论: 一句话决策
📌 理由: 操作依据
📍 买/损/标 狙击点位
⚠️ 提示: 风险提示
```

### 🔑 Tavily 多 Key 轮换

`TAVILY_API_KEYS` 支持多个 Key，**推荐一个 key 一行**（也兼容逗号分隔）：
```bash
# 方式一（推荐）：一个 key 一行，自动轮询
TAVILY_API_KEY_1=tvly-key1
TAVILY_API_KEY_2=tvly-key2

# 方式二（兼容）：逗号分隔单行
# TAVILY_API_KEYS=tvly-key1,tvly-key2
```
- 多个 Key **自动轮询**使用（负载均衡）
- 某个 Key **配额用尽**（429/402/rate limit）时自动标记冷却 30 天并切换下一个 Key（状态持久化在 `data/search_keys_state.json`，重启不丢失）
- 全部 Key 耗尽时跳过搜索并告警，不影响分析主流程

## 📁 项目结构

```
daily_stock_analysis/
├── src/                  # 源码（src layout）
│   └── stock_analysis/   # 主包
│       ├── main.py             # 主程序入口
│       ├── analyzer.py         # AI 分析器（OpenAI 兼容）
│       ├── market_analyzer.py  # 大盘复盘分析
│       ├── search_service.py   # 新闻搜索服务（Tavily/SerpAPI 多 Key 轮换）
│       ├── notification.py     # 消息推送（企业微信 / Bark / 多用户）
│       ├── push_config.py      # 多用户推送配置（push_config.yaml）
│       ├── scheduler.py        # 定时任务
│       ├── storage.py          # 数据存储
│       ├── config.py           # 配置管理（.env）
│       └── data_provider/      # 数据源适配器
│           ├── akshare_fetcher.py
│           ├── tushare_fetcher.py
│           ├── baostock_fetcher.py
│           └── yfinance_fetcher.py
├── tests/                # 单元测试（pytest，73+ 用例）
├── scripts/              # 辅助脚本（check_env.py 环境检查）
├── docs/                 # 文档（DEPLOY/CHANGELOG/CONTRIBUTING）
├── push_config.example.yaml  # 多用户推送配置模板
├── .env.example          # 环境变量模板（复制为 .env 使用）
├── .github/workflows/    # GitHub Actions
├── Dockerfile            # Docker 镜像
├── docker-compose.yml    # Docker 编排
└── requirements.txt      # 依赖
```

## 🗺️ Roadmap

> 📢 以下功能将视后续情况逐步完成，如果你有好的想法或建议，欢迎 [提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues) 讨论！

### 🔔 通知渠道扩展
- [x] 企业微信机器人
- [x] Bark（iOS 推送）
- [ ] 钉钉机器人
- [ ] 飞书机器人
- [ ] Telegram Bot
- [ ] Discord Webhook
- [ ] Slack Webhook
- [ ] 邮件通知
- [ ] Pushover

### 🤖 AI 模型支持
- [x] OpenAI 兼容 API（OpenAI / DeepSeek / 通义千问 / Moonshot / 智谱GLM 等，只需改 Base URL 和模型名）
- [ ] Claude
- [ ] 本地模型（Ollama）

### 📊 数据源扩展
- [x] AkShare（免费）
- [x] Tushare Pro
- [x] Baostock
- [x] YFinance
- [ ] 东方财富 API
- [ ] 同花顺 API
- [ ] 新浪财经

### 🎯 功能增强
- [x] 决策仪表盘
- [x] 大盘复盘
- [x] 定时推送
- [x] GitHub Actions
- [ ] Web 管理界面
- [ ] 自选股动态管理 API
- [ ] 历史分析回测
- [ ] 多策略支持
- [ ] 港股/美股支持

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

详见 [贡献指南](CONTRIBUTING.md)

## 📄 License

[MIT License](LICENSE) © 2026 ZhuLinsen

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。作者不对使用本项目产生的任何损失负责。

---

**如果觉得有用，请给个 ⭐ Star 支持一下！**
