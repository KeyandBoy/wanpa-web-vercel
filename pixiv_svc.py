import os
import re
from urllib.parse import quote

from trans_svc import to_en

_proxy_p = None


def _proxy():
    global _proxy_p
    if _proxy_p is not None:
        return _proxy_p
    p = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    _proxy_p = p or ""
    return _proxy_p


def get_cookie():
    c = os.environ.get("PIXIV_PHPSESSID") or ""
    return c.strip() or None


def resolve_original(url):
    """把 pximg 的预览图 URL 升级为原图 URL（经详情接口获取，失败则原样返回）。"""
    m = re.search(r"/img/[0-9/]+/(\d+)_p\d+", url)
    if not m:
        return url
    pid = m.group(1)
    cookie = get_cookie()
    if not cookie:
        return url
    try:
        from curl_cffi import requests as cr

        proxies = None
        p = _proxy()
        if p:
            proxies = {"http": p, "https": p}
        r = cr.get(
            "https://www.pixiv.net/ajax/illust/" + pid,
            headers={
                "Referer": "https://www.pixiv.net/",
                "Accept": "application/json",
                "Cookie": "PHPSESSID=" + cookie,
            },
            impersonate="chrome131",
            timeout=20,
            proxies=proxies,
        )
        if r.status_code != 200:
            return url
        urls = (r.json().get("body") or {}).get("urls") or {}
        return urls.get("original") or url
    except Exception:
        return url


def search_pixiv(keyword, page_no, count=20):
    from trans_svc import has_chinese

    kw = to_en(keyword) if has_chinese(keyword) else keyword
    cookie = get_cookie()
    if not cookie:
        raise ValueError("未配置 PIXIV_PHPSESSID（在 Vercel 环境变量设置，取值=浏览器登录后的 PHPSESSID）")
    try:
        from curl_cffi import requests as cr
    except ImportError:
        raise ValueError("缺少 curl_cffi 依赖")
    proxies = None
    p = _proxy()
    if p:
        proxies = {"http": p, "https": p}
    r = cr.get(
        "https://www.pixiv.net/ajax/search/artworks/" + quote(kw),
        params={
            "word": kw,
            "order": "date_d",
            "mode": "all",
            "p": page_no,
            "s_mode": "s_tag",
            "type": "all",
            "lang": "zh",
        },
        headers={
            "Referer": "https://www.pixiv.net/",
            "Accept": "application/json",
            "Cookie": "PHPSESSID=" + cookie,
        },
        impersonate="chrome131",
        timeout=30,
        proxies=proxies,
    )
    if r.status_code != 200:
        raise ValueError("Pixiv 搜索失败(HTTP %d，cookie 可能已失效)" % r.status_code)
    try:
        data = r.json()
    except ValueError:
        raise ValueError("Pixiv 返回无法解析")
    body = data.get("body") or {}
    illust = body.get("illustManga") or {}
    items = []
    seen = set()
    for d in (illust.get("data") or [])[:count]:
        u = d.get("urlOriginal") or d.get("url")
        if not u or not u.startswith("http"):
            continue
        if u in seen:
            continue
        seen.add(u)
        items.append({
            "url": u,
            "title": d.get("title") or keyword,
            "width": None,
            "height": None,
        })
    if not items:
        raise ValueError("Pixiv 没有搜到结果（cookie 未登录、R-18 显示未开启，或关键词无结果）")
    return items
