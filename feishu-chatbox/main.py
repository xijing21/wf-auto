import sys
import os

# 添加utils目录到模块搜索路径
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from utils.crawler import get_ruyisdk_posts
from utils.chatbox_client import generate_summary
from utils.feishu_sender import send_to_feishu
from utils.config_loader import load_config
from .config import FORUM_URL

def run_daily_report():
    """执行ruyisdk.cn每日报告任务"""
    config = load_config()
    
    posts = get_ruyisdk_posts(FORUM_URL)
    if not posts:
        print("无新帖子，跳过")
        return
    
    summary = generate_summary(posts, api_key=config["chatbox_api_key"])
    send_to_feishu(summary, webhook_url=config["feishu_webhook_url"])
    print("日报发送成功")

if __name__ == "__main__":
    run_daily_report()
