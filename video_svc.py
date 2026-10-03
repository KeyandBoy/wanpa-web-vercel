"""视频搜索 / 解析 / 流式播放（Tier1）。

本模块从 GetPhoto/video_svc.py 裁剪而来，只保留：
- 17 个源的搜索函数
- resolve_video 的 S0(直链) / S1(xhamster) / S2(yt-dlp) / S3(嗅探)
- HLS playlist 改写与分片流式转发、直链 Range 流式转发

已移除（Vercel serverless 不可用）：ffmpeg、本地磁盘、任务队列、
浏览器抓包(S3.5)、cookiesfrombrowser、jable/doll 的浏览器解析。
"""




import concurrent.futures
import glob
import hashlib
import json
import os
import re


import socket


import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

try:
    import yt_dlp
except Exception:
    yt_dlp = None

from trans_svc import to_en, to_zh, translate_many


def _require_yt_dlp():
    if yt_dlp is None:
        raise RuntimeError("本部署未安装 yt-dlp，该源不可用")
    return yt_dlp


_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


MAX_HEIGHT = 1080
FORMAT = f"bv*[height<={MAX_HEIGHT}]+ba/b[height<={MAX_HEIGHT}]/b"

# 通用搜索引擎（bing/yahoo）会带回各种外部站点，这里只留实测能解析出可播放直链的。
# 逐条踩过的坑：douyin/tiktok 要浏览器 JS；iqiyi 页面对所有请求头都返回同一个通用首页，
# 拿不到 data-player-tvid，几个公开接口回 Rule Block。宁可少几条结果，也不给放不了的。
# YouTube 不在这里 —— 它配了 YOUTUBE_COOKIES 就能解析，见 _is_unsupported_video_url。
_UNSUPPORTED_VIDEO_HOSTS = (
    "douyin.com",
    "tiktok.com",
    "iqiyi.com",
)


def _is_unsupported_video_url(url):
    low = (url or "").lower()
    if any(h in low for h in _UNSUPPORTED_VIDEO_HOSTS):
        return True
    if "youtube.com" in low or "youtu.be" in low:
        # 没配 cookie 时 YouTube 必撞 bot 验证（换 client、换 IP 都试过），挡掉；
        # 配上 YOUTUBE_COOKIES 就能解析，bing/yahoo 会自动把 YouTube 结果放回来。
        return _youtube_cookiefile() is None
    return False


def _proxy():
    """出站代理。Vercel 上由 PROXY 环境变量或「设置」面板提供。"""
    from env_utils import proxy as _env_proxy

    return _env_proxy()



def _proxy_dict():
    p = _proxy()
    return {"http": p, "https": p} if p else None


# m3u8 直链 -> 页面 URL 映射（用于给 CDN 分片补正确的 Referer）
_ref_cache = {}
_ref_lock = threading.Lock()


def _note_resolve(page_url, hls_url):
    if not hls_url:
        return
    with _ref_lock:
        _ref_cache[hls_url] = page_url
        if len(_ref_cache) > 3000:
            for k in list(_ref_cache)[:1500]:
                _ref_cache.pop(k, None)


def _referer_for_request(url):
    """分片/m3u8 请求的 Referer（等价 _referer_for，保留旧名兼容）"""
    return _referer_for(url)


def _http_headers_for(url):
    """requests 请求头（UA + Referer + 站点特有头）"""
    headers = {"User-Agent": _UA}
    ref = _referer_for_request(url)
    if ref:
        headers["Referer"] = ref
    headers.update(_extra_headers(url))
    return headers


def _resolve_uri(base, uri):
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri
    return urljoin(base, uri)


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
    "ixigua.com",
    "phncdn.com",
)


def _is_domestic(url):
    if not url:
        return False
    try:
        host = url.split("/")[2].lower()
    except IndexError:
        return False
    return any(host == h or host.endswith("." + h) for h in _DOMESTIC_HOSTS)


def _extra_headers(url):
    """某些 CDN 需要额外请求头才能放行"""
    if not url:
        return {}
    try:
        host = url.split("/")[2].lower()
    except IndexError:
        return {}
    return {}


def _resolve_ytdlp(url):
    """用 yt-dlp 解析播放页（纯 HTTP，不做浏览器 Cookie 读取）。"""
    yt_dlp = _require_yt_dlp()
    opts = dict(_base_opts(url))
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _is_bilibili_page(url):
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(host == h or host.endswith("." + h)
               for h in ("bilibili.com", "bilibili.tv", "b23.tv"))


def _bili_key(target):
    m = re.search(r"/video/(BV[0-9A-Za-z]{10})", target)
    if m:
        return {"bvid": m.group(1)}
    m = re.search(r"/video/av(\d+)", target)
    if m:
        return {"aid": m.group(1)}
    return None


_BILI_ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
_BILI_XOR_CODE = 23442827791579
_BILI_MASK_CODE = 2251799813685247


def _bvid_to_avid(bvid):
    """BV 号转 AV 号（现行算法：第 51 位旗位 + 58 进制 + 两处字符换位）。"""
    if len(bvid) != 12 or not bvid.startswith("BV"):
        raise ValueError("非法 BV 号: %s" % bvid)
    s = list(bvid)
    s[3], s[9] = s[9], s[3]
    s[4], s[7] = s[7], s[4]
    tmp = 0
    for c in s[3:]:
        idx = _BILI_ALPHABET.find(c)
        if idx < 0:
            raise ValueError("非法 BV 号: %s" % bvid)
        tmp = tmp * 58 + idx
    return (tmp & _BILI_MASK_CODE) ^ _BILI_XOR_CODE


def _bili_av_url(url):
    """把 /video/BVxxxx 改写成 /video/av<aid>，并去掉尾斜杠（?p=N 等参数原样保留）。

    两个实测前提，均在同一台 Vercel 机房 IP 上交叉验证：
    1. 抓 /video/av 稳定 200、抓 /video/BV 稳定 412，老视频新视频一视同仁；
    2. 路径带尾斜杠时返回的页面不内嵌 __playinfo__，特判会拿不到 DASH 流。
    """
    m = re.search(r"/video/(BV[0-9A-Za-z]{10}|av\d+)", url)
    if not m:
        return url
    key = m.group(1)
    if key[:2] == "BV":
        try:
            key = "av%d" % _bvid_to_avid(key)
        except Exception:
            return url
    tail = url[m.end(1):]
    if tail[:1] == "/":
        tail = tail[1:]
    return url[:m.start(1)] + key + tail


