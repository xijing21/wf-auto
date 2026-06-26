import requests
import os

def send_to_feishu(message, webhook_url=None):
    """发送消息到飞书（封装版）"""
    webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("未提供飞书Webhook URL")
    
    payload = {"msg_type": "text", "content": {"text": message}}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        print("飞书消息发送成功")
    except Exception as e:
        print(f"飞书发送失败: {e}")
