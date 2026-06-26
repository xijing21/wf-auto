from utils.crawler import get_ruyisdk_posts
from utils.ai_client import generate_summary
from utils.feishu_sender import send_to_feishu
from utils.config_loader import load_config
from .config import FORUM_URL  # 任务特定配置

def run_daily_report():
    """执行ruyisdk.cn每日报告任务"""
    # 加载全局配置
    config = load_config()
    
    # 1. 爬取最新帖子
    posts = get_ruyisdk_posts(FORUM_URL)
    if not posts:
        print("无新帖子，跳过")
        return
    
    # 2. 调用AI生成总结
    summary = generate_summary(posts, api_key=config["chatbox_api_key"])
    
    # 3. 发送到飞书
    send_to_feishu(summary, webhook_url=config["feishu_webhook_url"])
    print("日报发送成功")

if __name__ == "__main__":
    run_daily_report()
