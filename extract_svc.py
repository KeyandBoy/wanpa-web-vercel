"""链接下载 S2.5：服务端 HTML 媒体嗅探（Downie 风格，无需浏览器）。

只负责「抓页面 + 找地址 + 打分排序」，不负责下载。
不 import video_svc，避免循环依赖。
"""

import html as html_mod
import os
import re
from urllib.parse import urljoin, urlparse

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

_MEDIA_EXT_RE = re.compile(r"\.(m3u8|mp4|webm|mpd|flv|mov|m4v)(?:$|[?#])", re.I)
_NON_MEDIA_EXT_RE = re.compile(
    r"\.(?:jpg|jpeg|png|gif|webp|svg|ico|css|js|mjs|json|html?|xml|woff2?|ttf|mp3|aac|ogg|wav)(?:$|[?#])",
    re.I,
)

_TRUSTED_KINDS = ("video-tag", "meta", "player", "js-key")


def _proxy():
    """出站代理。Vercel 上由 PROXY 环境变量或「设置」面板提供。"""
    from env_utils import proxy as _env_proxy

    return _env_proxy()


def _proxy_dict():
    p = _proxy()
    return {"http": p, "https": p} if p else None


_DOMESTIC_HOSTS = (
    "bilibili.com",
    "bilivideo.com",
    "hdslb.com",
    "youku.com",
    "acfun.cn",
    "mgtv.com",
    "hitv.com",
    "sohu.com",
    "qq.com",
    "iqiyi.com",
    "douyin.com",
    "iesdouyin.com",
    "ixigua.com",
    "baidu.com",
    "hupu.com",
    "hoopchina.com.cn",
    "phncdn.com",
)


def _is_domestic(url):
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(host == h or host.endswith("." + h) for h in _DOMESTIC_HOSTS)


def _headers(referer=None):
    h = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        h["Referer"] = referer
    return h


def _get_text(url, headers, timeout):
    """按 [代理, 直连] 顺序尝试 requests → curl_cffi，返回 HTML 或 None"""
    attempts = [None]
    if not _is_domestic(url):
        pd = _proxy_dict()
        if pd:
            attempts = [pd, None]
    for proxies in attempts:
        try:
            import requests

            r = requests.get(url, headers=headers, timeout=timeout, proxies=proxies, allow_redirects=True)
            if r.status_code == 200 and r.text and len(r.text) > 20:
                return r.text
        except Exception:
            pass
    for proxies in attempts:
        try:
            from curl_cffi import requests as creq

            kw = {"headers": headers, "timeout": timeout, "impersonate": "chrome131", "allow_redirects": True}
            if proxies:
                kw["proxies"] = proxies
            r = creq.get(url, **kw)
            if getattr(r, "status_code", 200) == 200 and r.text and len(r.text) > 20:
                return r.text
        except Exception:
            pass
    return None


def fetch_html(url, referer=None, timeout=20):
    """抓页面 HTML：requests 优先，失败回退 curl_cffi（更像浏览器）。返回 str 或 None"""
    if not url:
        return None
    return _get_text(url, _headers(referer), timeout)


def _normalize(text):
    """还原 JS/HTML 转义，让正则能命中被混淆的地址"""
    if not text:
        return ""
    t = text.replace("\\/", "/")
    t = re.sub(r"\\u002[fF]", "/", t)
    t = re.sub(r"\\u0026", "&", t)
    t = re.sub(r"\\u003[dD]", "=", t)
    t = re.sub(r"\\u003[fF]", "?", t)
    t = re.sub(r"\\x2[fF]", "/", t)
    t = html_mod.unescape(t)
    return t


