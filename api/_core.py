import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from main_engine import (
    HEADERS,
    fetch_page_images,
    http_get,
    pixabay_page,
    search_anime_pictures_page,
    search_asiantolick_page,
    search_baidu_page,
    search_bing_page,
    search_duitang_page,
    search_foamgirl_page,
    search_giphy_page,
    search_google_page,
    search_huaban_page,
    search_maccms_pic_page,
    search_meitulu_page,
    search_openverse_page,
    search_pexels_page,
    search_photos18_page,
    search_pixiv_page,
    search_pornhub_albums_page,
    search_pornhub_page,
    search_pornpics_page,
    search_pxhere_page,
    search_so360_page,
    search_sogou_page,
    search_tuchong_page,
    search_twitter_page,
    search_unsplash_page,
    search_wallhaven_page,
    search_wallhere_page,
    search_wikimedia_page,
    search_xiurenai_page,
    search_xsnvshen_page,
    search_xxknit_page,
    search_yahoo_page,
    search_yande_page,
    search_youtube_page,
)

MAX_PROXY_BYTES = 25 * 1024 * 1024

BLOCKED_HOSTS = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.|169\.254\.)",
    re.I,
)

_BING_SESSION = None


def _get_bing_session():
    global _BING_SESSION
    if _BING_SESSION is None:
        try:
            from main_engine import _bing_session

            _BING_SESSION = _bing_session()
        except Exception:
            _BING_SESSION = None
    return _BING_SESSION


def api_search(keyword, source, page, count=20):
    source = source.lower()
    EN_SOURCES = {
        "pornhub", "pornhub-albums", "pornpics", "asiantolick",
        "foamgirl", "openverse", "wikimedia", "wallhaven", "wallhere", "yande",
        "pxhere", "pixabay", "unsplash", "giphy", "anime-pictures", "pixiv",
    }
    if source in EN_SOURCES:
        try:
            from trans_svc import has_chinese, to_en

            if has_chinese(keyword):
                keyword = to_en(keyword)
        except Exception:
            pass
    if source == "bing":
        items = search_bing_page(keyword, max(page - 1, 0), session=_get_bing_session())
        has_more = bool(items)
    elif source == "baidu":
        items = search_baidu_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "pixabay":
        items, has_more = pixabay_page(
            keyword, page, os.environ.get("PIXABAY_KEY", "")
        )
    elif source == "sogou":
        items = search_sogou_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "so360":
        items = search_so360_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "huaban":
        items = search_huaban_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "tuchong":
        items = search_tuchong_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "google":
        items = search_google_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "yahoo":
        items = search_yahoo_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "youtube":
        items = search_youtube_page(keyword, page)
        has_more = bool(items)
    elif source == "pornhub":
        items = search_pornhub_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "pornhub-albums":
        items = search_pornhub_albums_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "pornpics":
        items = search_pornpics_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "photos18":
        items = search_photos18_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "asiantolick":
        items = search_asiantolick_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "xxknit":
        items = search_xxknit_page(keyword, max(page - 1, 0) + 1)
        has_more = bool(items)
    elif source == "xiurenai":
        items = search_xiurenai_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "foamgirl":
        items = search_foamgirl_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "twitter":
        items = search_twitter_page(keyword, page)
        has_more = bool(items)
    elif source == "unsplash":
        items = search_unsplash_page(
            keyword, page, os.environ.get("UNSPLASH_KEY", "")
        )
        has_more = bool(items)
    elif source == "openverse":
        items = search_openverse_page(keyword, page)
        has_more = bool(items)
    elif source == "wikimedia":
        items = search_wikimedia_page(keyword, page)
        has_more = bool(items)
    elif source == "wallhaven":
        items = search_wallhaven_page(keyword, page)
        has_more = bool(items)
    elif source == "pxhere":
        items = search_pxhere_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "duitang":
        items = search_duitang_page(keyword, page)
        has_more = bool(items)
    elif source == "pexels":
        items = search_pexels_page(keyword, max(page - 1, 0), api_key=os.environ.get("PEXELS_KEY", ""))
        has_more = bool(items)
    elif source == "giphy":
        items = search_giphy_page(keyword, page)
        has_more = bool(items)
    elif source == "wallhere":
        items = search_wallhere_page(keyword, page)
        has_more = bool(items)
    elif source == "yande":
        items = search_yande_page(keyword, page)
        has_more = bool(items)
    elif source == "pixiv":
        items = search_pixiv_page(keyword, page)
        has_more = bool(items)
    elif source == "anime-pictures":
        items = search_anime_pictures_page(keyword, page)
        has_more = bool(items)
    elif source == "meitulu":
        items = search_meitulu_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "xsnvshen":
        items = search_xsnvshen_page(keyword, max(page - 1, 0))
        has_more = bool(items)
    elif source == "hhe62":
        items, has_more = search_maccms_pic_page(keyword, max(page - 1, 0), count=count)
    elif source == "cg51":
        from cg51_svc import search_album_images

        items, has_more = search_album_images(keyword, page, count=count)
    elif source in ("dogceo", "catapi", "bingwp", "bingbg", "picsum"):
        from random_svc import fetch_images

        items, has_more = fetch_images(source, page, count)
    else:
        raise ValueError("不支持的数据源: " + source)
    if source in ("pornhub-albums", "pornpics", "asiantolick", "foamgirl"):
        try:
            from trans_svc import translate_many

            titles = [i.get("title") or "" for i in items]
            tr = translate_many(titles)
            for i in items:
                t = i.get("title") or ""
                if t and tr.get(t) and tr[t] != t:
                    i["title_en"] = t
                    i["title"] = tr[t]
        except Exception:
            pass
    return {"items": items, "has_more": has_more}


