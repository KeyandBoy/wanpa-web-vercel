import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from io import BytesIO
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

WATERMARK_MARKS = ("watermark", "shuiyin", "logo", "mark", "sign")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")


def http_get(url, params=None, timeout=20, retries=3, session=None, verify=True, headers=None):
    last = None
    for i in range(retries):
        try:
            client = session if session is not None else requests
            r = client.get(
                url,
                headers=headers or HEADERS,
                params=params,
                timeout=timeout,
                verify=verify,
            )
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def search_bing_page(keyword, page, per_page=35, session=None):
    r = http_get(
        "https://www.bing.com/images/search",
        params={"q": keyword, "first": page * per_page, "count": per_page},
        session=session,
    )
    soup = BeautifulSoup(r.text, "html.parser")
    items = []
    for a in soup.select("a.iusc"):
        m = a.get("m")
        if not m:
            continue
        try:
            data = json.loads(m)
        except (json.JSONDecodeError, ValueError):
            continue
        img = data.get("murl") or data.get("purl")
        if img:
            items.append(
                {
                    "url": img,
                    "title": a.get("t", "") or keyword,
                    "width": data.get("mw"),
                    "height": data.get("mh"),
                }
            )
    return items


def _bing_session():
    try:
        from curl_cffi import requests as cr

        s = cr.Session(impersonate="chrome")
    except Exception:
        s = requests.Session()
    try:
        s.get("https://www.bing.com", timeout=20)
    except Exception:
        pass
    return s


def search_bing(keyword, count, delay):
    session = _bing_session()
    results = []
    page = 0
    while len(results) < count:
        found = search_bing_page(keyword, page, session=session)
        if not found:
            break
        results.extend(found)
        page += 1
        time.sleep(delay * random.uniform(0.5, 1.5))
    try:
        session.close()
    except Exception:
        pass
    return results[:count]


def search_baidu_page(keyword, page, per_page=30):
    r = http_get(
        "https://image.baidu.com/search/acjson",
        params={
            "tn": "resultjson_com",
            "ipn": "rj",
            "word": keyword,
            "pn": page * per_page,
            "rn": per_page,
        },
    )
    data = r.json()
    items = []
    for item in data.get("data") or []:
        if not item:
            continue
        img = None
        for key in ("middleURL", "thumbURL", "objURL"):
            url = item.get(key)
            if url and url.startswith(("http://", "https://")):
                img = url
                break
        if not img:
            for rep in item.get("replaceUrl") or []:
                if (rep.get("ObjUrl") or "").startswith(("http://", "https://")):
                    img = rep["ObjUrl"]
                    break
        if not img:
            continue
        items.append(
            {
                "url": img,
                "title": item.get("fromPageTitle") or keyword,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    return items


def search_baidu(keyword, count, delay):
    results = []
    page = 0
    while len(results) < count:
        found = search_baidu_page(keyword, page)
        if not found:
            break
        results.extend(found)
        page += 1
        time.sleep(delay * random.uniform(0.8, 1.6))
    return results[:count]


_pixabay_session = None


def _get_pixabay_session():
    global _pixabay_session
    if _pixabay_session is None:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": "https://pixabay.com/",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Dest": "document",
            }
        )
        try:
            session.get("https://pixabay.com/", timeout=20)
        except requests.RequestException:
            pass
        _pixabay_session = session
    return _pixabay_session


def pixabay_page(keyword, page, api_key, per_page=200):
    if api_key:
        r = http_get(
            "https://pixabay.com/api/",
            params={
                "key": api_key,
                "q": keyword,
                "per_page": per_page,
                "page": page,
                "image_type": "photo",
            },
        )
        hits = r.json().get("hits") or []
        items = []
        for h in hits:
            url = h.get("largeImageURL") or h.get("webformatURL")
            if url:
                items.append(
                    {
                        "url": url,
                        "title": h.get("tags") or keyword,
                        "width": h.get("imageWidth"),
                        "height": h.get("imageHeight"),
                        "page": h.get("pageURL"),
                    }
                )
        return items, len(hits) >= per_page

    session = _get_pixabay_session()
    base_url = f"https://pixabay.com/images/search/{quote(keyword)}/"
    url = base_url if page == 1 else f"{base_url}?pagi={page}"
    r = http_get(url, timeout=20, session=session)
    by_id = {}
    raw_urls = set(re.findall(r"https://cdn\.pixabay\.com/photo/[^\s\"']+", r.text))
    for u in raw_urls:
        u = u.split("?")[0]
        m = re.search(r"(.*)_(\d+)(?:_(\d+))?\.(jpg|png)$", u)
        if not m:
            continue
        base, w = m.group(1), int(m.group(2))
        h = int(m.group(3)) if m.group(3) else None
        cur = by_id.get(base)
        if cur is None or w > cur["width"]:
            by_id[base] = {"url": u, "width": w, "height": h}
    items = [
        {"url": v["url"], "title": keyword, "width": v["width"], "height": v["height"]}
        for v in by_id.values()
    ]
    return items, page == 1 and bool(items)


