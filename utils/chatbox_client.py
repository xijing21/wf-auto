from openai import OpenAI
import os

def generate_summary(posts, api_key=None, model="DeepSeek-V4-Flash"):
    """调用AI生成帖子总结"""
    if not posts:
        return "暂无新内容"
    
    prompt = "为以下帖子生成简洁总结，每行格式：<总结>：<链接>\n帖子列表：\n"
    for post in posts:
        prompt += f"- {post['title']}\n"
    
    api_key = api_key or os.getenv("CHATBOX_API_KEY")
    if not api_key:
        raise ValueError("未提供API密钥")
    
    client = OpenAI(api_key=api_key, base_url="https://chatbox.isrc.ac.cn/v1")
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI调用失败: {e}")
        return "\n".join([f"{post['title']}：{post['link']}" for post in posts])