def _resolve_bilibili(page_url):
    """B站解析：curl_cffi 抓视频页，读内嵌的 window.__playinfo__ 拿 DASH 双流。

    不走 api.bilibili.com 的 view/playurl —— 实测那两个端点对机房 IP 稳定返回
    412 风控页；网页端校验的是 TLS 指纹，curl_cffi 伪装 chrome 能过，而 yt-dlp
    的普通 TLS 会间歇性 412。分 P（?p=N）由页面自行返回对应分 P 的 playinfo，
    无需另查 cid。返回结构复用 _result_from_ytdlp，前端按双元素同步播放。
    """
    from curl_cffi import requests as cr

    sess = cr.Session(impersonate="chrome131", headers={"User-Agent": _UA})
    target = page_url
    if "b23.tv" in urlparse(page_url).netloc:
        target = str(sess.get(page_url, allow_redirects=True, timeout=12).url)
    target = _bili_av_url(target)
    if not _bili_key(target):
        raise ValueError("不是 B站视频链接")

    r = sess.get(target, timeout=20, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bilibili.com/",
    })
    if r.status_code != 200:
        raise ValueError("页面 HTTP %s" % r.status_code)
    html = r.text or ""
    m = re.search(r"window\.__playinfo__\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        raise ValueError("页面未内嵌 __playinfo__（可能被风控或页面结构变更）")
    try:
        meta = json.loads(m.group(1))
    except Exception as e:
        raise ValueError("__playinfo__ 解析失败: %s" % e)

    title = ""
    tm = re.search(r"<title>(.*?)</title>", html, re.S)
    if tm:
        title = re.sub(r"[_\-|]\s*哔哩哔哩.*$", "", tm.group(1)).strip()
    duration = None
    dm = re.search(r'"videoData"\s*:\s*\{.{0,4000}?"duration":\s*(\d+)', html, re.S)
    if dm:
        duration = int(dm.group(1))

    dash = ((meta.get("data") or {}).get("dash")) or {}
    vlist = [v for v in (dash.get("video") or []) if v.get("baseUrl") or v.get("base_url")]
    if not vlist:
        raise ValueError("页面无 DASH 流")
    ok = [v for v in vlist if (v.get("height") or 0) <= MAX_HEIGHT] or vlist
    best = max(ok, key=lambda v: ((v.get("height") or 0), (v.get("bandwidth") or 0)))
    height = best.get("height") or 0

    # 拼成 yt-dlp 形状，复用 _result_from_ytdlp 的双流/翻译/候选逻辑
    vfmt = {"url": best.get("baseUrl") or best.get("base_url"), "format_id": "bili",
            "ext": "mp4", "height": height, "protocol": "https",
            "vcodec": "avc1", "acodec": "none"}
    afmt = None
    alist = [a for a in (dash.get("audio") or []) if a.get("baseUrl") or a.get("base_url")]
    if alist:
        ba = max(alist, key=lambda a: a.get("bandwidth") or 0)
        afmt = {"url": ba.get("baseUrl") or ba.get("base_url"), "format_id": "bili-a",
                "ext": "m4a", "height": 0, "protocol": "https",
                "vcodec": "none", "acodec": "mp4a"}
    info = {
        "title": title or "",
        "duration": duration,
        "formats": [vfmt],
        "requested_formats": [vfmt] + ([afmt] if afmt else []),
    }
    result = _result_from_ytdlp(page_url, info, vfmt)
    result["stage"] = "site"
    return result


def _is_sohu_page(url):
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return any(host == h or host.endswith("." + h) for h in ("sohu.com",))


def _sohu_follow_dispatch(u, sess, referer):
    """搜狐的 mp4PlayUrl 是调度地址（data.vod.itc.cn/ip?k=），回 JSON 才带真实 CDN mp4。

    直接把它当媒体地址会让前端拿到 {"servers":[...]} 这坨 JSON，video 元素必然报错。
    不是 JSON 就原样返回（有些条目本就是直链）。
    """
    try:
        r = sess.get(u, timeout=15, headers={"Referer": referer})
        if r.status_code != 200:
            return u
        body = (r.text or "").lstrip()
        if not body.startswith("{") and not body.startswith("["):
            return u
        j = json.loads(body)
        servers = j.get("servers") if isinstance(j, dict) else None
        for s in servers or []:
            v = (s or {}).get("url")
            if isinstance(v, str) and v.startswith("http"):
                return v
    except Exception:
        pass
    return u


def _resolve_sohu(page_url):
    """搜狐解析：抓原页面取 `var vid`，再调 videonew.do 拿 mp4PlayUrl 直链。

    yt-dlp 走的是另一条路（把 /v/ 的 base64 解成 my.tv.sohu.com 的 .shtml 再抓），
    实测那条路 404；同一地址用 curl_cffi 伪装浏览器却是 200，说明是 TLS/UA 被拒。
    videonew.do 直接回 mp4 直链，不需要 yt-dlp 那套 allot 调度，故整条特判自成一体。
    """
    from curl_cffi import requests as cr

    sess = cr.Session(impersonate="chrome131", headers={"User-Agent": _UA})
    r = sess.get(page_url, timeout=20, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.bing.com/",
    })
    if r.status_code != 200:
        raise ValueError("页面 HTTP %s" % r.status_code)
    html_page = r.text or ""
    m = re.search(r"var vid\s*=\s*['\"](\d+)['\"]", html_page)
    if not m:
        raise ValueError("页面未找到 vid")
    vid = m.group(1)

    r2 = sess.get("http://my.tv.sohu.com/play/videonew.do?vid=" + vid, timeout=20,
                  headers={"Referer": page_url})
    if r2.status_code != 200:
        raise ValueError("播放信息 HTTP %s" % r2.status_code)
    try:
        meta = r2.json()
    except Exception as e:
        raise ValueError("播放信息非 JSON: %s" % e)
    data = meta.get("data") or {}
    urls = [u for u in (data.get("mp4PlayUrl") or data.get("clipsURL") or [])
            if isinstance(u, str) and u.startswith("http")]
    if not urls:
        raise ValueError("未拿到播放地址 play=%s status=%s"
                         % (meta.get("play"), meta.get("status")))
    urls = [_sohu_follow_dispatch(u, sess, page_url) for u in urls]

    title = ""
    tm = re.search(r'<meta property="og:title" content="([^"]*)"', html_page)
    if tm:
        import html as _html
        title = _html.unescape(tm.group(1)).strip()
    try:
        height = int(data.get("height") or 0)
    except Exception:
        height = 0
    try:
        size = int(data.get("totalBytes") or 0)
    except Exception:
        size = 0

    fmt = {"url": urls[0], "format_id": "sohu", "ext": "mp4", "height": height,
           "protocol": "https", "vcodec": "avc1", "acodec": "mp4a",
           "filesize": size or None}
    info = {
        "title": title or "sohu %s" % vid,
        "duration": data.get("totalDuration") or data.get("totalDurationDouble"),
        "formats": [fmt],
        "requested_formats": [fmt],
    }
    result = _result_from_ytdlp(page_url, info, fmt)
    result["stage"] = "site"
    return result


