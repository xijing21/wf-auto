# -*- coding: utf-8 -*-
"""
AI 日报生成模块
职责：接收爬虫产出的帖子列表，调用大模型生成结构化日报。
设计要点：
  - system / user 双角色分离，system 只放角色与格式约束
  - 强制 Markdown 分类输出，杜绝自由发挥
  - API 异常自动重试 + 最终降级为本地拼接
  - 不引入新依赖，仅用 openai SDK
"""

import os
import time
from openai import OpenAI

# ── 模型与端点配置 ──
DEFAULT_MODEL = "DeepSeek-V4-Flash"
BASE_URL = "https://chatbox.isrc.ac.cn/v1"

# ── system prompt：只定义角色 + 输出约束，不含具体数据 ──
SYSTEM_PROMPT = """你是 RuyiSDK 社区日报助手，负责将论坛新帖整理成简洁的飞书群日报。

输出要求：
1. 用 Markdown 格式，严格按以下结构输出，禁止增减分区或加额外说明：
## 📢 RuyiSDK 社区日报（最近{days}日）
共 {count} 条新动态，分类如下：

### 🚀 版本与功能
- <一句话概括>：[标题](链接)

### 🐛 问题反馈
- <一句话概括>：[标题](链接)

### 💬 使用讨论
- <一句话概括>：[标题](链接)

### 📄 其他
- <一句话概括>：[标题](链接)

2. 每条只写一句精炼概括，不要复述原标题；无帖子的分类直接省略该分区。
3. 链接必须使用原始 URL，不得编造或改写。
4. 全文控制在 600 字以内。"""


def _build_user_message(posts, days):
    """把帖子列表拼成干净的用户消息，去掉一切客套引导词"""
    lines = [f"以下是最近 {days} 日内的 {len(posts)} 条帖子，请按系统指令生成日报：", ""]
    for p in posts:
        title = p.get("title", "无标题")
        link = p.get("link", p.get("url", ""))
        lines.append(f"- {title} | {link}")
    return "\n".join(lines)


def _call_api(client, model, messages, max_retries=2):
    """带重试的 API 调用，指数退避"""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,   # 日报场景偏确定性，避免发挥
                max_tokens=1200,
                timeout=30,
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(2 ** attempt)   # 1s, 2s
    raise last_err


def _fallback_text(posts, days):
    """API 最终失败时的本地降级：纯文本拼接，保证日报仍能发出"""
    lines = [f"## 📢 RuyiSDK 社区日报（最近{days}日）", f"共 {len(posts)} 条新动态：", ""]
    for i, p in enumerate(posts, 1):
        title = p.get("title", "无标题")
        link = p.get("link", p.get("url", ""))
        lines.append(f"{i}. {title}：{link}")
    return "\n".join(lines)


def generate_summary(posts, api_key=None, model=DEFAULT_MODEL, days=1):
    """
    生成日报文本
    :param posts: list[dict]，每项含 title / link（或 url）
    :param api_key: 大模型 API Key，缺省从环境变量 CHATBOX_API_KEY 读
    :param model: 模型名
    :param days: 天数，用于填充日报标题
    :return: Markdown 格式日报字符串
    """
    if not posts:
        return f"最近 {days} 日暂无新动态，敬请期待更新！"

    api_key = api_key or os.getenv("CHATBOX_API_KEY")
    if not api_key:
        raise ValueError("未提供 API 密钥（CHATBOX_API_KEY）")

    client = OpenAI(api_key=api_key, base_url=BASE_URL)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(days=days, count=len(posts))},
        {"role": "user", "content": _build_user_message(posts, days)},
    ]

    try:
        return _call_api(client, model, messages)
    except Exception as e:
        print(f"[chatbox_client] AI 调用失败，降级为本地拼接: {e}")
        return _fallback_text(posts, days)
