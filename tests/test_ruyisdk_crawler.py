#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RuyiSDK 论坛帖子爬取工具
- 优先使用 Discourse /latest.json 接口（最可靠）
- 回退到 HTML 解析（基于 Discourse 实际 DOM 结构）
- 创建时间优先，无则用 activity 时间
用法:
    python3 ruyisdk_crawler.py            # 默认最近 7 天
    python3 ruyisdk_crawler.py 3          # 最近 3 天
    python3 ruyisdk_crawler.py 1          # 今日
    python3 ruyisdk_crawler.py https://ruyisdk.cn 7
输出: 标题：链接
"""

import sys
import json
import re
from datetime import datetime, timedelta, timezone

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

FORUM_URL = "https://ruyisdk.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")


def http_get(url, timeout=15):
    """统一的 HTTP GET，兼容有无 requests"""
    headers = {'User-Agent': UA}
    if HAS_REQUESTS:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text, resp.headers.get('Content-Type', '')
    else:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode('utf-8', errors='replace')
            ct = resp.headers.get('Content-Type', '')
            return data, ct


# ──────────────────────────────────────────────
# 方法1: JSON 接口 (推荐，时间字段最可靠)
# ──────────────────────────────────────────────
def fetch_via_json(forum_url, max_pages=5):
    """通过 /latest.json 获取帖子列表"""
    base = forum_url.rstrip('/')
    topics = []
    url = base + '/latest.json'

    for page in range(max_pages):
        try:
            text, ct = http_get(url)
            data = json.loads(text)
        except Exception as e:
            print(f"[JSON] 第 {page+1} 页请求失败: {e}")
            break

        batch = data.get('topic_list', {}).get('topics', [])
        if not batch:
            break
        topics.extend(batch)

        more = data.get('topic_list', {}).get('more_topics_url')
        if not more:
            break
        url = base + more if more.startswith('/') else more

    print(f"[JSON] 共获取 {len(topics)} 个主题")
    return topics


def filter_json_topics(topics, days):
    """从 JSON 数据中筛选最近 N 天的帖子"""
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)

    results = []
    for t in topics:
        if t.get('pinned') or t.get('pinned_globally'):
            continue

        # 优先 created_at，回退 last_posted_at / bumped_at (activity)
        created_str = t.get('created_at', '')
        activity_str = t.get('last_posted_at', '') or t.get('bumped_at', '')

        created_dt = parse_iso(created_str)
        activity_dt = parse_iso(activity_str)

        # 用哪个时间做筛选
        if created_dt and created_dt >= start:
            use_dt = created_dt
            time_label = f"创建: {use_dt:%Y-%m-%d %H:%M}"
        elif activity_dt and activity_dt >= start:
            use_dt = activity_dt
            time_label = f"活动: {use_dt:%Y-%m-%d %H:%M}"
        else:
            continue

        results.append({
            'title': t.get('title', '无标题'),
            'url': f"{FORUM_URL.rstrip('/')}/t/topic/{t.get('id', '')}",
            'time_label': time_label,
            'sort_time': use_dt,
        })

    results.sort(key=lambda x: x['sort_time'], reverse=True)
    return results


# ──────────────────────────────────────────────
# 方法2: HTML 解析 (回退方案，基于 Discourse 实际 DOM)
# ──────────────────────────────────────────────
def fetch_via_html(forum_url, days):
    """通过 HTML 页面解析帖子列表"""
    if not HAS_BS4:
        print("[HTML] 未安装 beautifulsoup4，跳过 HTML 解析")
        return []

    base = forum_url.rstrip('/')
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)

    results = []

    for page in range(1, 6):
        url = f"{base}/latest" if page == 1 else f"{base}/latest?page={page}"
        try:
            html, _ = http_get(url)
        except Exception as e:
            print(f"[HTML] 第 {page} 页请求失败: {e}")
            break

        soup = BeautifulSoup(html, 'html.parser')

        # Discourse 帖子行: tr.topic-list-item 或 tr[data-topic-id]
        rows = soup.find_all('tr', class_='topic-list-item')
        if not rows:
            rows = soup.select('tr[data-topic-id]')
        if not rows:
            break

        for row in rows:
            # ── 提取标题和链接 ──
            link_el = row.find('a', class_='title')
            if not link_el:
                link_el = row.find('a', class_='raw-link')
            if not link_el:
                link_el = row.find('a', class_='raw-topic-link')
            if not link_el:
                main_td = row.find('td', class_='main-link')
                if main_td:
                    link_el = main_td.find('a')
            if not link_el:
                continue

            title = link_el.get_text(strip=True)
            href = link_el.get('href', '')
            if not title or not href:
                continue

            if 'pinned' in row.get('class', []) or 'sticky' in row.get('class', []):
                continue

            link = href if href.startswith('http') else base + href

            # ── 提取时间 ──
            # Discourse 用 span.relative-date，data-time 是 epoch 毫秒
            time_dt = None
            time_label = ""

            # 1. 先找含 "created" 的 relative-date span
            for span in row.find_all('span', class_='relative-date'):
                dt_title = span.get('data-title', '')
                if 'creat' in dt_title.lower():
                    time_dt = extract_time_from_span(span)
                    if time_dt:
                        time_label = f"创建: {time_dt:%Y-%m-%d %H:%M}"
                        break

            # 2. 没有则用 td.activity 列
            if not time_dt:
                activity_td = row.find('td', class_='activity')
                if activity_td:
                    span = activity_td.find('span', class_='relative-date')
                    if span:
                        time_dt = extract_time_from_span(span)
                    else:
                        time_dt = extract_time_from_element(activity_td)
                    if time_dt:
                        time_label = f"活动: {time_dt:%Y-%m-%d %H:%M}"

            # 3. 兜底: 行内任意 relative-date
            if not time_dt:
                any_span = row.find('span', class_='relative-date')
                if any_span:
                    time_dt = extract_time_from_span(any_span)
                    if time_dt:
                        time_label = f"时间: {time_dt:%Y-%m-%d %H:%M}"

            if not time_dt:
                continue

            if time_dt >= start:
                results.append({
                    'title': title,
                    'url': link,
                    'time_label': time_label,
                    'sort_time': time_dt,
                })

    results.sort(key=lambda x: x['sort_time'], reverse=True)
    print(f"[HTML] 共匹配 {len(results)} 个帖子")
    return results


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────
def parse_iso(iso_str):
    """解析 Discourse ISO 时间: 2026-06-29T11:25:26.479Z"""
    if not iso_str:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            dt = datetime.strptime(iso_str, fmt)
            return dt.replace(tzinfo=timezone.utc).astimezone()
        except ValueError:
            continue
    m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', iso_str)
    if m:
        try:
            dt = datetime.strptime(m.group(1), '%Y-%m-%dT%H:%M:%S')
            return dt.replace(tzinfo=timezone.utc).astimezone()
        except ValueError:
            pass
    return None


def extract_time_from_span(span):
    """从 Discourse 的 span.relative-date 提取时间
    data-time 是 epoch 毫秒，data-title 是格式化时间文本
    """
    data_time = span.get('data-time')
    if data_time:
        try:
            epoch = int(data_time) / 1000.0
            return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
        except (ValueError, OSError):
            pass

    data_title = span.get('data-title', '')
    if data_title:
        dt = parse_discourse_title_time(data_title)
        if dt:
            return dt

    text = span.get_text(strip=True)
    if text:
        dt = parse_discourse_title_time(text)
        if dt:
            return dt
    return None


def extract_time_from_element(el):
    """从 td 等元素提取时间"""
    data_time = el.get('data-time')
    if data_time:
        try:
            epoch = int(data_time) / 1000.0
            return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone()
        except (ValueError, OSError):
            pass
    title = el.get('title', '')
    if title:
        dt = parse_discourse_title_time(title)
        if dt:
            return dt
    return None


def parse_discourse_title_time(s):
    """尝试多种格式解析 Discourse 时间字符串"""
    patterns = [
        '%b %d, %Y %I:%M %p',      # Jun 29, 2026 11:25 am
        '%b %d, %Y %H:%M',          # Jun 29, 2026 11:25
        '%b %d, %Y',                # Jun 29, 2026
        '%Y-%m-%d %H:%M:%S',        # 2026-06-29 11:25:26
        '%Y-%m-%d',                 # 2026-06-29
        '%Y年%m月%d日 %H:%M',       # 2026年06月29日 11:25
        '%Y年%m月%d日',             # 2026年06月29日
    ]
    for fmt in patterns:
        try:
            return datetime.strptime(s.strip(), fmt).astimezone()
        except ValueError:
            continue
    m = re.search(r'(\w{3}\s+\d{1,2},\s*\d{4}(?:\s+\d{1,2}:\d{2}\s*[ap]m)?)', s)
    if m:
        sub = m.group(1)
        for fmt in ('%b %d, %Y %I:%M %p', '%b %d, %Y'):
            try:
                return datetime.strptime(sub, fmt).astimezone()
            except ValueError:
                continue
    return None


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    forum_url = FORUM_URL
    days = 7

    for a in args:
        if a.startswith('http'):
            forum_url = a
        elif a.isdigit():
            days = int(a)

    print("=" * 60)
    print(f"  RuyiSDK 论坛帖子爬取工具")
    print(f"  目标: {forum_url}")
    print(f"  时间范围: 最近 {days} 天")
    print("=" * 60)

    results = []

    # 方法1: JSON 接口
    print("\n>>> 尝试 JSON 接口 (/latest.json)...")
    try:
        topics = fetch_via_json(forum_url)
        if topics:
            results = filter_json_topics(topics, days)
            print(f"  JSON 接口命中 {len(results)} 个帖子")
    except Exception as e:
        print(f"  JSON 接口失败: {e}")

    # 方法2: HTML 解析 (JSON 没结果时回退)
    if not results:
        print("\n>>> JSON 无结果，尝试 HTML 解析...")
        try:
            results = fetch_via_html(forum_url, days)
        except Exception as e:
            print(f"  HTML 解析失败: {e}")

    # 输出结果
    print("\n" + "=" * 60)
    if results:
        print(f"  最近 {days} 天共找到 {len(results)} 个帖子")
        print("=" * 60)
        print()
        for i, p in enumerate(results, 1):
            print(f"{i}. {p['title']}：{p['url']}")
            print(f"   ({p['time_label']})")
        print()
        print(f"共 {len(results)} 条")
    else:
        print("  未找到符合条件的帖子")
        print("=" * 60)
        print()
        print("排查建议:")
        print("  1. 确认网络已通: ping ruyisdk.cn")
        print("  2. 手动检查: curl -s https://ruyisdk.cn/latest.json | head -200")
        print("  3. 查看帖子实际时间格式")


if __name__ == '__main__':
    main()