def _guess_title(page_url):
    try:
        path = urlparse(page_url).path.rstrip("/")
        seg = path.rsplit("/", 1)[-1] if path else ""
        if seg:
            seg = unquote(seg)
            seg = re.sub(r"\.(html?|php|aspx?)$", "", seg, flags=re.I)
            seg = re.sub(r"[-_]+", " ", seg).strip()
            if seg:
                return seg[:200]
    except Exception:
        pass
    return "video"


def _cand_from_format(fmt):
    proto = fmt.get("protocol") or ""
    u = fmt.get("url") or ""
    is_hls = proto.startswith("m3u8") or bool(re.search(r"\.m3u8(\?|$)", u, re.I))
    h = fmt.get("height") or 0
    parts = [str(fmt.get("format_id") or "ytdlp"), str(fmt.get("ext") or "")]
    if h:
        parts.append(f"{h}p")
    return {
        "url": u,
        "ext": "m3u8" if is_hls else (fmt.get("ext") or "mp4"),
        "kind": "ytdlp",
        "quality": f"{h}p" if h else "",
        "from": urlparse(u).netloc.lower() if u else "",
        "label": " · ".join(p for p in parts if p),
    }


def _cand_from_url(u, kind="direct", label=""):
    from extract_svc import _ext_of, _quality_of

    return {
        "url": u,
        "ext": _ext_of(u),
        "kind": kind,
        "quality": _quality_of(u),
        "from": urlparse(u).netloc.lower() if u else "",
        "label": label or (_ext_of(u) if _ext_of(u) != "unknown" else kind),
    }


def _result_from_candidates(page_url, cands, title=None, stage="sniff"):
    """候选列表 → resolve_video 标准返回结构"""
    best = cands[0]
    _note_resolve(page_url, best["url"])
    ext = best.get("ext") or ""
    return {
        "title": title or _guess_title(page_url),
        "title_en": None,
        "duration": None,
        "url": best["url"],
        "format": best.get("label") or (ext if ext != "unknown" else ""),
        "size_bytes": None,
        "is_hls": ext == "m3u8",
        "stage": stage,
        "source_url": page_url,
        "candidates": cands,
    }


def _pick_format(info):
    fmt = None
    fallback = None
    for f in info.get("formats") or []:
        h = f.get("height") or 0
        if h > MAX_HEIGHT:
            continue
        if fallback is None or (f.get("vcodec") != "none" and h > (fallback.get("height") or 0)):
            fallback = f
        if f.get("protocol") not in ("https", "http"):
            continue
        if fmt is None or (f.get("vcodec") != "none" and (fmt.get("vcodec") == "none" or h > (fmt.get("height") or 0))):
            fmt = f
    fmt = fmt or fallback
    if fmt is None:
        u = info.get("url")
        if not u:
            return None
        fmt = {
            "url": u,
            "format_id": "direct",
            "ext": info.get("ext") or "mp4",
            "height": 0,
            "filesize": None,
            "filesize_approx": None,
        }
    return fmt


def _pick_audio_format(info):
    """从 yt-dlp 解析结果里取出与视频流配对的音频流。

    DASH 站（bilibili/优酷/芒果/YouTube…）音视频是两条独立流，`FORMAT`
    里的 `+ba` 让 yt-dlp 把这一对放进了 `requested_formats`。服务端没有
    ffmpeg 合不了流，所以把音频地址一并交回给前端，由播放器双元素同步。
    """
    for f in info.get("requested_formats") or []:
        if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none") and f.get("url"):
            return f
    # 兜底：有些站点只在 formats 里给音频，且没有 requested_formats
    for f in info.get("formats") or []:
        if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none") and f.get("url"):
            return f
    return None


def _result_from_ytdlp(page_url, info, fmt):
    _note_resolve(page_url, fmt["url"])
    title = (info.get("title") or "untitled")[:200]
    title_zh = to_zh(title)
    proto = fmt.get("protocol") or ""
    is_hls = proto.startswith("m3u8") or bool(re.search(r"\.m3u8(\?|$)", fmt["url"] or "", re.I))
    audio = None if is_hls else _pick_audio_format(info)
    result = {
        "title": title_zh,
        "title_en": title if title_zh != title else None,
        "duration": info.get("duration"),
        "url": fmt["url"],
        "format": f"{fmt.get('format_id')} {fmt.get('ext')} {fmt.get('height')}p" if fmt.get("height") else f"{fmt.get('format_id')} {fmt.get('ext')}",
        "size_bytes": fmt.get("filesize") or fmt.get("filesize_approx"),
        "is_hls": is_hls,
        "stage": "ytdlp",
        "source_url": page_url,
        "candidates": [_cand_from_format(fmt)],
    }
    if audio and audio.get("url") != fmt.get("url"):
        result["audio_url"] = audio["url"]
        result["audio_format"] = f"{audio.get('format_id')} {audio.get('ext')}"
        # 音频单独给一个候选，方便只想下载音频的调用方
        acand = _cand_from_format(audio)
        acand["kind"] = "audio"
        acand["label"] = f"音频 · {audio.get('ext') or ''}".strip()
        result["candidates"].append(acand)
    return result


# 嗅探可能把整页登录页当媒体地址：YouTube 撞验证时抓回来的就是 Google 登录页，
# 拉流回 text/html，前端点播放只是一片空白 —— 这种宁可不给地址。
_NON_MEDIA_MARKS = (
    "accounts.google.com",
    "/servicelogin",
    "consent.youtube.com",
    "accounts.youtube.com",
    "challenge/redirect",
)


def _is_non_media_url(u):
    low = (u or "").lower()
    return any(m in low for m in _NON_MEDIA_MARKS)


_NON_MEDIA_CT = ("text/", "application/json", "application/xhtml", "application/xml")