_PATTERNS = [
    # 1. <video>/<source> 标签
    (re.compile(r"<(?:video|source)\b[^>]*?\ssrc\s*=\s*[\"']([^\"']+)[\"']", re.I), "video-tag"),
    # 2. og:video / twitter:player meta
    (
        re.compile(
            r"<meta\b[^>]*?(?:property|name)\s*=\s*[\"'](?:og:video(?::secure_url)?|twitter:player(?::stream)?)?[\"']"
            r"[^>]*?content\s*=\s*[\"']([^\"']+)[\"']",
            re.I,
        ),
        "meta",
    ),
    (
        re.compile(
            r"<meta\b[^>]*?content\s*=\s*[\"']([^\"']+)[\"'][^>]*?"
            r"(?:property|name)\s*=\s*[\"'](?:og:video(?::secure_url)?|twitter:player(?::stream)?)?[\"']",
            re.I,
        ),
        "meta",
    ),
    # 3. 整页绝对地址正则
    (
        re.compile(
            r"https?://[^\s\"'<>\\)]+?\.(?:m3u8|mp4|webm|mpd|flv|mov|m4v)(?:\?[^\s\"'<>\\)]*)?",
            re.I,
        ),
        "regex",
    ),
    # 4. JS/JSON 键值（相对地址很常见，靠 key 可信度判断）
    (
        re.compile(
            r"[\"'](?:file|src|url|playUrl|play_url|playAddr|play_addr|video_url|videoUrl|video_src|videoSrc"
            r"|hlsUrl|hls_url|mp4Url|mp4_url|source|contentUrl|content_url|stream|playlist)[\"']"
            r"\s*[:=]\s*[\"']([^\"']+)[\"']",
            re.I,
        ),
        "js-key",
    ),
    # 5. 播放器初始化（jwplayer / videojs / hls.js / artplayer / dplayer）
    (
        re.compile(
            r"(?:jwplayer\s*\([^)]*\)\s*\.\s*setup\s*\(|videojs\s*\([^)]*\)\s*\.\s*src\s*\(|"
            r"hls\s*\.\s*loadSource\s*\(|\.setup\s*\(\s*\{)",
            re.I,
        ),
        "player",
    ),
]

