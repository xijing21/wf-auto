# RuyiSDK 论坛动态播报

本项目旨在自动抓取 RuyiSDK 论坛（基于 Discourse）最近指定天数的最新帖子，通过 AI 模型生成精简总结，并自动推送到飞书群机器人，方便团队每日跟进社区动态。

## ✨ 功能特性

- **智能抓取**：优先调用 Discourse `/latest.json` 接口获取数据，接口异常时自动回退到 HTML 页面解析。
- **时间过滤**：支持配置获取最近 N 天（如 1 天、3 天、7 天）的新帖，优先使用帖子的「创建时间」，无则使用「最后活动时间」。
- **AI 总结**：调用大语言模型（如 DeepSeek）将获取到的帖子列表整理成易读的日报格式。
- **飞书推送**：将生成的总结通过 Webhook 自动发送至指定的飞书群聊。

## 📂 核心文件说明

本模块位于 `feishu-chatbox/` 目录下，依赖上级目录 `utils/` 中的工具包：

| 文件路径                    | 职责说明                                                                                            |
| :-------------------------- | :-------------------------------------------------------------------------------------------------- |
| `feishu-chatbox/main.py`  | **主入口脚本**。负责串联爬取、总结、发送的整个业务流程。                                      |
| `utils/crawler.py`        | **爬虫模块**。负责获取论坛帖子，解析时间并按天数过滤，返回包含 `title` 和 `link` 的列表。 |
| `utils/chatbox_client.py` | **AI 总结模块**。接收帖子列表，调用大模型 API 生成日报文本。                                  |
| `utils/feishu_sender.py`  | **飞书发送模块**。封装飞书 Webhook 接口，负责将文本消息推送到群聊。                           |
| `utils/config_loader.py`  | **配置加载模块**。统一从环境变量读取 API Key、Webhook URL 和抓取天数 `DAYS`。               |

## ⚙️ 配置说明

脚本运行依赖以下环境变量（通过 `config_loader.py` 加载）：

| 环境变量名             | 是否必填 | 说明                             |
| :--------------------- | :------- | :------------------------------- |
| `FEISHU_WEBHOOK_URL` | 是       | 飞书自定义机器人的 Webhook 地址  |
| `CHATBOX_API_KEY`    | 是       | 用于调用 AI 总结接口的 API Key   |
| `DAYS`               | 否       | 获取最近几天的帖子，默认为 `7` |

## 🚀 怎么使用

### 1. 本地运行

确保你的 Python 环境中已安装依赖（如 `requests`, `beautifulsoup4` 等，详见根目录 `requirements.txt`）。

在项目根目录执行以下命令：

```bash
# 方式一：直接在命令前指定环境变量
DAYS=7 FEISHU_WEBHOOK_URL="你的飞书webhook" CHATBOX_API_KEY="你的api_key" python feishu-chatbox/main.py
# 方式二：先 export 环境变量，再运行
export DAYS=3
export FEISHU_WEBHOOK_URL="你的飞书webhook"
export CHATBOX_API_KEY="你的api_key"
python feishu-chatbox/main.py
```
### 2. GitHub Actions 部署
本项目设计为通过 GitHub Actions 定时触发。在仓库的 `.github/workflows/` 下的 yml 文件中，需要做如下配置：
**步骤 1：在 GitHub 仓库设置中添加变量和密钥**
- 在 `Settings -> Secrets and variables -> Actions -> Variables` 中添加 `DAYS`（如值为 `7`）。
- 在 `Settings -> Secrets and variables -> Actions -> Secrets` 中添加 `FEISHU_WEBHOOK_URL` 和 `CHATBOX_API_KEY`。
**步骤 2：在 Workflow YAML 中映射环境变量**
```yaml
jobs:
  send-report:
    runs-on: ubuntu-latest
    env:
      DAYS: ${{ vars.DAYS }}                      # 映射 Variables
      FEISHU_WEBHOOK_URL: ${{ secrets.FEISHU_WEBHOOK_URL }} # 映射 Secrets
      CHATBOX_API_KEY: ${{ secrets.CHATBOX_API_KEY }}       # 映射 Secrets
    steps:
      - name: Run main script
        run: python feishu-chatbox/main.py
```
配置完成后，Action 将按照设定的 cron 表达式定时执行，自动将社区新动态推送到飞书群。