def _probe_content_type(u, timeout=5):
    """读 Content-Type。拿不到返回 None —— 不确定就别据此淘汰，避免误伤。"""
    import requests

    from http_util import HEADERS

    try:
        sess = requests.Session()
        sess.trust_env = False
        if not _is_domestic(u):
            p = _proxy()
            if p:
                sess.proxies.update({"http": p, "https": p})
        for method in ("HEAD", "GET"):
            try:
                headers = dict(HEADERS)
                if method == "GET":
                    headers["Range"] = "bytes=0-1"
                r = sess.request(method, u, headers=headers, timeout=timeout, stream=True)
                ct = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                r.close()
                if ct:
                    return ct
            except Exception:
                continue
    except Exception:
        return None
    return None


def _probe_is_media(u):
    ct = _probe_content_type(u)
    if not ct:
        return True
    return not any(ct.startswith(p) for p in _NON_MEDIA_CT)


# 无扩展名但仍可能真是媒体的 URL 特征（CDN 常把地址藏在 query 里）
_MEDIA_HINT_RE = re.compile(
    r"videoplayback|manifest|m3u8|mpd|playlist|/hls|/dash|/streams?|/video|/media|"
    r"\.php|file=|url=|ext_?url|player",
    re.I,
)


def _sniff_candidates(url):
    """服务端嗅探（页面 + 1 层 iframe）"""
    import extract_svc

    html = extract_svc.fetch_html(url)
    cands = extract_svc.sniff_sources(url, html) if html else []
    if html:
        for iframe in extract_svc.sniff_iframes(url, html)[:3]:
            try:
                h2 = extract_svc.fetch_html(iframe)
                if h2:
                    cands.extend(extract_svc.sniff_sources(iframe, h2))
            except Exception:
                continue
    page = (url or "").rstrip("/")
    ordered = [
        c
        for c in extract_svc.score_and_dedup(cands)
        if not _is_non_media_url(c.get("url") or "")
        and (c.get("url") or "").rstrip("/") != page
    ]

    # kind=js-key 这类 pattern 不看扩展名，会把 YouTube 页面里几十条 watch?v= 帮助页、
    # 首页之类当媒体地址，前端一拉是整页 HTML。分三档：
    #   有媒体扩展名       -> 照旧信任
    #   无扩展名但像媒体   -> 并行探一次内容类型，回 text/* 的丢
    #   无扩展名又不像媒体 -> 直接丢（零请求）
    trusted, suspect = [], []
    for c in ordered:
        ext = (c.get("ext") or "").lower()
        u = c.get("url") or ""
        if ext and ext != "unknown":
            trusted.append(c)
        elif _MEDIA_HINT_RE.search(u):
            suspect.append(c)

    if suspect:
        bad = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(_probe_is_media, c.get("url") or ""): c.get("url") for c in suspect[:4]}
            for f in concurrent.futures.as_completed(futs):
                try:
                    if not f.result():
                        bad.add(futs[f])
                except Exception:
                    continue
        trusted.extend(c for c in suspect if c.get("url") not in bad)

    title = extract_svc.guess_title(url, html) if html else None
    return trusted, title


_DEAD_MSG = "视频已下架或不可见（源站已移除该内容）"

# 源站内容失效的信号：B站稿件状态码、腾讯下架文案、各站通用下架/私有/删除提示。
# 只认「内容没了」这类，风控和网络错误不在此列（那要留着排查）。
_DEAD_MARKS = (
    "62012", "62002", "62004", "62016", "62021",
    "外星人劫走",
    "稿件不可见", "内容已失效", "视频去哪了", "已下架", "已被删除", "已失效",
    "video unavailable", "private video", "video has been removed",
    "has been removed by", "no longer available",
)


def _friendly_error(msg):
    """把源站内容失效翻译成人话，并剥掉 yt-dlp 让人去 GitHub 报 issue 的尾巴。"""
    low = (msg or "").lower()
    if any(mk in low for mk in _DEAD_MARKS):
        return _DEAD_MSG
    msg = re.sub(r";?\s*please report this issue.*$", "", msg or "", flags=re.S | re.I)
    msg = re.sub(r"\s*(?:also\s+)?see\s+https://github\.com/yt-dlp.*$", "", msg, flags=re.S | re.I)
    return msg.strip(" ;")


def _assemble_error(errors, empty="解析失败"):
    """逐条友好化后拼接；一旦判定是内容失效，就只说这一句（别的都是噪音）。"""
    out, seen = [], set()
    for e in errors:
        f = _friendly_error(e)
        if f == _DEAD_MSG:
            return _DEAD_MSG
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return "; ".join(out) or empty


def resolve_video(url, mode="auto"):
    """多级解析：直链 → 站点特判 → yt-dlp → 服务端嗅探 → 浏览器抓包

    mode: auto(默认全链) | ytdlp | server | browser
    返回 dict 含 candidates[]，每个候选 {url, ext, kind, quality, label, from}
    """
    mode = (mode or "auto").strip().lower() or "auto"
    errors = []

    # B站 BV 路径对机房 IP 稳定 412，改写成同视频的 av 路径后再走全链
    if _is_bilibili_page(url):
        url = _bili_av_url(url)

    # S0: 本身就是媒体直链
    try:
        from extract_svc import media_kind

        mk = media_kind(url)
    except Exception:
        mk = "unknown"
    if mk in ("hls", "direct"):
        return _result_from_candidates(url, [_cand_from_url(url, "direct", "直链")], stage="direct")

    # S1: 站点特判
    if mode in ("auto", "ytdlp") and _is_xhamster_page(url):
        try:
            r = _resolve_xhamster(url)
            r["stage"] = "ytdlp"
            r["source_url"] = url
            r["candidates"] = [_cand_from_format({"url": r["url"], "format_id": "hls", "ext": "m3u8", "height": 0, "protocol": "m3u8_native"})]
            return r
        except Exception as e:
            errors.append(f"xhamster: {e}")
        if mode == "ytdlp":
            raise ValueError(_assemble_error(errors))

    # S1b: B站特判（yt-dlp 抓页面会被 412 拦，改走 api.bilibili.com）
    if mode in ("auto", "ytdlp") and _is_bilibili_page(url):
        try:
            return _resolve_bilibili(url)
        except Exception as e:
            errors.append(f"bilibili 特判: {e}")
            # 特判失败不中断，让下面的 yt-dlp 再试一次

    # S1c: 搜狐特判（yt-dlp 改写后的 my.tv 地址 404）
    if mode in ("auto", "ytdlp") and _is_sohu_page(url):
        try:
            return _resolve_sohu(url)
        except Exception as e:
            errors.append(f"sohu 特判: {e}")

    # S2: yt-dlp
    if mode in ("auto", "ytdlp"):
        try:
            info = _resolve_ytdlp(url)
            fmt = _pick_format(info)
            if not fmt:
                raise ValueError("该视频无可用直链格式")
            result = _result_from_ytdlp(url, info, fmt)
            if errors:
                # 上游特判失败但已用别的手段解析成功：把失败原因带回去，
                # 否则线上排查时完全看不到「为什么没走特判」。
                result["warnings"] = list(errors)
            return result
        except Exception as e:
            errors.append(f"yt-dlp: {e}")
        if mode == "ytdlp":
            raise ValueError(_assemble_error(errors))

    # S3: 服务端嗅探
    if mode in ("auto", "server"):
        try:
            cands, title = _sniff_candidates(url)
            if cands:
                result = _result_from_candidates(url, cands, title=title, stage="sniff")
                if errors:
                    result["warnings"] = list(errors)
                return result
            errors.append("服务端嗅探: 未找到媒体地址")
        except Exception as e:
            errors.append(f"服务端嗅探: {e}")
        if mode == "server":
            raise ValueError(_assemble_error(errors, "服务端嗅探未找到媒体地址"))



    raise ValueError(_assemble_error(errors))


