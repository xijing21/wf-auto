# -*- coding: utf-8 -*-
"""
RuyiSDK 论坛帖子爬取
- 优先 Discourse /latest.json 接口，回退 HTML 解析
- 创建时间优先，无则用 activity 时间
- 被 feishu-chatbox/main.py 调用：from utils.crawler import get_ruyisdk_posts
"""

import json
import re
from datetime import datetime, timedelta, timezone

import requests

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except ImportError:
    _HAS_BS4 = False

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")


# ──────────────────────────────────────────────
# 时间解析（内部工具）
# ──────────────────────────────────────────────
def _parse_iso(iso_str):
    """解析 Discourse ISO 时间 2026-06-29T11:25:26.479Z"""
    if not iso_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(iso_str, fmt).replace(
                tzinfo=timezone.utc).astimezone()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", iso_str)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=timezone.utc).astimezone()
        except ValueError:
            pass
    return None


def _parse_epoch_ms(epoch_str):
    if not epoch_str:
        return None
    try:
        return datetime.fromtimestamp(
            int(epoch_str) / 1000.0, tz=timezone.utc).astimezone()
    except (ValueError, OSError):
        return None


def _parse_text_time(s):
    if not s:
        return None
    for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %H:%M", "%b %d, %Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%Y年%m月%d日 %H:%M", "%Y年%m月%d日"):
        try:
            return datetime.strptime(s.strip(), fmt).astimezone()
        except ValueError:
            continue
    m = re.search(
        r"(\w{3}\s+\d{1,2},\s*\d{4}(?:\s+\d{1,2}:\d{2}\s*[ap]m)?)", s)
    if m:
        for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y"):
            try:
                return datetime.strptime(m.group(1), fmt).astimezone()
            except ValueError:
                continue
    return None


# ──────────────────────────────────────────────
# 通道1: JSON 接口
# ──────────────────────────────────────────────
def _fetch_topics_json(forum_url, max_pages=5):
    base = forum_url.rstrip("/")
    topics, url = [], base + "/latest.json"
    headers = {"User-Agent": UA, "Accept": "application/json"}
    for _ in range(max_pages):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            break
        batch = data.get("topic_list", {}).get("topics", [])
        if not batch:
            break
        topics.extend(batch)
        more = data.get("topic_list", {}).get("more_topics_url")
        if not more:
            break
        url = base + more if more.startswith("/") else more
    return topics


def _filter_json_topics(topics, days, forum_url):
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)
    base = forum_url.rstrip("/")
    results = []
    for t in topics:
        if t.get("pinned") or t.get("pinned_globally"):
            continue
        created_dt = _parse_iso(t.get("created_at", ""))
        activity_dt = _parse_iso(
            t.get("last_posted_at", "") or t.get("bumped_at", ""))
        if created_dt and created_dt >= start:
            use_dt, label = created_dt, f"创建: {created_dt:%Y-%m-%d %H:%M}"
        elif activity_dt and activity_dt >= start:
            use_dt, label = activity_dt, f"活动: {activity_dt:%Y-%m-%d %H:%M}"
        else:
            continue
        results.append({
            "title": t.get("title", "无标题"),
            "link": f"{base}/t/topic/{t.get('id', '')}",
            "time": use_dt.strftime("%Y-%m-%d %H:%M"),
            "time_label": label,
            "_sort": use_dt,
        })
    results.sort(key=lambda x: x["_sort"], reverse=True)
    for r in results:
        r.pop("_sort", None)
    return results


# ──────────────────────────────────────────────
# 通道2: HTML 解析（回退）
# ──────────────────────────────────────────────
def _extract_time_from_span(span):
    dt = _parse_epoch_ms(span.get("data-time"))
    if dt:
        return dt
    dt = _parse_text_time(span.get("data-title", ""))
    if dt:
        return dt
    return _parse_text_time(span.get_text(strip=True))


def _fetch_topics_html(forum_url, days):
    if not _HAS_BS4:
        return []
    base = forum_url.rstrip("/")
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)
    headers = {"User-Agent": UA}
    results = []
    for page in range(1, 6):
        url = f"{base}/latest" if page == 1 else f"{base}/latest?page={page}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except Exception:
            break
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr", class_="topic-list-item") \
            or soup.select("tr[data-topic-id]")
        if not rows:
            break
        for row in rows:
            link_el = (row.find("a", class_="title")
                       or row.find("a", class_="raw-link")
                       or row.find("a", class_="raw-topic-link"))
            if not link_el:
                main_td = row.find("td", class_="main-link")
                link_el = main_td.find("a") if main_td else None
            if not link_el:
                continue
            title = link_el.get_text(strip=True)
            href = link_el.get("href", "")
            if not title or not href:
                continue
            if "pinned" in row.get("class", []) or "sticky" in row.get("class", []):
                continue
            link = href if href.startswith("http") else base + href

            time_dt = None
            for span in row.find_all("span", class_="relative-date"):
                if "creat" in span.get("data-title", "").lower():
                    time_dt = _extract_time_from_span(span)
                    if time_dt:
                        break
            if not time_dt:
                activity_td = row.find("td", class_="activity")
                if activity_td:
                    span = activity_td.find("span", class_="relative-date")
                    if span:
                        time_dt = _extract_time_from_span(span)
                    else:
                        time_dt = (_parse_epoch_ms(activity_td.get("data-time"))
                                   or _parse_text_time(activity_td.get("title", "")))
            if not time_dt:
                any_span = row.find("span", class_="relative-date")
                if any_span:
                    time_dt = _extract_time_from_span(any_span)
            if not time_dt:
                continue
            if time_dt >= start:
                results.append({
                    "title": title,
                    "link": link,
                    "time": time_dt.strftime("%Y-%m-%d %H:%M"),
                    "time_label": f"时间: {time_dt:%Y-%m-%d %H:%M}",
                    "_sort": time_dt,
                })
    results.sort(key=lambda x: x["_sort"], reverse=True)
    for r in results:
        r.pop("_sort", None)
    return results


# ──────────────────────────────────────────────
# 对外接口（保持函数名与返回契约不变）
# ──────────────────────────────────────────────
def get_ruyisdk_posts(forum_url, days=1):
    """
    获取 ruyisdk.cn 论坛最近 days 天的帖子
    :param forum_url: 论坛地址
    :param days: 最近 N 天，默认 1（今日），向后兼容原有调用
    :return: list[dict]，每项含 title / link，可选 time / time_label
    """
    try:
        topics = _fetch_topics_json(forum_url)
        if topics:
            return _filter_json_topics(topics, days, forum_url)
        return _fetch_topics_html(forum_url, days)
    except Exception as e:
        print(f"爬取失败: {e}")
        return []
