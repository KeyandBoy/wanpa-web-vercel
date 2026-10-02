"""随机图片/视频源（free-api 系接口）。

这批接口的共同点：不支持关键词、不支持分页、每次返回随机内容。
调用方约定：
- 忽略 keyword
- 单条随机型循环凑批（去重），批量型按 page 本地切片
- 调用方必须跳过 _search_cache，否则 5 分钟内永远返回同一批「随机」结果
"""

import re
import threading
from concurrent.futures import ThreadPoolExecutor

IMAGE_RANDOM_SOURCES = ("dogceo", "catapi", "bingwp", "bingbg", "picsum")
VIDEO_RANDOM_SOURCES = ("xjj",)

IMAGE_RANDOM_SET = frozenset(IMAGE_RANDOM_SOURCES)
VIDEO_RANDOM_SET = frozenset(VIDEO_RANDOM_SOURCES)

# 每次只回 1 条、必须循环凑批的源
_LOOP_SOURCES = frozenset({"dogceo", "catapi"})
# 一次回一批、按 page 本地切片的源
_SLICE_SOURCES = frozenset({"bingwp", "bingbg", "picsum"})

_LOOP_MAX = 12
_LOOP_WORKERS = 4
_VIDEO_MAX = 12
_VIDEO_WORKERS = 6
_DEFAULT_COUNT = 12
_PICSUM_MAX_LIMIT = 100

_PAGE_CACHE = {}
_PAGE_CACHE_LOCK = threading.Lock()
_PAGE_CACHE_TTL = 60

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}


def is_random_image(source):
    return source in IMAGE_RANDOM_SET


def is_random_video(source):
    return source in VIDEO_RANDOM_SET


def _http_json(url, params=None, timeout=20):
    from http_util import http_get

    r = http_get(url, params=params, timeout=timeout, retries=2, headers=_HEADERS)
    return r.json()


def _norm_count(count, default=_DEFAULT_COUNT, cap=None):
    try:
        n = int(count or 0)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = default
    if cap:
        n = min(n, cap)
    return n


def _cached_json(url, ttl=_PAGE_CACHE_TTL):
    import time

    now = time.time()
    with _PAGE_CACHE_LOCK:
        hit = _PAGE_CACHE.get(url)
        if hit and now - hit[0] < ttl:
            return hit[1]
    data = _http_json(url, timeout=30)
    with _PAGE_CACHE_LOCK:
        _PAGE_CACHE[url] = (now, data)
    return data


def _bing_dims(url):
    m = re.search(r"_(\d{3,4})x(\d{3,4})\.", url or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _loop_once(source):
    """单条随机型：请求一次拿 1 条，拿不到返回 None"""
    if source == "dogceo":
        data = _http_json("https://dog.ceo/api/breeds/image/random")
        url = (data or {}).get("message") or ""
        if not url.startswith("http"):
            return None
        breed = ""
        m = re.search(r"/breeds/([^/]+)/", url)
        if m:
            breed = m.group(1).replace("-", " ")
        return {"url": url, "title": ("狗狗 " + breed).strip(), "width": None, "height": None}
    if source == "catapi":
        data = _http_json("https://api.thecatapi.com/v1/images/search")
        if not isinstance(data, list) or not data:
            return None
        one = data[0] or {}
        url = one.get("url") or ""
        if not url.startswith("http"):
            return None
        return {
            "url": url,
            "title": "猫咪随机图",
            "width": one.get("width"),
            "height": one.get("height"),
        }
    raise ValueError("不支持的随机源: " + str(source))


def _loop_batch(source, count):
    n = _norm_count(count, cap=_LOOP_MAX)
    got = []
    with ThreadPoolExecutor(max_workers=_LOOP_WORKERS) as ex:
        for item in ex.map(lambda _: _loop_once(source), range(n)):
            if item and item.get("url"):
                got.append(item)
    return _dedupe(got)


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def _slice_bingwp(page, count):
    """Bing 壁纸全量库（1616+ 张），本地按 page 切片"""
    data = _cached_json("https://raw.onmicrosoft.cn/Bing-Wallpaper-Action/main/data/zh-CN_all.json")
    rows = data.get("data") or []
    total = len(rows)
    n = _norm_count(count)
    start = (max(page, 1) - 1) * n
    items = []
    for row in rows[start:start + n]:
        url = row.get("url") or ""
        if not url:
            continue
        w, h = _bing_dims(url)
        title = row.get("title") or row.get("copyright") or "Bing 壁纸"
        items.append({"url": url, "title": title, "width": w, "height": h})
    return items, start + len(items) < total


def _slice_bingbg(page, count):
    """Bing 每日壁纸（仅当日几张），本地按 page 切片"""
    data = _http_json("https://api.asilu.com/bg/", timeout=25)
    rows = data.get("images") or []
    total = len(rows)
    n = _norm_count(count)
    start = (max(page, 1) - 1) * n
    items = []
    for row in rows[start:start + n]:
        url = row.get("url") or ""
        if not url:
            continue
        w, h = _bing_dims(url)
        items.append({
            "url": url,
            "title": row.get("copyright") or "Bing 每日壁纸",
            "width": w,
            "height": h,
        })
    return items, start + len(items) < total


def _slice_picsum(page, count):
    """Picsum 图库：/v2/list 真分页，自带 width/height/author"""
    n = _norm_count(count, cap=_PICSUM_MAX_LIMIT)
    rows = _http_json(
        "https://picsum.photos/v2/list",
        params={"page": max(page, 1), "limit": n},
        timeout=25,
    )
    items = []
    for row in rows or []:
        url = row.get("download_url") or ""
        if not url:
            continue
        author = row.get("author") or ""
        items.append({
            "url": url,
            "title": (author + " · Picsum").strip(" ·") or "Picsum 随机图",
            "width": row.get("width"),
            "height": row.get("height"),
        })
    return items, len(items) >= n


def fetch_images(source, page=1, count=None):
    """随机图片源 -> (items, has_more)。忽略 keyword，由调用方跳过缓存。"""
    if source in _LOOP_SOURCES:
        # 单条随机：每次都新内容，永远有下一页
        return _loop_batch(source, count), True
    if source == "bingwp":
        return _slice_bingwp(page, count)
    if source == "bingbg":
        return _slice_bingbg(page, count)
    if source == "picsum":
        return _slice_picsum(page, count)
    raise ValueError("不支持的随机源: " + str(source))


def _loop_video_once():
    data = _http_json("https://api.kuleu.com/api/MP4_xiaojiejie", params={"type": "json"})
    url = (data or {}).get("mp4_video") or ""
    if not url.startswith("http"):
        return None
    return {
        "title": "高质量小姐姐",
        "url": url,
        "duration_text": "",
        "duration": 0,
        "thumb": None,
        "source": "xjj",
    }


def fetch_videos(source, count=8):
    """随机视频源 -> items。忽略 keyword，由调用方跳过缓存。"""
    if source != "xjj":
        raise ValueError("不支持的随机视频源: " + str(source))
    target = _norm_count(count, default=8, cap=_VIDEO_MAX)
    got = []
    for _ in range(3):  # 去重后不足时再补两轮，防止随机接口重复返回同一条
        need = target - len(got)
        if need <= 0:
            break
        with ThreadPoolExecutor(max_workers=_VIDEO_WORKERS) as ex:
            for item in ex.map(lambda _: _loop_video_once(), range(need)):
                if item:
                    got.append(item)
        got = _dedupe(got)
    return got[:target]
