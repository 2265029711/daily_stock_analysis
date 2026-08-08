# Changelog

所有重要更改都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 变更
- 🔄 AI 供应商改为 OpenAI 兼容格式独占
  - 移除 Gemini 支持（配置、依赖、workflow、文档全量清理）
  - 仅保留 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 配置
  - 重命名分析器为 `OpenAIAnalyzer`，简化为单一重试链路
- 🔔 新增 Bark（iOS）推送，通知渠道独立解耦
  - 企业微信 / Bark 各自独立配置、独立发送、互不影响
  - 新增 `BARK_DEVICE_KEY` / `BARK_SERVER_URL` / `BARK_GROUP` 配置
- ✅ 新增单元测试（pytest）：`tests/test_config.py`、`tests/test_analyzer.py`、`tests/test_notification.py`

### 计划中
- 钉钉机器人支持
- 飞书机器人支持
- Web 管理界面

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持
  - 支持 DeepSeek、通义千问、Moonshot、智谱 GLM 等
  - Gemini 和 OpenAI 格式二选一
  - 自动降级重试机制

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 决策仪表盘分析
  - 一句话核心结论
  - 精确买入/止损/目标点位
  - 检查清单（✅⚠️❌）
  - 分持仓建议（空仓者 vs 持仓者）
- 📊 大盘复盘功能
  - 主要指数行情
  - 涨跌统计
  - 板块涨跌榜
  - AI 生成复盘报告
- 🔍 多数据源支持
  - AkShare（主数据源，免费）
  - Tushare Pro
  - Baostock
  - YFinance
- 📰 新闻搜索服务
  - Tavily API
  - SerpAPI
- 💬 企业微信机器人推送
- ⏰ 定时任务调度
- 🐳 Docker 部署支持
- 🚀 GitHub Actions 零成本部署

### 技术特性
- Gemini AI 模型（gemini-3-flash-preview）
- 429 限流自动重试 + 模型切换
- 请求间延时防封禁
- 多 API Key 负载均衡
- SQLite 本地数据存储

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v1.0.0