def api_page_images(url):
    items = fetch_page_images(url)
    return {"items": items, "has_more": False}


def api_comic_search(keyword, source, page=1, count=20):
    from comic_svc import search_comic

    items, has_more = search_comic(keyword, source, page, count=count)
    return {"items": items, "has_more": has_more}


def api_comic_pages(url, limit=None):
    from comic_svc import comic_pages

    return comic_pages(url, limit)


def _img_error(url, e):
    """把下载异常翻成一行人话，前端日志能直接看到失败原因（而不是只有一个 HTTP 400）。"""
    host = url.split("/")[2].split(":")[0]
    msg = str(e)
    low = msg.lower()
    if "timed out" in low or "timeout" in low:
        return f"下载超时: {host}"
    if "nameresolution" in low or "name or service not known" in low or "getaddrinfo" in low:
        return f"域名解析失败(源站域名已失效?): {host}"
    if "max retries" in low or "connection" in low:
        return f"连接失败: {host}"
    m = re.match(r"(\d{3})", msg)
    if m:
        return f"上游返回 HTTP {m.group(1)}: {host}"
    return f"{host}: {msg[:100]}"


# 图片专用请求头：Chrome/126 这种旧 UA 会被部分 CDN 直接 403（实测 p4.itc.cn 对 126 给 403、131 给 200）
_IMG_HEADERS = {
    **HEADERS,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


def api_proxy(url):
    if not url.startswith(("http://", "https://")):
        raise ValueError("无效的图片地址")
    host = url.split("/")[2].split(":")[0].lower()
    if BLOCKED_HOSTS.match(host):
        raise ValueError("该地址不允许访问")
    headers = _IMG_HEADERS
    try:
        if host == "xr.afxfl.com":
            from main_engine import _direct_session

            headers = {**_IMG_HEADERS, "Referer": "https://www.xiurenai.com/"}
            r = http_get(url, timeout=20, retries=2, headers=headers, session=_direct_session())
        else:
            r = http_get(url, timeout=20, retries=2, headers=headers)
    except Exception as e:
        raise ValueError(_img_error(url, e)) from e
    ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
    if not ctype.startswith("image/"):
        if ctype == "application/octet-stream" and re.search(
            r"\.(jpe?g|png|gif|webp|bmp)(\?|$)", url, re.I
        ):
            ctype = "image/jpeg"
        else:
            raise ValueError("目标不是图片: " + ctype)
    if len(r.content) > MAX_PROXY_BYTES:
        raise ValueError("图片超过大小限制")
    return r.content, ctype


def api_upload(task_id, seq, ext, body):
    from vercel_blob import put

    ext = ext if ext in ("jpg", "png", "gif", "webp") else "jpg"
    blob = put(
        f"crawl/{task_id}/{seq}.{ext}",
        body,
        {"addRandomSuffix": "false", "cacheControlMaxAge": "3600"},
    )
    return {"url": blob["url"]}


def api_cleanup(prefix):
    from vercel_blob import delete, list

    data = list({"prefix": prefix})
    blobs = data.get("blobs") or []
    urls = [b["url"] for b in blobs]
    deleted = 0
    if urls:
        delete(urls)
        deleted = len(urls)
    return {"deleted": deleted}


def ok_json(payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return body, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
    }


def err_json(status, msg, error_type=None):
    payload = {"error": msg}
    if error_type:
        payload["error_type"] = error_type
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return body, {
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(body)),
    }, status


def classify_error(e):
    """将异常分类为 error_type"""
    msg = str(e).lower()
    if "timeout" in msg or "timed out" in msg:
        return "timeout"
    if "connection" in msg and ("refused" in msg or "reset" in msg or "abort" in msg):
        return "connection_error"
    if "connection" in msg and ("closed" in msg or "eof" in msg):
        return "connection_closed"
    if "403" in msg or "forbidden" in msg or "block" in msg:
        return "source_blocked"
    if "ssl" in msg or "tls" in msg:
        return "ssl_error"
    if "dns" in msg or "resolve" in msg:
        return "dns_error"
    if "json" in msg or "parse" in msg or "decode" in msg:
        return "parse_error"
    if "not found" in msg or "404" in msg:
        return "not_found"
    return "unknown"
