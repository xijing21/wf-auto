# utils/config_loader.py
import os

def load_config():
    """加载配置（支持环境变量和GitHub Secrets）"""
    return {
        "chatbox_api_key": os.getenv("CHATBOX_API_KEY"),
        "feishu_webhook_url": os.getenv("FEISHU_WEBHOOK_URL"),
        "default_model": "DeepSeek-V4-Flash"
    }