def search_pixabay(keyword, count, api_key, delay):
    results = []
    page = 1
    while len(results) < count:
        items, has_more = pixabay_page(keyword, page, api_key)
        if not items:
            break
        results.extend(items)
        if not has_more:
            break
        page += 1
        time.sleep(delay * random.uniform(0.8, 1.6))
    return results[:count]


# ========== 扩展数据源 ==========

def search_sogou_page(keyword, page, per_page=48):
    """搜狗图片: pic.sogou.com/napi JSON 接口(风控严格)"""
    r = http_get(
        "https://pic.sogou.com/napi/pc/searchList",
        params={"mode": 1, "query": keyword, "start": page * per_page, "xml_len": per_page},
        retries=1,
    )
    d = r.json()
    if not (d.get("data") or {}).get("items"):
        raise ValueError("搜狗图片风控严格(forbid), 可能暂时无法使用")
    items = []
    for item in d["data"]["items"]:
        url = item.get("picUrl") or item.get("thumbUrl") or ""
        if not url.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "url": url,
                "title": item.get("title") or keyword,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    return items


def search_so360_page(keyword, page, per_page=60):
    """360图片: image.so.com/j JSON 接口"""
    r = http_get(
        "https://image.so.com/j",
        params={"q": keyword, "pn": per_page, "sn": page * per_page},
    )
    data = r.json()
    items = []
    for item in data.get("list") or []:
        url = item.get("img") or item.get("thumb") or ""
        if not url.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "url": url,
                "title": item.get("title") or keyword,
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    return items


def search_huaban_page(keyword, page, per_page=20):
    """花瓣网: 需要登录, 失败时抛异常提示"""
    try:
        r = http_get(
            "https://api.huaban.com/search",
            params={"q": keyword, "per_page": per_page, "page": page + 1},
            retries=1,
        )
    except Exception as e:
        raise ValueError(f"花瓣网访问失败: {e}") from e
    if r.status_code in (401, 403):
        raise ValueError("花瓣网需要登录, 无法爬取")
    data = r.json()
    items = []
    for pin in (data.get("pins") or []) if isinstance(data, dict) else []:
        file = pin.get("file") or {}
        url = file.get("real_domain") or ""
        if url:
            url = "https://hbimg.huaban.com/" + url.lstrip("/")
            items.append(
                {"url": url, "title": pin.get("raw_text") or keyword, "width": None, "height": None}
            )
    return items


def search_tuchong_page(keyword, page, per_page=20):
    """图虫: 需登录态, 失败时抛异常提示"""
    try:
        r = http_get(
            "https://tuchong.com/rest-api/v2/search",
            params={"query": keyword, "type": "post", "page": page + 1, "count": per_page},
            retries=1,
        )
    except Exception as e:
        raise ValueError(f"图虫访问失败: {e}") from e
    if r.status_code in (401, 403):
        raise ValueError("图虫需要登录, 无法爬取")
    data = r.json()
    items = []
    for post in ((data.get("data") or {}).get("post_list") or []):
        for img in (post.get("images") or [])[:5]:
            url = img.get("img_id") or img.get("img_url") or ""
            if url.startswith("http"):
                items.append({"url": url, "title": post.get("post_title") or keyword, "width": None, "height": None})
    return items


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


