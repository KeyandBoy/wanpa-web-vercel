"""51吃瓜网（cg51）源。

能力：
  * resolve_base()  自动跟随最新域名（读「最新网址」页 + 重定向，失败回退 CG51_BASE）
  * search_posts()  关键词搜索，返回帖子（列表卡片）
  * post_images()   进帖抓取该帖全部图片（data-xkrkllgl 属性）
  * post_video()    进帖解析视频（data-config -> video.url -> m3u8/HLS）
  * maybe_decrypt() 图片 AES-128-CBC 解密（key/iv 写死于站点 JS，按内容魔数判定）

默认直连（国内可达），如需代理请在 .env 配 CG51_PROXY=。
"""

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlparse


def env_utils_get(key, default=None):
    """读取配置（os.environ -> KV 用户配置 -> .env -> .env.local）。"""
    from env_utils import env as _env

    return _env(key, default)


DEFAULT_BASE = "https://basis.qvujkzrd.cc/"

_AES_KEY = b"f5d965df75336270"
_AES_IV = b"97b60394abc2fbe1"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_BASE_TTL = 6 * 3600
_HOST_TTL = 6 * 3600
_POSTS_PER_PAGE = 25

_lock = threading.Lock()
_state = {"base": "", "ts": 0.0}
_known_hosts = {}
_post_re = re.compile(r'id="post-card-(\d+)"')
_archive_re = re.compile(r'href="(/archives/(\d+)/)"')
_title_re = re.compile(r"<h2[^>]*class=\"post-card[^\"]*\"[^>]*>(.*?)</h2>", re.S)
_img_re = re.compile(r'data-xkrkllgl="([^"]+)"')
_cfg_re = re.compile(r"data-config='([^']*)'")
_cover_re = re.compile(r"loadBannerDirect\('([^']+)'")
_page_title_re = re.compile(r"<title>(.*?)</title>", re.S)
_mirror_res = [
    re.compile(
        r'(?:官网|新域名|备用域名|最新域名|官方域名|备用网址|当前域名|导航地址)[：:]\s*'
        r'<a[^>]+href="(https?://[^"]+)"',
        re.I,
    ),
    re.compile(r'<a[^>]+href="(https?://[^"/]+/?)"[^>]*>\s*https?://\S*?\s*</a>'),
]

_MIRROR_SKIP_PREFIX = ("pic.", "hls.", "img.", "static.", "cdn.", "w3.org", "schema.org")


# ---------------------------------------------------------------- 基础设施
def _norm_base(u):
    u = (u or "").strip()
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u if u.endswith("/") else u + "/"


def configured_base():
    v = (os.environ.get("CG51_BASE") or "").strip()
    if not v:
        try:
            v = (env_utils_get("CG51_BASE") or "").strip()
        except Exception:
            v = ""
    return _norm_base(v) or DEFAULT_BASE


def _proxy():
    for k in ("CG51_PROXY",):
        v = (os.environ.get(k) or "").strip()
        if v:
            return v
    try:
        v = (env_utils_get("CG51_PROXY") or "").strip()
        if v:
            return v
    except Exception:
        pass
    return ""


