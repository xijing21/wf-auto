import sys
import os
# 添加utils目录到模块搜索路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from utils.crawler import get_ruyisdk_posts
from utils.chatbox_client import generate_summary
from utils.feishu_sender import send_to_feishu
from utils.config_loader import load_config


def run_daily_report():
    """执行ruyisdk.cn每日报告任务"""
    config = load_config()
    FORUM_URL = "https://ruyisdk.cn/"
    DAYS = config.get("DAYS", 1)          # 从 config 读取天数，默认 1

    posts = get_ruyisdk_posts(FORUM_URL, days=DAYS)   # ← 仅此处变化
    if not posts:
        no_new_posts_message = f"最近{DAYS}日无新动态，敬请期待更新！"
        send_to_feishu(no_new_posts_message, webhook_url=config["feishu_webhook_url"])
        print("已发送无新动态通知")
        return
    summary = generate_summary(posts, api_key=config["chatbox_api_key"])
    send_to_feishu(summary, webhook_url=config["feishu_webhook_url"])
    print(f"日报发送成功，共包含 {len(posts)} 篇最近{DAYS}日的帖子")


if __name__ == "__main__":
    run_daily_report()