def search_google_page(keyword, page, per_page=20, verify=True):
    """Google 图片: HTML 解析 AF_initDataCallback; 反爬强, 失败返回空"""
    try:
        r = http_get(
            "https://www.google.com/search",
            params={"tbm": "isch", "q": keyword, "start": page * per_page},
            retries=1,
            verify=verify,
        )
    except Exception as e:
        raise ValueError(f"Google 访问失败(可能需要代理): {e}") from e
    if r.status_code != 200 or "AF_initDataCallback" not in r.text:
        raise ValueError("Google 返回验证页或不可用, 可能需要代理")
    text = r.text
    items = []
    seen = set()
    for m in re.finditer(r"data:function\(\)\{return (\[.*?\])\}", text):
        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            continue
        for s in _walk_strings(data):
            if (
                isinstance(s, str)
                and s.startswith(("http://", "https://"))
                and "google" not in s
                and "gstatic" not in s
                and s not in seen
            ):
                seen.add(s)
                items.append({"url": s, "title": keyword, "width": None, "height": None})
    if not items:
        for m in re.finditer(r"https://encrypted-tbn0\.gstatic\.com/images\?q=tbn:[^\"&\\]+", text):
            u = m.group(0)
            if u not in seen:
                seen.add(u)
                items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_yahoo_page(keyword, page, per_page=20):
    """Yahoo 图片: HTML 解析 (curl_cffi 模拟 Chrome TLS 指纹, 绕过 JA3 反爬)"""
    try:
        from curl_cffi import requests as cr

        proxies = {
            k: v
            for k, v in (
                ("http", os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")),
                ("https", os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")),
            )
            if v
        }
        r = cr.get(
            "https://images.search.yahoo.com/search/images",
            params={"p": keyword, "b": page * per_page + 1},
            impersonate="chrome131",
            timeout=20,
            proxies=proxies or None,
        )
        if r.status_code != 200:
            raise ValueError(f"Yahoo 返回 {r.status_code}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Yahoo 访问失败(可能需要代理): {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'data-src="(https?://[^"]+)"', r.text):
        u = m.group(1)
        if u in seen or not u.startswith(("http://", "https://")):
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    for m in re.finditer(r'<img[^>]+src="(https?://tse[^"]+)"', r.text):
        u = m.group(1)
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_openverse_page(keyword, page, per_page=20):
    """Openverse 聚合图库: 官方开放 JSON API (免 key)"""
    try:
        r = http_get(
            "https://api.openverse.org/v1/images/",
            params={"q": keyword, "page": page, "page_size": per_page},
            retries=1,
        )
        data = r.json()
    except Exception as e:
        raise ValueError(f"Openverse 访问失败: {e}") from e
    items = []
    for hit in data.get("results") or []:
        url = hit.get("url")
        if url:
            items.append(
                {
                    "url": url,
                    "title": hit.get("title") or keyword,
                    "width": None,
                    "height": None,
                }
            )
    return items


def search_wikimedia_page(keyword, page, per_page=20):
    """Wikimedia Commons: 官方 API (免 key), 百科大图"""
    try:
        r = http_get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": keyword,
                "gsrlimit": per_page,
                "gsrnamespace": 6,
                "gsroffset": (page - 1) * per_page,
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "format": "json",
            },
            retries=1,
        )
        data = r.json()
    except Exception as e:
        raise ValueError(f"Wikimedia 访问失败: {e}") from e
    items = []
    for p in (data.get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        url = ii.get("url") or ""
        mime = ii.get("mime") or ""
        if url and mime.startswith("image/") and mime not in ("image/svg+xml", "image/tiff"):
            items.append(
                {
                    "url": url,
                    "title": (p.get("title") or "").replace("File:", "") or keyword,
                    "width": ii.get("width"),
                    "height": ii.get("height"),
                }
            )
    return items


def search_wallhaven_page(keyword, page, per_page=20):
    """Wallhaven 壁纸: 官方 JSON API (免 key)"""
    try:
        r = http_get(
            "https://wallhaven.cc/api/v1/search",
            params={"q": keyword, "page": page, "atleast": "1920x1080"},
            retries=1,
        )
        data = r.json()
    except Exception as e:
        raise ValueError(f"Wallhaven 访问失败: {e}") from e
    items = []
    for hit in data.get("data") or []:
        url = hit.get("path")
        if url:
            items.append(
                {
                    "url": url,
                    "title": keyword,
                    "width": hit.get("dimension_x"),
                    "height": hit.get("dimension_y"),
                }
            )
    return items


def search_pxhere_page(keyword, page, per_page=20):
    """pxhere: CC0 摄影图库 HTML"""
    try:
        r = http_get(
            "https://pxhere.com/zh/search",
            params={"q": keyword, "page": page},
            retries=1,
        )
        urls = re.findall(r'src="(https://c\.pxhere\.com/photos/[^"]+)"', r.text)
    except Exception as e:
        raise ValueError(f"pxhere 访问失败: {e}") from e
    items, seen = [], set()
    for u in urls:
        u = u.split("!")[0]
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_duitang_page(keyword, page, per_page=20):
    """堆糖: 中文美图, 公开 JSON 接口 (免 key)"""
    try:
        r = http_get(
            "https://www.duitang.com/napi/blog/list/by_search/",
            params={"kw": keyword, "start": (page - 1) * 24, "limit": 24},
            retries=1,
        )
        data = r.json()
    except Exception as e:
        raise ValueError(f"堆糖访问失败: {e}") from e
    items = []
    for it in data.get("data", {}).get("object_list") or []:
        photo = it.get("photo") or {}
        url = photo.get("path")
        if url:
            items.append(
                {
                    "url": url,
                    "title": keyword,
                    "width": photo.get("width"),
                    "height": photo.get("height"),
                }
            )
    return items


def search_pexels_page(keyword, page, per_page=20):
    """Pexels: 免版权摄影图库 HTML"""
    try:
        r = http_get(
            "https://www.pexels.com/search/" + quote(keyword) + "/",
            params={"page": page},
            retries=1,
        )
        urls = re.findall(
            r"https://images\.pexels\.com/photos/\d+/pexels-photo-\d+\.jpeg", r.text
        )
    except Exception as e:
        raise ValueError(f"Pexels 访问失败: {e}") from e
    items, seen = [], set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_giphy_page(keyword, page, per_page=20):
    """Giphy: 动图库 HTML (原图 gif)"""
    try:
        r = http_get(
            "https://giphy.com/search/" + quote(keyword),
            retries=1,
        )
        urls = re.findall(r"https://media\d+\.giphy\.com/media/[^\"']+/giphy\.gif", r.text)
    except Exception as e:
        raise ValueError(f"Giphy 访问失败: {e}") from e
    items, seen = [], set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_wallhere_page(keyword, page, per_page=20):
    """Wallhere 壁纸库: HTML (需代理, 中文标签页可用)"""
    try:
        r = http_get(
            "https://wallhere.com/zh/search",
            params={"q": keyword, "page": page},
            retries=1,
        )
        urls = re.findall(r"https://c\.wallhere\.com/photos/[^\"']+\.jpg", r.text)
    except Exception as e:
        raise ValueError(f"Wallhere 访问失败(可能需要代理): {e}") from e
    items, seen = [], set()
    for u in urls:
        u = u.split("!")[0]
        if u in seen or not u.endswith(".jpg"):
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_yande_page(keyword, page, per_page=20):
    """yande.re: 动漫壁纸站公开 JSON API (需代理)"""
    try:
        r = http_get(
            "https://yande.re/post.json",
            params={"tags": keyword, "limit": per_page, "page": page},
            retries=1,
        )
        data = r.json()
    except Exception as e:
        raise ValueError(f"yande.re 访问失败(可能需要代理): {e}") from e
    items = []
    for hit in data if isinstance(data, list) else []:
        url = hit.get("sample_url") or hit.get("file_url")
        if url:
            items.append(
                {
                    "url": url,
                    "title": keyword,
                    "width": hit.get("sample_width") or hit.get("width"),
                    "height": hit.get("sample_height") or hit.get("height"),
                }
            )
    return items


def search_youtube_page(keyword, page, per_page=20):
    """YouTube 缩略图: 解析 ytInitialData 取视频封面"""
    try:
        r = http_get(
            "https://www.youtube.com/results",
            params={"search_query": keyword, "page": page},
            retries=1,
        )
    except Exception as e:
        raise ValueError(f"YouTube 访问失败(可能需要代理): {e}") from e
    if "ytInitialData" not in r.text:
        raise ValueError("YouTube 页面结构异常(可能需要代理)")
    m = re.search(r"var ytInitialData = (\{.*?\});", r.text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    items = []
    seen = set()
    video_ids = set()

    def walk(node):
        if isinstance(node, dict):
            vr = node.get("videoRenderer")
            if isinstance(vr, dict):
                vid = vr.get("videoId")
                thumbs = (vr.get("thumbnail") or {}).get("thumbnails") or []
                title = (((vr.get("title") or {}).get("runs") or [{}])[0].get("text")) or keyword
                if vid and vid not in video_ids:
                    video_ids.add(vid)
                    url = None
                    for t in reversed(thumbs):
                        u = t.get("url") or ""
                        if u.startswith("http"):
                            url = u
                            break
                    if url:
                        url = url.split("?")[0]
                        if url not in seen:
                            seen.add(url)
                            items.append({"url": url, "title": title, "width": None, "height": None})
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return items[:per_page]










def _direct_session():
    """国内站直连 session（不走环境代理）"""
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    return s


_xiurenai_cache = {}


def _interleave(pairs):
    """把 (group, url) 对按图集交错排列，让每页混合多个图集"""
    groups = {}
    order = []
    for g, u in pairs:
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(u)
    flat = []
    i = 0
    while True:
        got = False
        for g in order:
            if i < len(groups[g]):
                flat.append((g, groups[g][i]))
                got = True
        if not got:
            break
        i += 1
    return flat


def search_xiurenai_page(keyword, page, per_page=20):
    """xiurenai.com: 秀人网写真，搜索图集并返回图集内高清大图（国内直连）"""
    global _xiurenai_cache
    if keyword not in _xiurenai_cache:
        s = _direct_session()
        try:
            r = s.get("https://www.xiurenai.com/", params={"s": keyword}, timeout=25)
        except Exception as e:
            raise ValueError(f"秀人网访问失败: {e}") from e
        detail_links = []
        for m in re.finditer(r'<a[^>]+href="(https?://www\.xiurenai\.com/other/iess/\d+\.html)"[^>]*>\s*<img[^>]+src="(https?://xr\.afxfl\.com[^"]+)"', r.text):
            detail_links.append(m.group(1))
        all_imgs = []
        for dl in detail_links[:10]:
            try:
                dr = s.get(dl, timeout=25)
            except Exception:
                continue
            for m in re.finditer(r'<img[^>]+(?:src|data-src|data-original)="(https?://xr\.afxfl\.com/uploads/[^"]+)"', dr.text):
                u = m.group(1)
                if (dl, u) not in all_imgs:
                    all_imgs.append((dl, u))
        _xiurenai_cache[keyword] = _interleave(all_imgs)
    pairs = _xiurenai_cache[keyword]
    start = max(page - 1, 0) * per_page
    slice_ = pairs[start : start + per_page]
    return [{"url": u, "title": keyword, "width": None, "height": None, "group": dl} for dl, u in slice_]










def search_foamgirl_page(keyword, page, per_page=20):
    """foamgirl.net: 亚洲性感写真，去掉缩略后缀拿原图"""
    try:
        r = http_get("https://foamgirl.net/", params={"s": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"FoamGirl 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<img[^>]+(?:src|data-src|data-original)="(https?://cdn\.foamgirl\.net[^"]+)"', r.text):
        u = m.group(1).split("!")[0]
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
        if len(items) >= per_page:
            break
    return items


def search_pornhub_page(keyword, page, per_page=20):
    """Pornhub: Cloudflare 反爬, 尽力尝试"""
    try:
        r = http_get(
            "https://www.pornhub.com/video/search",
            params={"search": keyword, "page": page + 1},
            retries=1,
        )
    except Exception as e:
        raise ValueError(f"Pornhub 访问失败(可能有 Cloudflare 风控): {e}") from e
    items = []
    seen = set()
    cards = re.findall(r'<li class="pcVideoListItem.*?</li>', r.text, re.S)
    for card in cards:
        m = re.search(r'<img[^>]+src="(https?://[^"]+)"', card)
        if not m:
            continue
        u = m.group(1)
        if (
            u in seen
            or "pix-cdn77.phncdn.com" in u
            or "/images/categories/" in u
            or "/www-static/" in u
        ):
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
        if len(items) >= per_page:
            break
    return items[:per_page]


def search_pornhub_albums_page(keyword, page, per_page=20):
    """cn.pornhub.com/albums: Pornhub 图集，进图集提取大图"""
    try:
        r = http_get("https://cn.pornhub.com/albums", params={"search": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"Pornhub 图集访问失败: {e}") from e
    albums = list(dict.fromkeys(re.findall(r'href="(/album/\d+)"', r.text)))[:8]
    items = []
    seen = set()
    for ap in albums:
        try:
            ar = http_get("https://cn.pornhub.com" + ap, timeout=25)
        except Exception:
            continue
        title_m = re.search(r'<title>(.*?)</title>', ar.text, re.S)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip()[:100] if title_m else keyword
        for m in re.finditer(r'<img[^>]+(?:src|data-src|data-image)="(https?://(?:pix-fl|ei\.phncdn)[^"]+)"', ar.text):
            u = m.group(1)
            if u in seen or "/thumb" in u or "www-static" in u or "/images/" in u:
                continue
            seen.add(u)
            items.append({"url": u, "title": title, "width": None, "height": None, "group": ap})
            if len(items) >= per_page:
                break
        if len(items) >= per_page:
            break
    return items


def search_pornpics_page(keyword, page, per_page=20):
    """pornpics.com: 色情图片搜索"""
    try:
        r = http_get("https://www.pornpics.com/", params={"q": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"Pornpics 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<img[^>]+(?:src|data-src)="(https?://cdni\.pornpics\.com[^"]+)"[^>]*alt="([^"]*)"', r.text):
        u, alt = m.group(1), m.group(2)
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": alt or keyword, "width": None, "height": None})
        if len(items) >= per_page:
            break
    return items


def search_photos18_page(keyword, page, per_page=20):
    """photos18.com: 色情图片搜索"""
    try:
        r = http_get("https://www.photos18.com/", params={"q": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"Photos18 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<img[^>]+(?:src|data-src)="(/images/node/[^"]+)"', r.text):
        p = m.group(1).split("?")[0]
        u = "https://www.photos18.com" + p
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
        if len(items) >= per_page:
            break
    return items


def search_asiantolick_page(keyword, page, per_page=20):
    """asiantolick.com: 亚洲色情图片（原图在 telegra.ph）"""
    try:
        r = http_get("https://asiantolick.com/search", params={"q": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"AsianToLick 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<img[^>]+(?:src|data-src)="(https?://wsrv\.nl[^"]+)"', r.text):
        u = m.group(1)
        mm = re.search(r"url=([^&]+)", u)
        if mm:
            orig = requests.utils.unquote(mm.group(1))
            if orig.startswith("http") and orig not in seen:
                seen.add(orig)
                items.append({"url": orig, "title": keyword, "width": None, "height": None})
                if len(items) >= per_page:
                    break
    return items


def search_xxknit_page(keyword, page, per_page=20):
    """xx.knit.bid (爱妹国写真/Cosplay): SSR 搜索，返回图集封面图"""
    from curl_cffi import requests as cr

    url = f"https://xx.knit.bid/zh-hant/search/?s={requests.utils.quote(keyword)}"
    try:
        r = cr.get(url, impersonate="chrome131", timeout=20)
        if r.status_code != 200:
            raise ValueError(f"xx.knit.bid 返回 {r.status_code}")
    except Exception as e:
        raise ValueError(f"xx.knit.bid 访问失败: {e}") from e

    items = []
    cards = re.findall(r'<a\s+href="(/zh-hant/topic/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S)
    for href, body in cards:
        m = re.search(r'<img[^>]+src="([^"]+)"[^>]*width="(\d+)"[^>]*height="(\d+)"', body)
        if not m:
            continue
        img_url = m.group(1)
        if img_url.startswith("/"):
            img_url = "https://xx.knit.bid" + img_url
        title_match = re.search(r'<strong[^>]*class="[^"]*topic-entry-title[^"]*"[^>]*>([^<]+)</strong>', body)
        title = (title_match.group(1).strip() if title_match else keyword)
        width = int(m.group(2))
        height = int(m.group(3))
        items.append({"url": img_url, "title": title, "width": width, "height": height, "group": href})
        if len(items) >= per_page:
            break
    return items


def search_unsplash_page(keyword, page, api_key, per_page=20):
    """Unsplash: 官方 API (需 key), 无 key 时尝试站内 napi"""
    if api_key:
        try:
            r = http_get(
                "https://api.unsplash.com/search/photos",
                params={"query": keyword, "page": page, "per_page": per_page},
                headers={**HEADERS, "Authorization": f"Client-ID {api_key}"},
                retries=1,
            )
        except Exception as e:
            raise ValueError(f"Unsplash API 访问失败: {e}") from e
        items = []
        for hit in r.json().get("results") or []:
            urls = hit.get("urls") or {}
            url = urls.get("full") or urls.get("regular") or ""
            if url:
                items.append(
                    {
                        "url": url,
                        "title": hit.get("alt_description") or keyword,
                        "width": hit.get("width"),
                        "height": hit.get("height"),
                    }
                )
        return items
    try:
        r = http_get(
            "https://unsplash.com/napi/search/photos",
            params={"query": keyword, "page": page, "per_page": per_page, "xp": ""},
            retries=1,
        )
        if r.status_code == 401 or "within.website" in r.url:
            raise ValueError("Unsplash 无 key 被防护墙拦截")
        data = r.json()
        items = []
        for hit in (data.get("results") or []):
            urls = hit.get("urls") or {}
            url = urls.get("full") or urls.get("regular") or ""
            if url:
                items.append(
                    {
                        "url": url,
                        "title": hit.get("alt_description") or keyword,
                        "width": hit.get("width"),
                        "height": hit.get("height"),
                    }
                )
        return items
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Unsplash 站内接口访问失败: {e}") from e


def search_twitter_page(keyword, page, per_page=20):
    """Twitter/X: 需登录, 仅尝试公开页图提取"""
    try:
        r = http_get(
            "https://x.com/search",
            params={"q": keyword, "f": "image"},
            retries=1,
        )
    except Exception as e:
        raise ValueError(f"Twitter/X 访问失败: {e}") from e
    low = r.text[:3000].lower()
    if "login" in r.url.lower() or "to get started" in low or "auth/login" in low:
        raise ValueError("Twitter/X 需要登录, 无法爬取; 可用「自定义网址」抓取公开帖文内图片")
    items = []
    seen = set()
    for m in re.finditer(r'<img[^>]+src="(https?://pbs\.twimg\.com[^"]+)"', r.text):
        u = m.group(1)
        if u in seen:
            continue
        seen.add(u)
        items.append({"url": u, "title": keyword, "width": None, "height": None})
    return items[:per_page]


def search_pixiv_page(keyword, page, per_page=20):
    """Pixiv 插画: cookie + AJAX 搜索（需配置 PIXIV_PHPSESSID，R18 需在设置开启）"""
    from pixiv_svc import search_pixiv

    return search_pixiv(keyword, max(page - 1, 0) + 1, per_page)


def search_anime_pictures_page(keyword, page, per_page=20):
    """Anime-Pictures: 日系动漫壁纸站 (SvelteKit SPA, 需 curl_cffi 模拟 Chrome 访问海外)"""
    try:
        from curl_cffi import requests as cr

        proxies = {
            k: v
            for k, v in (
                ("http", os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")),
                ("https", os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")),
            )
            if v
        }
        r = cr.get(
            "https://anime-pictures.net/pictures/view_posts/0",
            params={"lang": "zh-cn", "search_tag": keyword, "page": page - 1},
            impersonate="chrome131",
            timeout=25,
            proxies=proxies or None,
        )
        if r.status_code != 200:
            raise ValueError(f"Anime-Pictures 返回 {r.status_code}")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Anime-Pictures 访问失败(可能需要代理): {e}") from e
    items = []
    seen = set()
    # 每张图: <div class="img-block" data-pubtime> 内含 posts/{id} 链接、_bp.avif 大图、
    # _cp.avif 缩略图与 alt="动漫图片 {W}x{H}"。按块解析保证 id/图/尺寸一一对应。
    for blk in re.findall(
        r'<div class="img-block[^"]*"[^>]*>(.*?)</div></div>', r.text, re.S
    ):
        m_bp = re.search(r'(https://opreviews\.anime-pictures\.net/\w{3}/(\w{32})_bp\.avif)', blk)
        m_cp = re.search(r'(https://opreviews\.anime-pictures\.net/\w{3}/(\w{32})_cp\.avif)', blk)
        m_id = re.search(r'\./posts/(\d+)', blk)
        m_dim = re.search(r'<img alt="动漫图片 (\d+)x(\d+)"', blk)
        url = (m_bp or m_cp).group(1)
        if url in seen:
            continue
        seen.add(url)
        items.append(
            {
                "url": url,
                "title": keyword,
                "width": int(m_dim.group(1)) if m_dim else None,
                "height": int(m_dim.group(2)) if m_dim else None,
                "hash": (m_bp or m_cp).group(2),
                "post_id": m_id.group(1) if m_id else None,
                "site": "anime-pictures",
            }
        )
    return items[:per_page]


def search_meitulu_page(keyword, page, per_page=20):
    """meitulu.me: 美图录，关键词搜索返回图集封面图（直连）"""
    try:
        r = http_get(
            "https://meitulu.me/search",
            params={"q": keyword},
            timeout=25,
        )
    except Exception as e:
        raise ValueError(f"美图录访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'href="(/item/[^"]+)"[^>]*>\s*<img[^>]+src="(/poster/[^"]+)"', r.text):
        ih, p = m.group(1), m.group(2)
        if p in seen:
            continue
        seen.add(p)
        items.append({"url": "https://meitulu.me" + p, "title": keyword, "width": None, "height": None, "group": ih})
        if len(items) >= per_page:
            break
    return items


_xsnvshen_cache = {}


def _xsnvshen_sess():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    try:
        s.get("https://www.xsnvshen.co/", timeout=15)
    except Exception:
        pass
    return s


def search_xsnvshen_page(keyword, page, per_page=20):
    """xsnvshen.co: 秀色女神，按关键词匹配图集并返回图集内所有大图（需 session cookie）"""
    global _xsnvshen_cache
    if keyword not in _xsnvshen_cache:
        s = _xsnvshen_sess()
        album_ids = []
        for list_url in ("https://www.xsnvshen.co/album/", "https://www.xsnvshen.co/album/hd/"):
            try:
                r = s.get(list_url, timeout=20)
            except Exception as e:
                raise ValueError(f"秀色女神访问失败: {e}") from e
            for m in re.finditer(
                r'<a[^>]+href="(/album/\d+)"[^>]+class="itemimg"[^>]*title="([^"]*)"[^>]*>',
                r.text,
                re.S,
            ):
                href, title = m.group(1), m.group(2)
                if keyword in title:
                    album_ids.append(href)
        album_ids = album_ids[:8]
        all_imgs = []
        for ap in album_ids:
            try:
                ar = s.get("https://www.xsnvshen.co" + ap, timeout=20)
            except Exception:
                continue
            seen_local = set()
            for mm in re.finditer(r"data-original=['\"](//?img\.xsnvshen\.co/album/[^'\"]+)['\"]", ar.text):
                u = mm.group(1)
                if "/thumb_" in u:
                    continue
                if u.startswith("//"):
                    u = "https:" + u
                if u in seen_local:
                    continue
                seen_local.add(u)
                all_imgs.append((ap, u))
        _xsnvshen_cache[keyword] = _interleave(all_imgs)
    pairs = _xsnvshen_cache[keyword]
    start = max(page - 1, 0) * per_page
    slice_ = pairs[start : start + per_page]
    return [{"url": u, "title": keyword, "width": None, "height": None, "group": ap} for ap, u in slice_]


def search_maccms_pic_page(keyword, page, per_page=20, count=None):
    """hhe62 美图源：关键词匹配分类列表标题，取图集全部图片交错返回"""
    from maccms_svc import search_pic

    return search_pic(keyword, page, per_page, count=count)


def fetch_page_images(url):
    """抓取任意网页, 提取页面内的图片链接"""
    if not url.startswith(("http://", "https://")):
        raise ValueError("无效的网址")
    r = http_get(url, timeout=20, retries=1)
    text = r.text
    items = []
    seen = set()
    candidates = []
    for m in re.finditer(r'<img[^>]+>', text, re.I):
        tag = m.group(0)
        src = ""
        mm = re.search(r'srcset="([^"]+)"', tag)
        if mm:
            first = mm.group(1).split(",")[0].strip().split(" ")[0]
            src = first
        if not src:
            mm = re.search(r'src="([^"]+)"', tag)
            if mm:
                src = mm.group(1)
        if not src:
            continue
        import urllib.parse as _up

        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = _up.urljoin(url, src)
        elif src.startswith("data:"):
            continue
        if not src.startswith(("http://", "https://")):
            continue
        low = src.lower()
        if not any(low.endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
            if "?" not in low and "/" not in low:
                continue
        if any(d in low for d in ("pixel", "spacer", "blank", "1x1", "tracking", "beacon", "logo")):
            continue
        if src in seen:
            continue
        seen.add(src)
        candidates.append(src)
    for u in candidates:
        items.append({"url": u, "title": "", "width": None, "height": None})
    return items


def passes_filter(item, args):
    if args.min_width and item.get("width") and item["width"] < args.min_width:
        return False
    if args.min_height and item.get("height") and item["height"] < args.min_height:
        return False
    if not args.no_watermark_filter:
        text = (item["url"] + " " + item.get("title", "")).lower()
        if any(m in text for m in WATERMARK_MARKS):
            return False
    return True


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def md5_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_existing_hashes(root):
    hashes = set()
    if not os.path.isdir(root):
        return hashes
    for dirpath, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith(IMAGE_EXTS):
                p = os.path.join(dirpath, name)
                try:
                    hashes.add(md5_file(p))
                except OSError:
                    pass
    return hashes


def fetch_image(item):
    r = http_get(item["url"], timeout=25)
    if not r.headers.get("Content-Type", "").startswith("image/"):
        return None
    im = Image.open(BytesIO(r.content))
    im.load()
    fmt = (im.format or "JPEG").lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in ("jpg", "png", "gif", "webp", "bmp"):
        fmt = "jpg"
    return r.content, fmt, im.width, im.height


def download_items(items, folder, keyword, source, args, existing_hashes, progress=None):
    seen = set(existing_hashes)
    lock = threading.Lock()
    meta = []
    downloaded = dup = skipped = 0
    idx = 0

    def emit(event):
        if progress:
            progress(event)

    def work(item):
        try:
            result = fetch_image(item)
            if not result:
                return "skip", item
            content, fmt, w, h = result
            digest = md5_bytes(content)
            with lock:
                if len(meta) >= args.count:
                    return "extra", item
                if digest in seen:
                    return "dup", item
                seen.add(digest)
                nonlocal idx
                idx += 1
                ext = "jpeg" if fmt == "jpg" else fmt
                path = os.path.join(folder, f"{keyword}_{source}_{idx:03d}.{ext}")
                with open(path, "wb") as f:
                    f.write(content)
                entry = {
                    "keyword": keyword,
                    "source": source,
                    "url": item["url"],
                    "path": path,
                    "width": w,
                    "height": h,
                    "size_bytes": len(content),
                    "md5": digest,
                }
                meta.append(entry)
                emit({"type": "file", "path": path, "width": w, "height": h})
                return "ok", item
        except Exception:
            return "fail", item

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        it = iter(items)
        pending = set()
        while True:
            while len(pending) < args.workers * 2:
                try:
                    pending.add(pool.submit(work, next(it)))
                except StopIteration:
                    break
            if not pending:
                break
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                status, _ = fut.result()
                if status == "ok":
                    downloaded += 1
                elif status == "dup":
                    dup += 1
                else:
                    skipped += 1
            if downloaded >= args.count:
                break

    emit({"type": "progress", "downloaded": downloaded, "dup": dup, "skipped": skipped})
    return downloaded, dup, skipped, meta


def crawl_keyword(keyword, sources, args, existing_hashes, progress=None):
    def emit(event):
        if progress:
            progress(event)

    total_meta = []
    emit({"type": "log", "msg": f"===== 关键词: {keyword} ====="})
    for source in sources:
        emit({"type": "log", "msg": f"-- 数据源: {source} --"})
        try:
            if source == "bing":
                items = search_bing(keyword, args.count * 3, args.delay)
            elif source == "baidu":
                items = search_baidu(keyword, args.count * 3, args.delay)
            elif source == "pixabay":
                items = search_pixabay(keyword, args.count * 3, args.pixabay_key, args.delay)
            else:
                emit({"type": "log", "msg": f"未知数据源: {source}, 跳过"})
                continue
        except Exception as e:
            emit({"type": "log", "msg": f"搜索失败: {e}"})
            continue

        items = [i for i in items if passes_filter(i, args)]
        emit({"type": "log", "msg": f"候选图片 {len(items)} 张, 开始下载..."})

        folder = os.path.join(args.output, keyword, source)
        os.makedirs(folder, exist_ok=True)

        downloaded, dup, skipped, meta = download_items(
            items, folder, keyword, source, args, existing_hashes, progress=emit
        )
        total_meta.extend(meta)
        existing_hashes.update(m["md5"] for m in meta)
        emit({"type": "log", "msg": f"下载 {downloaded} | 去重跳过 {dup} | 失败/过滤 {skipped}"})

        if meta:
            mfile = os.path.join(folder, "metadata.json")
            with open(mfile, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            emit({"type": "log", "msg": f"元数据: {mfile}"})

    if total_meta:
        mfile = os.path.join(args.output, keyword, "metadata.json")
        with open(mfile, "w", encoding="utf-8") as f:
            json.dump(total_meta, f, ensure_ascii=False, indent=2)
        emit({"type": "log", "msg": f"汇总元数据: {mfile}"})


def main():
    parser = argparse.ArgumentParser(
        description="多源图片爬取程序: Bing 图片搜索 / 百度图片 / Pixabay"
    )
    parser.add_argument(
        "--keywords", required=True, help="主题关键词, 用逗号分隔, 例如: 猫,狗,日落"
    )
    parser.add_argument(
        "--sites", default="bing,baidu,pixabay", help="数据源, 逗号分隔 (bing,baidu,pixabay)"
    )
    parser.add_argument(
        "--count", type=int, default=100, help="每个关键词每个数据源的目标下载数量 (默认 100)"
    )
    parser.add_argument("--output", default="output", help="保存根目录 (默认 output)")
    parser.add_argument("--min-width", type=int, default=0, help="低于该宽度的图片将被过滤")
    parser.add_argument("--min-height", type=int, default=0, help="低于该高度的图片将被过滤")
    parser.add_argument(
        "--pixabay-key",
        default=os.environ.get("PIXABAY_KEY", ""),
        help="Pixabay 官方 API key, 留空则使用 HTML 解析 (速度较慢)",
    )
    parser.add_argument("--workers", type=int, default=8, help="并发下载线程数 (默认 8)")
    parser.add_argument(
        "--no-watermark-filter", action="store_true", help="关闭水印 URL 过滤"
    )
    parser.add_argument(
        "--no-rescan", action="store_true", help="不扫描已下载图片, 仅本次运行内去重"
    )
    parser.add_argument("--delay", type=float, default=1.0, help="页面抓取间随机延时基数 (秒)")
    args = parser.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    sources = [s.strip().lower() for s in args.sites.split(",") if s.strip()]
    if not keywords or not sources:
        parser.error("--keywords 和 --sites 不能为空")

    existing_hashes = set()
    if not args.no_rescan:
        print("扫描已下载图片进行跨次去重...")
        existing_hashes = build_existing_hashes(args.output)

    for keyword in keywords:
        crawl_keyword(keyword, sources, args, existing_hashes)

    print("\n全部完成。")


if __name__ == "__main__":
    main()
