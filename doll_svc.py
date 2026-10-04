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
    """抓页面（不带 Referer），手动跟随跳转。

    源站对 `/search/<关键词>`（缺尾斜杠）会回 301，而 Location 被站方配置写成了
    `https://host:65037/...` —— 客户端照着连那个端口只会超时，然后报一串看不懂的
    连接池错误。这里先按标准端口纠正 Location 再跳；端口/主机不正常的直接拒绝。
    """
    proxies = {"http": _proxy(), "https": _proxy()} if _proxy() else None
    headers = {"User-Agent": _UA}
    from urllib.parse import urljoin, urlparse, urlunparse

    cur = url
    for _ in range(6):
        r = requests.get(
            cur,
            headers=headers,
            timeout=timeout,
            proxies=proxies,
            allow_redirects=False,
        )
        if r.status_code not in (301, 302, 303, 307, 308):
            break
        loc = (r.headers.get("Location") or "").strip()
        if not loc:
            break
        nxt = urljoin(cur, loc)
        p = urlparse(nxt)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("源站返回了异常跳转 %s（疑似反爬陷阱），已拒绝跟随后继续" % nxt)
        if p.port and p.port not in (80, 443):
            nxt = urlunparse(p._replace(netloc=p.hostname))
        cur = nxt
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
        # 带尾斜杠：缺斜杠时源站回 301，且 Location 会被写成带 :65037 的坏地址
        url = SITE + "/search/" + _sanitize_kw(keyword) + "/"
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