_YT_COOKIE_LOCK = threading.Lock()
_YT_COOKIE_PATH = None


def _is_youtube_url(url):
    if not url:
        return False
    low = url.lower()
    return "youtube.com" in low or "youtu.be" in low


def _youtube_cookiefile():
    """把 YOUTUBE_COOKIES（Netscape 格式 cookie.txt 全文）落成临时文件供 yt-dlp 读取。

    YouTube 对机房 IP 一律要求验证：换 player_client 全试过（6 个 client × 6 视频 = 36 次全 BOT），
    yt-dlp 内置的 PO Token provider 只有缓存、没有生成器（生成要外部 Node 插件），公共 Invidious
    实例又全部 401/403/502 —— 浏览器 cookie 是唯一可靠路子。
    内容只落盘、绝不打印。
    """
    global _YT_COOKIE_PATH
    try:
        from env_utils import env

        raw = env("YOUTUBE_COOKIES")
    except Exception:
        return None
    if not raw:
        return None
    with _YT_COOKIE_LOCK:
        if _YT_COOKIE_PATH:
            return _YT_COOKIE_PATH if os.path.exists(_YT_COOKIE_PATH) else None
        try:
            d = tempfile.mkdtemp(prefix="ytck_")
            path = os.path.join(d, "cookies.txt")
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(raw.rstrip("\n") + "\n")
            _YT_COOKIE_PATH = path
            return path
        except Exception:
            return None


def _base_opts(url=None):
    opts = {
        "quiet": True,
        "noplaylist": True,
        "format": FORMAT,
        "merge_output_format": "mp4",
        "restrictfilenames": True,
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    }
    opts["http_headers"].update(_extra_headers(url))
    ref = _referer_for(url) if url else None
    if ref:
        opts["http_headers"]["Referer"] = ref

    ck = _youtube_cookiefile()
    if ck and _is_youtube_url(url):
        opts["cookiefile"] = ck


    p = _proxy()
    if p and not _is_domestic(url):
        opts["proxy"] = p
    elif _is_domestic(url):
        opts["proxy"] = ""
    return opts


def search_youtube(keyword, count):
    opts = dict(_base_opts())
    opts.update({"extract_flat": "in_playlist", "playlist_items": f"1-{count}"})
    try:
        yt_dlp = _require_yt_dlp()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{count}:{keyword}", download=False)
    except Exception as e:
        raise ValueError(f"YouTube 搜索失败: {e}") from e
    items = []
    for e in (info.get("entries") or [])[:count]:
        if not e or not e.get("url"):
            continue
        items.append(
            {
                "title": (e.get("title") or keyword)[:200],
                "url": e.get("url"),
                "duration": e.get("duration"),
                "thumb": e.get("thumbnails", [{}])[-1].get("url") if e.get("thumbnails") else None,
                "source": "youtube",
            }
        )
    _translate_items(items)
    return items


def _parse_dur(label):
    m = re.search(r"时长[:：]?\s*(\d+)\s*小时(?:\s*(\d+)\s*分钟)?(?:\s*(\d+)\s*秒)?", label)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    m = re.search(r"时长[:：]?\s*(\d+)\s*分钟(?:\s*(\d+)\s*秒)?", label)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2) or 0)
    m = re.search(r"时长[:：]?\s*(\d+)\s*秒", label)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:分钟|分)", label)
    if m:
        return int(m.group(1)) * 60
    return None


def _translate_items(items):
    titles = [i["title"] for i in items]
    tr = translate_many(titles)
    for i in items:
        orig = i["title"]
        if tr.get(orig) and tr[orig] != orig:
            i["title_en"] = orig
            i["title"] = tr[orig]


def search_bing_video(keyword, count):
    import requests

    from http_util import HEADERS

    headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
    try:
        sess = requests.Session()
        sess.trust_env = False
        r = sess.get(
            "https://cn.bing.com/videos/search",
            params={"q": keyword, "FORM": "HDRSC7"},
            headers=headers,
            timeout=25,
        )
        r.raise_for_status()
        text = r.text
    except Exception as e:
        raise ValueError(f"必应视频访问失败: {e}") from e
    # Douyin requires browser JS to generate play URLs — filter them out
    _SKIP_VIDEO_HOSTS = _UNSUPPORTED_VIDEO_HOSTS
    items = []
    for m in re.finditer(
        r'<a aria-label="([^"]*?)" data-dc="[^"]*" class="mc_vtvc_link[^"]*"[^>]*href="([^"]+)"',
        text,
    ):
        label, href = m.group(1), m.group(2)
        if any(h in href for h in _SKIP_VIDEO_HOSTS):
            continue
        title = label.split("来源:")[0].strip()
        dur_m = re.search(r"时长[:：]?\s*(\d+\s*(?:小时|分钟|分))?[\s]*(\d+\s*秒)?", label)
        dur = ""
        if dur_m:
            dur = " ".join(x for x in dur_m.groups() if x).strip()
        thumb = None
        if len(items) < count:
            items.append(
                {
                    "title": title[:200],
                    "url": href,
                    "duration_text": dur,
                    "duration": _parse_dur(label),
                    "thumb": thumb,
                    "source": "bing",
                }
            )
    if not items:
        raise ValueError("必应视频没有可播放的结果（解析不了的站点已过滤）")
    _translate_items(items)
    return items