_PLAYER_FILE_RE = re.compile(
    r"\.setup\s*\(\s*\{[^{}]*?[\"']file[\"']\s*:\s*[\"']([^\"']+)[\"']",
    re.I,
)
_IFRAME_RE = re.compile(r"<iframe\b[^>]*?\ssrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)

_SKIP_HOST_HINTS = (
    "doubleclick",
    "googlesyndication",
    "googleadservices",
    "adservice",
    "/ads/",
    "analytics",
    "beacon",
)


def _absolutize(page_url, raw):
    u = (raw or "").strip().strip("'\"").strip()
    if not u or u.startswith(("data:", "blob:", "javascript:", "#")):
        return None
    if u.startswith("//"):
        u = "https:" + u
    if not u.startswith(("http://", "https://")):
        try:
            u = urljoin(page_url, u)
        except Exception:
            return None
    if not u.startswith(("http://", "https://")):
        return None
    return u


def _ext_of(u):
    m = _MEDIA_EXT_RE.search(u.split("#")[0])
    return (m.group(1).lower() if m else "unknown")


def _quality_of(u):
    m = re.search(r"(\d{3,4})\s*p\b", u, re.I)
    if m:
        return f"{m.group(1)}p"
    m = re.search(r"[/_-](\d{3,4})[/_-]", u)
    if m and 144 <= int(m.group(1)) <= 2160:
        return f"{m.group(1)}p"
    return ""


def sniff_sources(page_url, html):
    """从单个页面 HTML 里提取候选媒体地址，返回未排序的 dict 列表"""
    if not html:
        return []
    text = _normalize(html)
    raw_found = []

    def add(raw, kind):
        u = _absolutize(page_url, raw)
        if not u:
            return
        has_ext = bool(_MEDIA_EXT_RE.search(u.split("#")[0]))
        if not has_ext:
            if kind not in _TRUSTED_KINDS:
                return
            if _NON_MEDIA_EXT_RE.search(u.split("#")[0]):
                return
        raw_found.append((u, kind))

    # 模式 5 的 .setup({file:...}) 单独兜一层
    for m in _PLAYER_FILE_RE.finditer(text):
        add(m.group(1), "player")

    for rx, kind in _PATTERNS:
        if kind == "player":
            # 已由 _PLAYER_FILE_RE 处理，避免重复
            continue
        for m in rx.finditer(text):
            add(m.group(1) if m.re.groups else m.group(0), kind)

    # 协议相对地址 //cdn.example.com/x.mp4
    for m in re.finditer(r"//([^\s\"'<>]+?\.(?:m3u8|mp4|webm|mpd|flv|mov|m4v)(?:\?[^\s\"'<>]*)?)", text, re.I):
        add("https://" + m.group(1), "regex")

    seen = set()
    out = []
    for u, kind in raw_found:
        if u in seen:
            continue
        seen.add(u)
        out.append(
            {
                "url": u,
                "ext": _ext_of(u),
                "kind": kind,
                "quality": _quality_of(u),
                "from": urlparse(u).netloc.lower(),
            }
        )
    return out


def sniff_iframes(page_url, html):
    """返回页面内 iframe 地址（供 1 层递归）"""
    if not html:
        return []
    out = []
    for m in _IFRAME_RE.finditer(_normalize(html)):
        u = _absolutize(page_url, m.group(1))
        if not u or not u.startswith("http"):
            continue
        low = u.lower()
        if any(h in low for h in _SKIP_HOST_HINTS):
            continue
        if u not in out:
            out.append(u)
    return out


def sniff_page(url, depth=0, max_depth=1, max_iframes=3, seen=None):
    """抓页面嗅探候选地址；depth<max_depth 时递归 iframe 一层"""
    if seen is None:
        seen = {url}
    html = fetch_html(url)
    cands = sniff_sources(url, html)
    if depth < max_depth and html:
        n = 0
        for iframe in sniff_iframes(url, html):
            if n >= max_iframes:
                break
            if iframe in seen:
                continue
            seen.add(iframe)
            n += 1
            try:
                cands.extend(sniff_page(iframe, depth + 1, max_depth, max_iframes, seen))
            except Exception:
                continue
    return cands


def _score(c):
    u = c["url"].lower()
    kind = c.get("kind") or ""
    s = 0
    if ".m3u8" in u:
        s += 50
    elif ".mp4" in u:
        s += 40
    elif ".webm" in u:
        s += 35
    elif ".mpd" in u:
        s += 30
    elif ".flv" in u:
        s += 25
    if u.startswith("https://"):
        s += 10
    if c.get("quality"):
        s += 8
    if "master" in u or "playlist" in u:
        s += 5
    if kind in ("video-tag", "meta", "player"):
        s += 12
    elif kind == "js-key":
        s += 6
    elif kind == "regex":
        s += 2
    if any(x in u for x in ("preview", "thumb", "sample", "trailer")):
        s -= 15
    if any(x in c.get("from", "") for x in _SKIP_HOST_HINTS):
        s -= 50
    return s


def _label(c):
    ext = c.get("ext") or ""
    q = c.get("quality") or ""
    kind = c.get("kind") or ""
    kind_cn = {
        "video-tag": "video标签",
        "meta": "og元数据",
        "player": "播放器",
        "js-key": "JS变量",
        "regex": "整页正则",
        "ytdlp": "yt-dlp",
        "browser": "浏览器",
        "direct": "直链",
    }.get(kind, kind or "-")
    parts = [x for x in (q, ext if ext != "unknown" else "", kind_cn) if x]
    return " · ".join(parts)


def score_and_dedup(cands, limit=8):
    """按可信度/格式打分排序并去重，返回带 label 的候选列表"""
    if not cands:
        return []
    uniq = {}
    for c in cands:
        if c and c.get("url"):
            uniq.setdefault(c["url"], c)
    ordered = sorted(uniq.values(), key=_score, reverse=True)
    out = []
    for c in ordered[:limit]:
        item = dict(c)
        item["label"] = _label(c)
        item["kind"] = c.get("kind") or "unknown"
        out.append(item)
    return out


def candidates_from_urls(urls, kind="browser", page_url=None):
    """把一串已抓到的媒体地址包装成候选列表（浏览器抓包/直链用）"""
    out = []
    for u in urls or []:
        if not u:
            continue
        out.append(
            {
                "url": u,
                "ext": _ext_of(u),
                "kind": kind,
                "quality": _quality_of(u),
                "from": urlparse(u).netloc.lower(),
            }
        )
    return score_and_dedup(out)


def media_kind(url):
    """返回 'hls' | 'direct' | 'unknown'，供下载路由使用"""
    if not url:
        return "unknown"
    u = url.split("#")[0]
    if re.search(r"\.m3u8(?:$|[?])", u, re.I):
        return "hls"
    if re.search(r"\.(?:mp4|webm|mpd|flv|mov|m4v)(?:$|[?])", u, re.I):
        return "direct"
    return "unknown"


def guess_title(page_url, html=None):
    if html:
        m = _TITLE_RE.search(html)
        if m:
            t = html_mod.unescape(m.group(1)).strip()
            t = re.sub(r"\s+", " ", t)
            if t:
                return t[:200]
    try:
        path = urlparse(page_url).path.rstrip("/")
        seg = path.rsplit("/", 1)[-1] if path else ""
        if seg:
            from urllib.parse import unquote

            seg = unquote(seg)
            seg = re.sub(r"\.(html?|php|aspx?)$", "", seg, flags=re.I)
            seg = re.sub(r"[-_]+", " ", seg).strip()
            if seg:
                return seg[:200]
    except Exception:
        pass
    return "video"