def _get(url, timeout=30, headers=None):
    from curl_cffi import requests as cr

    hdr = {"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9", "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    p = _proxy()
    proxies = {"http": p, "https": p} if p else None
    return cr.get(
        url, headers=hdr, impersonate="chrome", timeout=timeout,
        proxies=proxies, allow_redirects=True,
    )


def _text(url, timeout=30, headers=None):
    r = _get(url, timeout=timeout, headers=headers)
    if getattr(r, "status_code", 0) != 200:
        raise ValueError("cg51 请求失败(HTTP %d): %s" % (r.status_code, url))
    return r.text


def _abs(u):
    base = resolve_base()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith(("http://", "https://")):
        return u
    return base + u.lstrip("/")


def _looks_site(html):
    return ("post-card" in html) or ("Mirages" in html) or ("/action/search_by" in html)


# ---------------------------------------------------------- 域名自动跟随
def _probe(url):
    try:
        r = _get(url, timeout=15)
    except Exception:
        return None
    if getattr(r, "status_code", 0) != 200:
        return None
    try:
        html = r.text
    except Exception:
        return None
    if not _looks_site(html):
        return None
    final = _norm_base(getattr(r, "url", "") or url)
    return final if final else None


def _discover(seed):
    """从站点首页提取「官网/新域名/备用域名」等镜像地址。"""
    out = []
    try:
        html = _text(seed, timeout=15)
    except Exception:
        return out
    for pat in _mirror_res:
        for m in pat.finditer(html):
            u = _norm_base(m.group(1))
            host = (urlparse(u).hostname or "").lower()
            if not host or host.startswith(_MIRROR_SKIP_PREFIX):
                continue
            if u not in out:
                out.append(u)
    return out


def resolve_base(force=False):
    """返回当前可用的站点根地址（带尾部 /），6 小时缓存。"""
    now = time.time()
    with _lock:
        if not force and _state["base"] and now - _state["ts"] < _BASE_TTL:
            return _state["base"]

    seed = configured_base()
    final = _probe(seed)
    if final:
        _remember(final)
        with _lock:
            _state["base"], _state["ts"] = final, time.time()
        return final

    for cand in _discover(seed)[:5]:
        if cand == seed:
            continue
        final = _probe(cand)
        if final:
            _remember(final)
            with _lock:
                _state["base"], _state["ts"] = final, time.time()
            return final

    with _lock:
        _state["base"], _state["ts"] = seed, time.time()
    _remember(seed)
    return seed


def _remember(base):
    host = (urlparse(base).hostname or "").lower()
    if host:
        _known_hosts[host] = time.time()


def _forget(host):
    host = (host or "").lower()
    with _lock:
        _known_hosts.pop(host, None)


def is_cdn_url(url):
    """cg51 图片 CDN（内容走 AES 加密），按 host 前缀判断。"""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    if host.startswith("pic.") or ".ndhixj.cn" in host or ".sqbcn.cn" in host or ".huyaohj.cn" in host:
        return True
    return host in _known_hosts and host != (urlparse(resolve_base()).hostname or "").lower()


def is_post_url(url, probe=True):
    """是否 cg51 帖子页（/archives/{id}/）。host 未知时探一次站点标记。"""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    if not re.match(r"^/archives/\d+/?$", p.path or ""):
        return False
    host = (p.hostname or "").lower()
    if not host:
        return False
    if host in _known_hosts:
        return True
    if host == (urlparse(configured_base()).hostname or "").lower():
        _remember(configured_base())
        return True
    if not probe:
        return False
    final = _probe("https://%s/" % host)
    if final:
        _remember(final)
        return True
    return False


# ------------------------------------------------------------------ 图片解密
_IMAGE_MAGIC = (
    b"\xff\xd8\xff",          # JPEG
    b"\x89PNG\r\n\x1a\n",     # PNG
    b"GIF8",                  # GIF
    b"RIFF",                  # WEBP
    b"BM",                    # BMP
    b"II*\x00",               # TIFF LE
    b"MM\x00*",               # TIFF BE
    b"\x00\x00\x01\x00",      # ICO
)


def _looks_image(data):
    if not data:
        return False
    for mag in _IMAGE_MAGIC:
        if data.startswith(mag):
            return True
    if len(data) > 12 and data[4:8] == b"ftyp":
        return True
    return False


def sniff_media_type(data):
    """按魔数猜 MIME（cg51 CDN 返回 binary/octet-stream，需自行识别）。"""
    if not data:
        return ""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"BM"):
        return "image/bmp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "image/avif"
    if data.startswith(b"\x00\x00\x01\x00"):
        return "image/x-icon"
    return ""


def maybe_decrypt(data, url=None):
    """内容不是图片且 16 字节对齐时尝试 AES-128-CBC 解密；解出来仍不是图片则原样返回。

    纯按内容判定，不依赖域名（CDN 域名会轮换）。
    """
    if not data or len(data) % 16:
        return data
    if _looks_image(data):
        return data
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        dec = Cipher(algorithms.AES(_AES_KEY), modes.CBC(_AES_IV)).decryptor()
        out = dec.update(data) + dec.finalize()
    except Exception:
        return data
    pad = out[-1] if out else 0
    if 1 <= pad <= 16 and out.endswith(bytes([pad]) * pad):
        out = out[: -pad]
    if _looks_image(out):
        return out
    return data


# ------------------------------------------------------------------ 帖子搜索
def _parse_cards(html):
    hrefs = {}
    for m in _archive_re.finditer(html):
        hrefs.setdefault(m.group(2), m.group(1))
    out, seen = [], set()
    for m in _post_re.finditer(html):
        pid = m.group(1)
        if pid in seen or pid not in hrefs:
            continue
        seen.add(pid)
        seg = html[max(0, m.start() - 1500): m.start() + 3000]
        title = ""
        tm = _title_re.search(seg) or _title_re.search(html[m.start(): m.start() + 4000])
        if tm:
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        cm = _cover_re.search(seg)
        cover = _abs(cm.group(1)) if cm else ""
        out.append({
            "url": _abs(hrefs[pid]),
            "id": pid,
            "title": title,
            "thumbnail": cover,
            "cover": cover,
            "source": "cg51",
            "kind": "album",
        })
    return out