def search_yahoo(keyword, count):
    """Yahoo 视频: video.search.yahoo.com HTML 解析, 缩略图走 Bing CDN"""

    from urllib.parse import parse_qs, unquote, urlparse

    try:
        r = _fetch_proxied(
            "https://video.search.yahoo.com/search/video",
            params={"p": keyword},
            timeout=25,
        )
        text = r.text
    except Exception as e:
        raise ValueError(f"Yahoo 视频访问失败: {e}") from e
    items = []
    seen = set()
    total = 0
    blocked = 0
    for m in re.finditer(
        r'<li class="tile[^"]*"[^>]*id="resitem-\d+"[^>]*>.*?data-referenceurl="([^"]*)"[^>]*>(.*?)</a></li>',
        text,
        re.S,
    ):
        ref, inner = m.group(1), m.group(2)
        total += 1
        if _is_unsupported_video_url(ref):
            blocked += 1
            continue
        url = ref
        q = parse_qs(urlparse(url).query)
        img = q.get("imgurl")
        if img and img[0].startswith("http"):
            url = img[0]
        if url in seen or not url.startswith("http"):
            continue
        seen.add(url)
        title = ""
        tm = re.search(r'class="[^"]*tile-title[^"]*">(.*?)</p>', inner, re.S)
        if tm:
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        if not title:
            am = re.search(r'<img[^>]+alt="([^"]*)"', inner)
            if am:
                title = am.group(1).strip()
        if not title:
            continue
        thumb = None
        im = re.search(r'<img[^>]+src="(https?://[^"]+)"', inner)
        if im:
            thumb = im.group(1).replace("&amp;", "&")
        dur = ""
        dm = re.search(r'class="[^"]*time[^"]*"[^>]*>([^<]+)</p>', inner)
        if dm:
            dur = dm.group(1).strip()
        items.append(
            {
                "title": title[:200],
                "url": url,
                "duration": _parse_dur(dur),
                "duration_text": dur,
                "thumb": thumb,
                "source": "yahoo",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError(f"Yahoo 视频没有解析到结果（页内匹配{total}条，被过滤{blocked}条，html={len(text)}字节）")
    _translate_items(items)
    return items


def search_pornhub(keyword, count):
    opts = dict(_base_opts())
    opts.update({"extract_flat": "in_playlist", "playlist_items": f"1-{count}"})
    url = "https://www.pornhub.com/video/search?search=" + quote(to_en(keyword))
    try:
        yt_dlp = _require_yt_dlp()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise ValueError(f"Pornhub 搜索失败: {e}") from e
    items = []
    for e in (info.get("entries") or [])[:count]:
        if not e or not e.get("url"):
            continue
        items.append(
            {
                "title": (e.get("title") or keyword)[:200],
                "url": e.get("url"),
                "duration": None,
                "duration_text": "",
                "thumb": e.get("thumbnails", [{}])[-1].get("url") if e.get("thumbnails") else None,
                "source": "pornhub",
            }
        )
    _translate_items(items)
    return items


def _fetch_proxied(url, params=None, timeout=25):
    import requests

    p = _proxy()
    proxies = {"http": p, "https": p} if p else None
    r = requests.get(
        url,
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        },
        timeout=timeout,
        proxies=proxies,
    )
    r.raise_for_status()
    return r


def _fetch_any(url, params=None, timeout=25):
    """直连优先，失败后走代理（用于国外可直连站点）"""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    }
    try:
        return requests.get(url, params=params, headers=headers, timeout=timeout)
    except Exception:
        return _fetch_proxied(url, params=params, timeout=timeout)


