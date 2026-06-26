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
    
    posts = get_ruyisdk_posts(FORUM_URL)
    if not posts:
        # 没有新帖子时发送通知消息
        no_new_posts_message = "今日无新动态，敬请期待明日更新！"
        send_to_feishu(no_new_posts_message, webhook_url=config["feishu_webhook_url"])
        print("已发送无新动态通知")
        return
    
    summary = generate_summary(posts, api_key=config["chatbox_api_key"])
    send_to_feishu(summary, webhook_url=config["feishu_webhook_url"])
    print("日报发送成功")

if __name__ == "__main__":
    run_daily_report()
