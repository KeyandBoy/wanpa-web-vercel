"""玩偶姐姐 / 麻豆系成人视频源（hongkongdollvideo.com）。

- 列表/搜索：静态解析 video-item 卡片（标题/缩略图/链接）
- 播放地址：不再使用 Playwright，改由 resolve_video 的 yt-dlp / 页面嗅探回落

参考 TVSpider 的 doll.js 思路；Vercel 上已移除浏览器依赖。
"""

import os
import re
import threading

import requests

from trans_svc import to_zh

BASE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://hongkongdollvideo.com"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"



def _proxy():
    """出站代理。Vercel 上由 PROXY 环境变量或「设置」面板提供。"""
    from env_utils import proxy as _env_proxy

    return _env_proxy()


def _fetch(url, timeout=20):
    proxies = {"http": _proxy(), "https": _proxy()} if _proxy() else None
    r = requests.get(
        url,
        headers={"User-Agent": _UA, "Referer": SITE + "/"},
        timeout=timeout,
        proxies=proxies,
    )
    r.raise_for_status()
    return r


def _t2s(text):
    """繁体转简体（复用 opencc，若不可用原样返回）"""
    try:
        from opencc import OpenCC
        return OpenCC("t2s").convert(text or "")
    except Exception:
        return text or ""


def search_doll(keyword, count):
    """搜索玩偶姐姐视频（默认展示最新）"""
    items = []
    if keyword:
        url = SITE + "/search/" + _sanitize_kw(keyword)
    else:
        url = SITE
    try:
        r = _fetch(url)
    except Exception as e:
        raise ValueError(f"玩偶姐姐访问失败: {e}") from e
    seen = set()
    for m in re.finditer(
        r'<div class="video-item">\s*<div class="thumb">\s*<a[^>]+title="([^"]*)"[^>]+href="([^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"',
        r.text,
    ):
        title, href, img = m.group(1), m.group(2), m.group(3)
        if href in seen:
            continue
        seen.add(href)
        full_url = href if href.startswith("http") else SITE + href
        items.append({
            "title": _t2s(title)[:200],
            "url": full_url,
            "thumb": img,
            "source": "doll",
        })
        if len(items) >= count:
            break
    if not items:
        raise ValueError("玩偶姐姐没有搜索到结果")
    # 翻译标题为中文（已是中文则跳过）
    for it in items:
        try:
            zh = to_zh(it["title"])
            if zh and zh != it["title"]:
                it["title"] = zh[:200]
        except Exception:
            pass
    return items


def _sanitize_kw(kw):
    from urllib.parse import quote
    kw = (kw or "").strip()
    kw = re.sub(r"\s+", "+", kw)
    kw = re.sub(r"[^A-Za-z0-9\u4e00-\u9fa5+]+", "", kw)
    return quote(kw, safe="+")