def search_xnxx(keyword, count):
    keyword = to_en(keyword)
    try:
        r = _fetch_proxied("https://www.xnxx.com/search/" + quote(keyword))
    except Exception as e:
        raise ValueError(f"XNXX 搜索失败: {e}") from e
    items = []
    for m in re.finditer(r'<p><a href="(/video-[\w]+/[^"]+)" title="([^"]*)">', r.text):
        href, title = m.group(1), m.group(2)
        items.append(
            {
                "title": title[:200],
                "url": "https://www.xnxx.com" + href,
                "duration": None,
                "duration_text": "",
                "thumb": None,
                "source": "xnxx",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("XNXX 没有解析到结果")
    _translate_items(items)
    return items


def search_xvideos(keyword, count):
    """XVIDEOS 搜索（2026 页面结构）：/video.{eid}/slug 卡片 + data-src 缩略图 + 内嵌时长"""
    keyword = to_en(keyword)
    try:
        r = _fetch_proxied("https://www.xvideos.com/?k=" + quote(keyword))
    except Exception as e:
        raise ValueError(f"XVIDEOS 搜索失败: {e}") from e
    items = []
    seen = set()
    # 卡片：<div class="thumb"><a href="/video.xxx/slug"><img ... data-src="thumb">
    for m in re.finditer(
        r'<div class="thumb"><a href="(/video\.\w+/[^"]+)"[^>]*>.*?data-src="([^"]+)"',
        r.text,
        re.S,
    ):
        href, thumb = m.group(1), m.group(2)
        if href in seen:
            continue
        seen.add(href)
        items.append(
            {
                "title": "",
                "url": "https://www.xvideos.com" + href,
                "duration": None,
                "duration_text": "",
                "thumb": thumb if thumb.startswith("http") else "https:" + thumb,
                "source": "xvideos",
            }
        )
        if len(items) >= count:
            break
    # 标题+时长：<p class="title"><a>标题 <span class="duration">X min</span>（顺序与卡片一致）
    title_durs = []
    for m in re.finditer(r'<p class="title"[^>]*>\s*<a[^>]*>(.*?)</a>', r.text, re.S):
        inner = m.group(1)
        dur = re.search(r'<span class="duration"[^>]*>([^<]+)</span>', inner)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if title:
            title_durs.append((title, dur.group(1).strip() if dur else ""))
    for i, it in enumerate(items):
        if i < len(title_durs):
            it["title"] = title_durs[i][0][:200]
            it["duration_text"] = title_durs[i][1]
        else:
            it["title"] = it["url"].rsplit("/", 1)[-1].replace("_", " ").title()[:200]
    if not items:
        raise ValueError("XVIDEOS 没有解析到结果")
    _translate_items(items)
    return items


def search_xhamster(keyword, count):
    keyword = to_en(keyword)
    try:
        r = _fetch_proxied("https://xhamster.com/search", params={"q": keyword})
    except Exception as e:
        raise ValueError(f"xHamster 搜索失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(
        r'href="(https?://(?:www\.)?xhamster\.com/videos/[^"]+)"[^>]*aria-label="([^"]*)"',
        r.text,
    ):
        url, title = m.group(1), m.group(2)
        if url in seen:
            continue
        seen.add(url)
        items.append(
            {
                "title": title[:200],
                "url": url,
                "duration": None,
                "duration_text": "",
                "thumb": None,
                "source": "xhamster",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("xHamster 没有解析到结果")
    _translate_items(items)
    return items


def search_thothub(keyword, count):
    keyword = to_en(keyword)
    try:
        kw = quote(re.sub(r"\s+", "+", keyword), safe="+")
        r = _fetch_proxied("https://thothub.vip/search/" + kw + "/")
    except Exception as e:
        raise ValueError(f"ThotHub 搜索失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(
        r'<a href="(https?://(?:www\.)?thothub\.(?:vip|to)/video/\d+/[^"]+/)" title="([^"]*)"',
        r.text,
    ):
        url, title = m.group(1), m.group(2)
        if url in seen:
            continue
        seen.add(url)
        seg = r.text[m.start() : m.start() + 600]
        dm = re.search(r"(\d+):(\d{2})", seg)
        dur = int(dm.group(1)) * 60 + int(dm.group(2)) if dm else None
        items.append(
            {
                "title": title[:200],
                "url": url,
                "duration": dur,
                "duration_text": "",
                "thumb": None,
                "source": "thothub",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("ThotHub 没有解析到结果")
    _translate_items(items)
    return items


def _colon_dur(s):
    if not s:
        return None
    try:
        parts = [int(x) for x in str(s).split(":")]
    except ValueError:
        return None
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return None


def search_bilibili(keyword, count):
    from curl_cffi import requests as cr

    try:
        sess = cr.Session(
            impersonate="chrome131",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        )
        sess.get("https://www.bilibili.com/", timeout=12)
        r = sess.get(
            "https://api.bilibili.com/x/web-interface/search/type",
            params={"search_type": "video", "keyword": keyword, "page": 1},
            headers={"Referer": "https://search.bilibili.com/"},
            timeout=12,
        )
        d = r.json()
    except Exception as e:
        raise ValueError(f"B站搜索失败: {e}") from e
    if d.get("code") != 0:
        raise ValueError(f"B站搜索失败: {d.get('message') or d.get('code')}")
    items = []
    for v in (d.get("data") or {}).get("result") or []:
        title = re.sub(r"<[^>]+>", "", v.get("title") or "").strip()[:200]
        if not title or not v.get("bvid"):
            continue
        pic = v.get("pic") or ""
        if pic.startswith("//"):
            pic = "https:" + pic
        url = v.get("arcurl") or f"https://www.bilibili.com/video/{v.get('bvid')}"
        if url.startswith("http://"):
            url = "https://" + url[len("http://") :]
        items.append(
            {
                "title": title,
                "url": url,
                "duration": _colon_dur(v.get("duration")),
                "duration_text": "",
                "thumb": pic,
                "source": "bilibili",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("B站没有搜索到结果")
    _translate_items(items)
    return items


def search_acfun(keyword, count):
    from curl_cffi import requests as cr

    try:
        r = cr.post(
            "https://www.acfun.cn/rest/pc-direct/search/video",
            data={"keyword": keyword, "page": 1, "pageSize": count, "quickView": "true"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=12,
            impersonate="chrome131",
        )
        d = r.json()
    except Exception as e:
        raise ValueError(f"AcFun 搜索失败: {e}") from e
    items = []
    for v in (d.get("videoList") or [])[:count]:
        title = (v.get("title") or v.get("emTitle") or "").strip()[:200]
        cid = v.get("id") or v.get("contentId")
        if not title or not cid:
            continue
        items.append(
            {
                "title": title,
                "url": f"https://www.acfun.cn/v/ac{cid}",
                "duration": _colon_dur(v.get("playDuration")),
                "duration_text": "",
                "thumb": v.get("coverUrl"),
                "source": "acfun",
            }
        )
    if not items:
        raise ValueError("AcFun 没有搜索到结果")
    _translate_items(items)
    return items


def search_youku(keyword, count):
    from curl_cffi import requests as cr

    try:
        sess = cr.Session(
            impersonate="chrome131",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        )
        sess.get("https://www.youku.com/", timeout=12)
        r = sess.get("https://so.youku.com/search_video/q_" + quote(keyword), timeout=12)
        text = r.text
    except Exception as e:
        raise ValueError(f"优酷搜索失败: {e}") from e
    if "punish" in text or '"videoId"' not in text:
        raise ValueError("优酷触发验证码风控（无法程序化绕过），请稍后再试，或改用 B站/必应等视频源")
    items = []
    for m in re.finditer(r'"videoId":"([^"]+)"[^}]*?"title":"([^"]{4,80})"', text):
        vid, title = m.group(1), m.group(2)
        try:
            title = json.loads('"' + title + '"')
        except Exception:
            pass
        seg = text[m.start() : m.start() + 1200]
        sm = re.search(r'"seconds":"(\d+)"', seg)
        dur = int(sm.group(1)) if sm else None
        items.append(
            {
                "title": title[:200],
                "url": f"https://v.youku.com/v_show/id_{vid}.html",
                "duration": dur,
                "duration_text": "",
                "thumb": None,
                "source": "youku",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("优酷没有搜索到结果")
    _translate_items(items)
    return items


def search_mgtv(keyword, count):
    from curl_cffi import requests as cr

    params = {
        "_support": "10000000",
        "allowedRC": "1",
        "area": "10",
        "channelId": "2",
        "chargeInfo": "a1",
        "feature": "all",
        "hudong": "1",
        "kind": "19",
        "pc": "80",
        "platform": "pcweb",
        "pn": "1",
        "sort": "c2",
        "year": "all",
        "word": keyword,
        "pno": 1,
        "psize": 20,
        "cname": "all",
    }
    try:
        r = cr.get(
            "https://pianku.api.mgtv.com/rider/list/pcweb/v3",
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://so.mgtv.com/",
            },
            timeout=12,
            impersonate="chrome131",
        )
        d = r.json()
    except Exception as e:
        raise ValueError(f"芒果TV搜索失败: {e}") from e
    items = []
    for v in (d.get("data") or {}).get("hitDocs") or []:
        title = (v.get("title") or "").strip()[:200]
        clip = v.get("clipId")
        part = v.get("playPartId")
        if not title or not clip or not part:
            continue
        items.append(
            {
                "title": title,
                "url": f"https://www.mgtv.com/b/{clip}/{part}.html",
                "duration": None,
                "duration_text": "",
                "thumb": v.get("img"),
                "source": "mgtv",
            }
        )
        if len(items) >= count:
            break
    if not items:
        raise ValueError("芒果TV没有搜索到结果")
    _translate_items(items)
    return items


def _resolve_xhamster(url):
    """xhamster 特判：h264 直链需 cookie 单独访问会 403，改返回 HLS m3u8（分片带 Referer 可直访）"""
    opts = dict(_base_opts(url))
    opts["skip_download"] = True
    try:
        yt_dlp = _require_yt_dlp()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise ValueError(f"xhamster 解析失败: {e}") from e
    fmt = None
    for f in info.get("formats") or []:
        if f.get("protocol") != "m3u8_native":
            continue
        h = f.get("height") or 0
        if h > MAX_HEIGHT:
            continue
        if fmt is None or h > (fmt.get("height") or 0):
            fmt = f
    if fmt is None:
        raise ValueError("xhamster 无可用 HLS 流")
    _note_resolve(url, fmt["url"])
    title = (info.get("title") or "xhamster")[:200]
    title_zh = to_zh(title)
    return {
        "title": title_zh,
        "title_en": title if title_zh != title else None,
        "duration": info.get("duration"),
        "url": fmt["url"],
        "format": f"hls {fmt.get('height')}p",
        "size_bytes": None,
        "is_hls": True,
    }


def _referer_for_host(url):
    host = url.split("/")[2].lower() if url.startswith("http") else ""
    if "phncdn" in host:
        return "https://www.pornhub.com/"
    if "bilivideo" in host or "biliimg" in host:
        return "https://www.bilibili.com/"
    if "googlevideo" in host:
        return "https://www.youtube.com/"
    if "xhamster" in host or "xhcdn" in host:
        return "https://xhamster.com/"
    if "xnxx" in host:
        return "https://www.xnxx.com/"
    if "xvideos" in host or "cdn77" in host:
        return "https://www.xvideos.com/"
    if "thothub" in host or "loulouvideo" in host or "hddpornhub" in host:
        return "https://thothub.to/"
    if "mushroomtrack" in host or "jable" in host:
        return "https://jable.tv/"
    return None


def _referer_for(url):
    """媒体地址的 Referer：已知 CDN 映射 > resolve 时记录的页面 origin > None"""
    if not url:
        return None
    ref = _referer_for_host(url)
    if ref:
        return ref
    with _ref_lock:
        page = _ref_cache.get(url)
    if page:
        ref = _referer_for_host(page)
        if ref:
            return ref
        try:
            pr = urlparse(page)
            if pr.scheme in ("http", "https") and pr.netloc:
                return f"{pr.scheme}://{pr.netloc}/"
        except Exception:
            pass
    return None


def _is_xhamster_page(url):
    try:
        return (
            urlparse(url).netloc.lower().endswith("xhamster.com")
            and "/videos/" in urlparse(url).path
        )
    except Exception:
        return False


def stream_direct(url, range_header, extra_headers=None):
    """把视频直链流式转发给浏览器（支持 Range），返回 (状态码, 响应头 dict, 迭代器)"""
    import requests

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    headers.update(_extra_headers(url))
    ref = _referer_for(url)
    if ref:
        headers["Referer"] = ref
    if range_header:
        headers["Range"] = range_header
    if extra_headers:
        headers.update(extra_headers)
    p = _proxy()
    proxies = {"http": p, "https": p} if (p and not _is_domestic(url)) else None
    r = requests.get(url, headers=headers, stream=True, timeout=30, proxies=proxies)
    out = {}
    for k in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
        if r.headers.get(k):
            out[k] = r.headers[k]
    return r.status_code, out, r.iter_content(65536)


def fetch_playlist(url):
    """拉取 m3u8 播放列表文本，返回 (text, base_url)"""
    import requests

    headers = {"User-Agent": _UA, "Accept": "*/*"}
    headers.update(_extra_headers(url))
    ref = _referer_for(url)
    if ref:
        headers["Referer"] = ref
    p = _proxy()
    proxies = {"http": p, "https": p} if (p and not _is_domestic(url)) else None
    r = requests.get(url, headers=headers, timeout=30, proxies=proxies)
    if r.status_code != 200:
        raise RuntimeError(f"播放列表 {r.status_code}")
    base = url
    if r.url and "://" in r.url:
        base = r.url
    return r.text, base


def rewrite_playlist(text, base):
    """把 m3u8 内的分片/密钥/variant URL 改写为本机代理端点，返回改写后文本。

    每个改写后的 URL 都附带 `sig`（见 stream_sign.py）：代理端点是开放接口，
    没有签名就会被当成免费代理白嫖流量。签名自包含过期时间点，无需服务端存储。
    """
    from stream_sign import sign

    def _target(prefix, absu):
        return "%s%s&sig=%s" % (prefix, quote(absu, safe=""), sign(absu))

    playlist_prefix = "/api/hls-playlist?url="
    seg_prefix = "/api/hls-seg?url="
    out = []
    prev_directive = ""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            out.append("")
            continue
        if s.startswith("#"):
            m = re.search(r'URI="([^"]+)"', s)
            if m:
                uri = m.group(1)
                absu = urljoin(base, uri)
                if s.startswith("#EXT-X-MEDIA"):
                    newu = _target(playlist_prefix, absu)
                else:
                    newu = _target(seg_prefix, absu)
                s = s.replace(f'URI="{uri}"', f'URI="{newu}"')
            out.append(s)
            prev_directive = s
        else:
            absu = urljoin(base, s)
            if prev_directive.startswith("#EXT-X-STREAM-INF") or prev_directive.startswith("#EXT-X-I-FRAME-STREAM-INF"):
                out.append(_target(playlist_prefix, absu))
            else:
                out.append(_target(seg_prefix, absu))
            prev_directive = ""
    return "\n".join(out)


def stream_hls_segment(url):
    """流式代理分片/密钥（带 UA/Referer），返回字节迭代器"""
    import requests

    headers = {"User-Agent": _UA, "Accept": "*/*"}
    headers.update(_extra_headers(url))
    ref = _referer_for(url)
    if ref:
        headers["Referer"] = ref
    p = _proxy()
    proxies = {"http": p, "https": p} if (p and not _is_domestic(url)) else None
    r = requests.get(url, headers=headers, stream=True, timeout=(10, 60), proxies=proxies)
    if r.status_code != 200:
        raise RuntimeError(f"分片 {r.status_code}")
    for chunk in r.iter_content(65536):
        if chunk:
            yield chunk
