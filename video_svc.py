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


def _url_page(url):
    """取 /video/xxx?p=2 的分 P 序号（1 起）"""
    try:
        return max(1, int((parse_qs(urlparse(url).query).get("p") or ["1"])[0] or 1))
    except Exception:
        return 1


def _resolve_bilibili(page_url, page=1):
    """B站走 api.bilibili.com 的 view + playurl(DASH)。

    yt-dlp 抓 /video/ 页面会被 B 站 412 反爬拦截（Vercel 机房 IP 更易触发），
    但 api.bilibili.com 不拦；且与 search_bilibili 共用 curl_cffi 的 TLS 指纹
    伪装通道。返回结构复用 _result_from_ytdlp，前端按「视频+音频双流」同步播放。
    """
    from curl_cffi import requests as cr

    sess = cr.Session(impersonate="chrome131", headers={"User-Agent": _UA})
    ref = {"Referer": "https://www.bilibili.com/"}
    sess.get("https://www.bilibili.com/", timeout=12)  # 预热 cookie

    target = page_url
    if "b23.tv" in urlparse(page_url).netloc:
        target = str(sess.get(page_url, allow_redirects=True, timeout=12).url)
    key = _bili_key(target)
    if not key:
        raise ValueError("不是 B站视频链接")

    view = sess.get("https://api.bilibili.com/x/web-interface/view",
                    params=key, headers=ref, timeout=15).json()
    if view.get("code") != 0:
        raise ValueError("view: %s" % (view.get("message") or view.get("code")))
    data = view.get("data") or {}
    cid = data.get("cid")
    pages = data.get("pages") or []
    if pages:
        idx = max(1, min(int(page or 1), len(pages)))
        cid = pages[idx - 1].get("cid") or cid
    if not cid:
        raise ValueError("view: 缺少 cid")

    params = {}
    if key.get("bvid"):
        params["bvid"] = key["bvid"]
    if key.get("aid"):
        params["avid"] = key["aid"]
    params.update({"cid": cid, "qn": 80, "fnval": 16, "fnver": 0, "fourk": 1})
    play = sess.get("https://api.bilibili.com/x/player/playurl",
                    params=params, headers=ref, timeout=15).json()
    if play.get("code") != 0:
        raise ValueError("playurl: %s" % (play.get("message") or play.get("code")))
    dash = ((play.get("data") or {}).get("dash")) or {}
    vlist = [v for v in (dash.get("video") or []) if v.get("baseUrl") or v.get("base_url")]
    if not vlist:
        raise ValueError("playurl: 无可用视频流")
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
        "title": data.get("title") or "",
        "duration": data.get("duration"),
        "formats": [vfmt],
        "requested_formats": [vfmt] + ([afmt] if afmt else []),
    }
    result = _result_from_ytdlp(page_url, info, vfmt)
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
    ordered = extract_svc.score_and_dedup(cands)
    title = extract_svc.guess_title(url, html) if html else None
    return ordered, title


def resolve_video(url, mode="auto"):
    """多级解析：直链 → 站点特判 → yt-dlp → 服务端嗅探 → 浏览器抓包

    mode: auto(默认全链) | ytdlp | server | browser
    返回 dict 含 candidates[]，每个候选 {url, ext, kind, quality, label, from}
    """
    mode = (mode or "auto").strip().lower() or "auto"
    errors = []

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
            raise ValueError("; ".join(errors))

    # S1b: B站特判（yt-dlp 抓页面会被 412 拦，改走 api.bilibili.com）
    if mode in ("auto", "ytdlp") and _is_bilibili_page(url):
        try:
            return _resolve_bilibili(url, page=_url_page(url))
        except Exception as e:
            errors.append(f"bilibili 特判: {e}")
            # 特判失败不中断，让下面的 yt-dlp 再试一次

    # S2: yt-dlp
    if mode in ("auto", "ytdlp"):
        try:
            info = _resolve_ytdlp(url)
            fmt = _pick_format(info)
            if not fmt:
                raise ValueError("该视频无可用直链格式")
            return _result_from_ytdlp(url, info, fmt)
        except Exception as e:
            errors.append(f"yt-dlp: {e}")
        if mode == "ytdlp":
            raise ValueError("; ".join(errors) or "解析失败")

    # S3: 服务端嗅探
    if mode in ("auto", "server"):
        try:
            cands, title = _sniff_candidates(url)
            if cands:
                return _result_from_candidates(url, cands, title=title, stage="sniff")
            errors.append("服务端嗅探: 未找到媒体地址")
        except Exception as e:
            errors.append(f"服务端嗅探: {e}")
        if mode == "server":
            raise ValueError("; ".join(errors) or "服务端嗅探未找到媒体地址")



    raise ValueError("; ".join(errors) or "解析失败")


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
    _SKIP_VIDEO_HOSTS = ("douyin.com", "tiktok.com")
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
        raise ValueError("必应视频没有可播放的结果（抖音/TikTok需要浏览器Cookie）")
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
    for m in re.finditer(
        r'<li class="tile[^"]*"[^>]*id="resitem-\d+"[^>]*>.*?data-referenceurl="([^"]*)"[^>]*>(.*?)</a></li>',
        text,
        re.S,
    ):
        ref, inner = m.group(1), m.group(2)
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
        raise ValueError("Yahoo 视频没有解析到结果")
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
