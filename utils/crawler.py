import requests
from bs4 import BeautifulSoup
import os

def get_ruyisdk_posts(forum_url):
    """获取ruyisdk.cn论坛帖子"""
    try:
        # 添加User-Agent避免被反爬
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(forum_url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        
        # 根据ruyisdk.cn的实际HTML结构解析帖子
        # 这里需要根据实际网页结构调整选择器
        # 示例：查找所有帖子项
        post_elements = soup.find_all('div', class_='post-item')  # 根据实际结构调整
        
        for post in post_elements:
            title = post.find('h3').text.strip() if post.find('h3') else '无标题'
            link = post.find('a')['href'] if post.find('a') else ''
            posts.append({'title': title, 'link': link})
            
        return posts
    except Exception as e:
        print(f"爬取失败: {e}")
        return []