def search_posts(keyword, page=1, timeout=25):
    """按关键词搜帖子。page 从 1 开始（1 = /search/kw/，N = /search/kw/N/）。"""
    kw = (keyword or "").strip()
    if not kw:
        return []
    try:
        page = int(page or 1)
    except (TypeError, ValueError):
        page = 1
    seg = quote(kw[:40], safe="")
    path = "search/%s/" % seg if page <= 1 else "search/%s/%d/" % (seg, page)
    html = _text(_abs(path), timeout=timeout, headers={"Referer": resolve_base()})
    posts = _parse_cards(html)
    for p in posts:
        _remember(p["url"])
    return posts


# ------------------------------------------------------------------ 进帖抓取
def _post_title(html, url):
    m = _page_title_re.search(html or "")
    if not m:
        return url
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    for sep in (" | 51吃瓜网", " - 51吃瓜网", "| 51吃瓜网"):
        if sep in t:
            t = t.split(sep)[0].strip()
    return t.strip(" -_|·") or url


def post_images(url, timeout=25):
    """进帖抓取该帖全部图片地址（未解密的 CDN 直链）。返回 (urls, title)。"""
    html = _text(url, timeout=timeout, headers={"Referer": resolve_base()})
    title = _post_title(html, url)
    out, seen = [], set()
    for m in _img_re.finditer(html):
        u = m.group(1).replace("&amp;", "&").strip()
        if not u:
            continue
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = _abs(u)
        elif not u.startswith(("http://", "https://")):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    if out:
        _remember(url)
    return out, title


def _load_config(html):
    m = _cfg_re.search(html or "")
    if not m:
        return None
    raw = m.group(1).strip()
    for candidate in (raw, raw.replace("\\/", "/")):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def post_video(url, timeout=25):
    """进帖解析视频，返回 {url: m3u8, title, ...}；无视频返回 None。"""
    html = _text(url, timeout=timeout, headers={"Referer": resolve_base()})
    cfg = _load_config(html)
    if not isinstance(cfg, dict):
        return None
    v = cfg.get("video") or {}
    play = (v.get("url") or "").strip()
    if not play:
        return None
    _remember(url)
    h265 = cfg.get("video_h265") or {}
    return {
        "url": play,
        "title": _post_title(html, url),
        "source": "cg51",
        "stage": "site",
        "source_url": url,
        "is_hls": True,
        "type": v.get("type") or "hls",
        "alt": (h265.get("url") or "").strip() if isinstance(h265, dict) else "",
        "candidates": [
            {"url": play, "ext": "m3u8", "kind": "hls", "quality": "",
             "label": "HLS", "from": "cg51"}
        ],
    }


# ------------------------------------------------------------------ 上层封装
def search_album_images(keyword, page=1, count=60, max_posts=12, workers=4):
    """图片模块：搜帖子 -> 进帖抓全部图 -> 扁平图片列表。返回 (items, has_more)。"""
    posts = search_posts(keyword, page=page)
    if not posts:
        return [], False
    limit = int(count or 60)
    need = max(4, min(len(posts), max_posts, -(-limit // 6)))
    chosen = posts[:need]

    def work(p):
        try:
            urls, title = post_images(p["url"])
            return p, urls, title
        except Exception:
            return p, [], p.get("title") or ""

    items, seen = [], set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for p, urls, title in pool.map(work, chosen):
            for u in urls:
                if u in seen:
                    continue
                seen.add(u)
                items.append({
                    "url": u,
                    "title": title or p.get("title") or "",
                    "width": None,
                    "height": None,
                    "source": "cg51",
                    "album": p["url"],
                })
                if len(items) >= limit:
                    return items, True
    return items, True


def search_video_posts(keyword, count=10):
    """视频模块：帖子即视频，返回 yt-dlp 风格条目（url 为帖子地址，resolve 时取 m3u8）。"""
    count = max(1, min(int(count or 10), 60))
    posts, page = [], 1
    while len(posts) < count and page <= 3:
        batch = search_posts(keyword, page=page)
        if not batch:
            break
        posts.extend(batch)
        page += 1
    out = []
    for p in posts[:count]:
        out.append({
            "title": (p.get("title") or "cg51 视频")[:200],
            "url": p["url"],
            "duration": None,
            "duration_text": "",
            "thumb": p.get("thumbnail") or None,
            "source": "cg51",
        })
    return out


def reset_base():
    """清空域名缓存（域名失效时调用）。"""
    with _lock:
        _state["base"], _state["ts"] = "", 0.0
    _known_hosts.clear()
