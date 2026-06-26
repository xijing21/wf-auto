import requests
import os

def send_to_feishu(message, webhook_url=None):
    print(f"尝试发送消息: {message[:50]}...")  # 打印消息前50字符
    print(f"使用Webhook URL: {webhook_url}")
    
    webhook_url = webhook_url or os.getenv("FEISHU_WEBHOOK_URL")
    if not webhook_url:
        print("错误: 未提供飞书Webhook URL")
        return False
    
    payload = {"msg_type": "text", "content": {"text": message}}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text}")
        response.raise_for_status()
        print("飞书消息发送成功")
        return True
    except Exception as e:
        print(f"飞书发送失败: {e}")
        return False

