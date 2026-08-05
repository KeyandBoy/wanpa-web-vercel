import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from curl_cffi import requests as cr
from trans_svc import translate_many, to_en, to_ko, to_ja, to_zh_hant

# 搜索翻译语言：按“网站所在语言”判定（美国/英文站→en、日本/日文站→ja、繁中站→zh_TW）。
# general = 中文站/中文标题为主，直接原词搜不翻译。
SEARCH_LANG = {"en": to_en, "ko": to_ko, "ja": to_ja, "zh_TW": to_zh_hant}

COMICS = {
    "wnacg": {
        "url": "https://www.wnacg.com/",
        "label": "绅士漫画",
        "hosts": ["wnacg.com"],
        "lang": "general",
    },
    "177picyy": {
        "url": "https://www.177picyy.com/",
        "label": "177picyy",
        "hosts": ["177picyy.com"],
        "lang": "ja",
        "force_zh": True,
    },
    "ho5ho": {
        "url": "https://www.ho5ho.com/",
        "label": "ho5ho",
        "hosts": ["ho5ho.com"],
        "lang": "zh_TW",
    },
    "caitlin": {
        "url": "https://caitlin.top/",
        "label": "Caitlin",
        "hosts": ["caitlin.top"],
        "lang": "en",
    },
    "rokuhentai": {
        "url": "https://rokuhentai.com/",
        "label": "Rokuhentai",
        "hosts": ["rokuhentai.com"],
        "lang": "en",
    },
    "h-webtoon": {
        "url": "https://h-webtoon.com/",
        "label": "H-Webtoon",
        "hosts": ["h-webtoon.com"],
        "lang": "general",
    },
    "cartoon18": {
        "url": "https://www.cartoon18.com/",
        "label": "Cartoon18",
        "hosts": ["cartoon18.com"],
        "lang": "ja",
        "force_zh": True,
    },
    "xhentai888": {
        "url": "https://xhentai888.xyz/",
        "label": "xhentai888",
        "hosts": ["xhentai888.xyz"],
        "lang": "general",
        "force_zh": True,
    },
    "sexacg": {
        "url": "https://www.sexacg.xyz/",
        "label": "SexACG",
        "hosts": ["sexacg.xyz"],
        "lang": "general",
    },
    "hentaiclap": {
        "url": "https://hentaiclap.com/",
        "label": "HentaiClap",
        "hosts": ["hentaiclap.com"],
        "lang": "en",
    },
    "hentairun": {
        "url": "https://hentairun.com/",
        "label": "HentaiRun",
        "hosts": ["hentairun.com"],
        "lang": "en",
    },
    "allporncomic": {
        "url": "https://allporncomic.com/",
        "label": "AllPornComic",
        "hosts": ["allporncomic.com"],
        "lang": "en",
    },
    "8muses": {
        "url": "https://8muses.io/",
        "label": "8muses",
        "hosts": ["8muses.io"],
        "lang": "en",
    },
    "ilikecomix": {
        "url": "https://ilikecomix.com/",
        "label": "ILikeComix",
        "hosts": ["ilikecomix.com"],
        "lang": "en",
    },
}

CN_TAGS = ("汉化", "中文本", "中文版", "汉化组", "汉化版", "中文", "中译", "简中", "繁中", "中文化", "汉化中")

# 英文/日文汉化标记（词边界匹配，避免 cn/tl 等子串误判）
CN_EN_RE = re.compile(
    r"(?i)(?:^|[^a-z])(chinese|scanlat\w*|scantlat\w*|translated|translation|scl|cn|tl)(?:[^a-z]|$)"
)


def _is_cn_tag(title):
    t = title or ""
    if any(k in t for k in CN_TAGS):
        return True
    return bool(CN_EN_RE.search(t))

SEARCH_PARAMS = {"f": "_all", "s": "create_time_DESC", "syn": "yes"}


def _proxy():
    import os

    p = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    if p:
        return p
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("PROXY="):
                    return line.strip().split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def _get(url, params=None, referer=None):
    p = _proxy()
    proxies = {"http": p, "https": p} if p else None
    s = cr.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    if referer:
        s.headers.update({"Referer": referer})
    return s.get(
        url,
        params=params,
        impersonate="chrome",
        timeout=25,
        proxies=proxies,
        allow_redirects=True,
    )


def _strip(html):
    s = re.sub(r"<[^>]+>", "", html or "")
    s = s.replace("&nbsp;", " ").replace("&#039;", "'").replace("&amp;", "&").replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", s).strip()


def _clean(t):
    try:
        t = html.unescape(t)
    except Exception:
        pass
    return re.sub(r"\s+", " ", t or "").strip()


def _abs(u, base):
    u = u.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http"):
        return u
    return base.rstrip("/") + ("/" + u.lstrip("/") if u.startswith("/") else u)


def _decode_text(r):
    enc = (getattr(r, "encoding", "") or "").lower()
    if enc and enc not in ("utf-8", "utf8", "ascii"):
        try:
            return r.content.decode(enc, "replace")
        except Exception:
            pass
    try:
        return r.text
    except Exception:
        try:
            return r.content.decode("gbk", "replace")
        except Exception:
            return r.content.decode("utf-8", "replace")


def _paginate(fetch_page, page, per_page, count):
    """fetch_page(p) -> 该页条目列表；跨页聚合到 count 所需数量，返回 (items, has_more)"""
    want = count or per_page
    start = max(page - 1, 0) * want
    all_items = []
    seen = set()
    p = 1
    while len(all_items) < start + want and p <= 30:
        try:
            chunk = fetch_page(p)
        except Exception:
            break
        if not chunk:
            break
        new = 0
        for it in chunk:
            if it["url"] not in seen:
                seen.add(it["url"])
                all_items.append(it)
                new += 1
        if new == 0:
            break
        p += 1
    return all_items[start : start + want], len(all_items) > start + want


def _grab_chapters(chaps, fetcher, limit, workers=6):
    """并发抓取章节页图片列表，拼接为一张大图清单；limit 满足后提前停止"""
    images = []
    for i in range(0, len(chaps), workers):
        if limit and len(images) >= limit:
            break
        batch = chaps[i : i + workers]
        try:
            with ThreadPoolExecutor(max_workers=workers) as ex:
                results = list(ex.map(fetcher, batch))
        except Exception:
            results = []
        for imgs in results:
            if imgs:
                images.extend(imgs)
                if limit and len(images) >= limit:
                    break
    return images


# ============================== wnacg ==============================
def _wnacg_search_page(p, base, keyword):
    r = _get(base + "search/", {**SEARCH_PARAMS, "q": keyword, "p": p})
    if r.status_code != 200:
        return []
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        if not re.match(r"/photos-index-aid-\d+\.html$", href):
            continue
        title = None
        alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner)
        if alt_m:
            title = alt_m.group(1).strip()
        if not title:
            title = re.sub(r"<[^>]+>", "", inner).strip()
        title = _strip(title)
        if len(title) < 2:
            continue
        url = base.rstrip("/") + href
        if url in seen:
            continue
        seen.add(url)
        cover = None
        cm = re.search(r'src=["\']([^"\']+/data/t/[^"\']+)["\']', m.group(0))
        if cm:
            cover = cm.group(1)
            if cover.startswith("//"):
                cover = "https:" + cover
        items.append({"title": title[:120], "url": url, "source": "wnacg", "cover": cover})
    return items


def _wnacg_detail_pic_links(url):
    """优先通过 /photos-item-aid-{aid}.html 获取全部大图 URL；失败时回退到详情页解析"""
    base = re.match(r"https?://[^/]+", url).group(0)
    aid_m = re.search(r"aid-(\d+)", url)
    title = ""
    try:
        r = _get(url)
        if r.status_code == 200:
            title_m = re.search(r"<h2>(.*?)</h2>", r.text, re.S)
            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
    except Exception:
        pass
    if aid_m:
        try:
            it = _get(base + "/photos-item-aid-%s.html" % aid_m.group(1))
            if it.status_code == 200:
                jm = re.search(r'"page_url":\[(.*?)\]', it.text, re.S)
                if jm:
                    urls = []
                    for u in re.findall(r'"(https?://[^"]+|//[^"]+)"', jm.group(1)):
                        if not u.startswith("http"):
                            u = "https:" + u
                        if "logo" in u.lower():
                            continue
                        urls.append(u)
                    urls = list(dict.fromkeys(urls))
                    if urls:
                        return urls, title
        except Exception:
            pass
    try:
        r = _get(url)
    except Exception:
        return [], None
    if r.status_code != 200:
        return [], None
    links = re.findall(r'href="(/photos-view-id-\d+\.html)"', r.text)
    return list(dict.fromkeys(links)), title


def _wnacg_pages(url, limit=None):
    base = re.match(r"https?://[^/]+", url).group(0)
    links, title = _wnacg_detail_pic_links(url)
    if not links:
        raise ValueError("未找到图片列表")
    if links[0].startswith("http"):
        images = links
    else:

        def fetch_one(href):
            try:
                r = _get(base + href)
            except Exception:
                return None
            if r.status_code != 200:
                return None
            m = re.search(r'id="picarea"[^>]+src="([^"]+)"', r.text)
            if not m:
                m = re.search(r'id="imgarea"[^>]*>.*?src="([^"]+)"', r.text, re.S)
            if not m:
                m = re.search(r'img5\.qy0\.ru/data/[^"\']+', r.text)
            if not m:
                return None
            u = m.group(1)
            if u.startswith("//"):
                u = "https:" + u
            elif not u.startswith("http"):
                u = "https:" + u
            return u

        with ThreadPoolExecutor(max_workers=8) as ex:
            images = list(ex.map(fetch_one, links))
        images = [u for u in images if u]
    if not images:
        raise ValueError("未提取到图片地址")
    if limit and limit > 0:
        images = images[:limit]
    return {"title": title or url.split("/")[-1], "images": images}


# ============================== 177picyy ==============================
def _p177_search_page(p, base, keyword):
    url = base if p == 1 else base + "page/%d/" % p
    r = _get(url, params={"s": keyword})
    if r.status_code != 200:
        return []
    items = []
    for art in re.finditer(r"<article[^>]*>(.*?)</article>", r.text, re.S):
        block = art.group(1)
        hm = re.search(r'rel="bookmark" href="([^"]+)"', block)
        if not hm:
            continue
        tm = re.search(r"<h2[^>]*>\s*<a[^>]*>(.*?)</a>", block, re.S)
        title = _strip(tm.group(1)) if tm else ""
        if len(title) < 2:
            continue
        cm = re.search(r"timthumb\.php\?src=([^&\s\"']+)", block)
        cover = cm.group(1) if cm else None
        items.append({"title": title[:120], "url": hm.group(1), "source": "177picyy", "cover": cover})
    return items


def _p177_pages(url, limit=None):
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("177picyy 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.S)
    title = _strip(tm.group(1)) if tm else ""
    imgs = re.findall(r'data-lazy-src="(http://img\.177picyy\.com/uploads/[^"]+)"', r.text)
    if not imgs:
        imgs = re.findall(r'src="(http://img\.177picyy\.com/uploads/[^"]+)"', r.text)
    imgs = list(dict.fromkeys(imgs))
    if not imgs:
        raise ValueError("177picyy 未提取到图片地址")
    if limit and limit > 0:
        imgs = imgs[:limit]
    return {"title": title or url.split("/")[-1], "images": imgs}


# ============================== ho5ho ==============================
def _ho5_search_page(p, base, keyword):
    url = base if p == 1 else base + "page/%d/" % p
    r = _get(url, params={"s": keyword})
    if r.status_code != 200:
        return []
    items = []
    for card in re.finditer(r'<article class="ho5ho-v2-card">(.*?)</article>', r.text, re.S):
        block = card.group(1)
        hm = re.search(r'class="ho5ho-v2-card-cover[^"]*"[^>]*href="([^"]+)"', block)
        if not hm:
            continue
        tm = re.search(r'class="ho5ho-v2-card-title[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', block, re.S)
        title = _strip(tm.group(1)) if tm else ""
        if len(title) < 2:
            continue
        im = re.search(r"<img[^>]+src=\"([^\"]+)\"", block)
        items.append({"title": title[:120], "url": _abs(hm.group(1), base), "source": "ho5ho", "cover": _abs(im.group(1), base) if im else None})
    return items


def _ho5_pages(url, limit=None):
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("ho5ho 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
    if not tm:
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.S)
    title = _strip(tm.group(1)) if tm else ""
    chaps = []
    for m in re.finditer(r'<li class="wp-manga-chapter[^"]*">\s*<a[^>]+href="([^"]+)"', r.text):
        h = _abs(m.group(1), url)
        if h not in chaps:
            chaps.append(h)
    if not chaps:
        raise ValueError("ho5ho 未找到章节")

    def fetch(ch):
        for _try in range(3):
            try:
                p = _get(ch)
            except Exception:
                continue
            if p.status_code != 200:
                continue
            m = re.search(r'id="ho5ho-reader-image-manifest"[^>]*>(.*?)</script>', p.text, re.S)
            if m:
                try:
                    arr = json.loads(m.group(1).strip())
                except Exception:
                    arr = []
                out = [u for u in arr if isinstance(u, str) and u.startswith("http")]
                if out:
                    return out
        return []

    images = _grab_chapters(chaps, fetch, limit)
    if not images:
        raise ValueError("ho5ho 未提取到图片地址")
    return {"title": title or url.split("/")[-1], "images": images}


# ============================== caitlin ==============================
def _cai_search_page(p, base, keyword):
    r = _get("https://caitlin.top/index.php", params={"route": "comic/list", "search_key": keyword, "page": p})
    if r.status_code != 200:
        return []
    titles = re.findall(r'<h5 class="title"><a[^>]+title="([^"]+)"[^>]+href="index\.php\?route=comic/article&amp;comic_id=(\d+)"', r.text)
    covers = re.findall(r'data-src="(//c2\.imkhan[\w.-]*\.top/image/cover/h300/[^"]+\.avif)"', r.text)
    items = []
    for i, (title, cid) in enumerate(titles):
        cover = ("https:" + covers[i]) if i < len(covers) else None
        items.append({"title": title[:120], "url": "https://caitlin.top/index.php?route=comic/article&comic_id=%s" % cid, "source": "caitlin", "cover": cover})
    return items


def _cai_pages(url, limit=None):
    m = re.search(r"comic_id=(\d+)", url)
    if not m:
        raise ValueError("caitlin 链接无效")
    cid = m.group(1)
    r = _get("https://caitlin.top/index.php?route=comic/readOnline&comic_id=%s&host_id=0" % cid)
    if r.status_code != 200:
        raise ValueError("caitlin 访问失败(HTTP %d)" % r.status_code)
    txt = r.text
    fm = re.search(r'var\s+IMAGE_FOLDER\s*=\s*"([^"]+)"', txt)
    sm = re.search(r'var\s+image_server_id\s*=\s*(\d+)', txt)
    lm = re.search(r"Image_List\s*=\s*(\[[^\]]*\]);", txt)
    svm = re.search(r"IMAGE_SERVER\s*=\s*(\{.*?\});", txt, re.S)
    if not (fm and sm and lm and svm):
        raise ValueError("caitlin 阅读器数据结构未识别")
    try:
        arr = json.loads(lm.group(1))
        servers = json.loads(svm.group(1))
    except Exception as e:
        raise ValueError("caitlin 阅读器数据解析失败: %s" % e)
    hosts = servers.get(str(sm.group(1))) or servers.get(sm.group(1))
    if not hosts:
        raise ValueError("caitlin 图片服务器未识别")
    folder = fm.group(1)
    images = []
    for i, item in enumerate(arr):
        sort = str(item.get("sort", i + 1))
        ext = str(item.get("extension", "jpg"))
        host = hosts[i % len(hosts)]
        u = host + folder + sort + "." + ext
        if not u.startswith("http"):
            u = "https:" + u
        images.append(u)
    images = list(dict.fromkeys(images))
    if not images:
        raise ValueError("caitlin 未提取到图片地址")
    if limit and limit > 0:
        images = images[:limit]
    tm = re.search(r"<h1[^>]*>(.*?)</h1>", txt, re.S)
    title = _strip(tm.group(1)) if tm else ""
    return {"title": title or cid, "images": images}


# ============================== rokuhentai ==============================
def _rok_cards_from_html(txt, base):
    codes = re.findall(r'id="site-manga-card-([a-z0-9]+)"', txt)
    titles = re.findall(r"site-manga-card__title--primary[^>]*>([^<]+)<", txt)
    items = []
    for i, code in enumerate(codes):
        title = _strip(titles[i]) if i < len(titles) else ""
        if len(title) < 2:
            continue
        items.append(
            {
                "title": title[:120],
                "url": "https://rokuhentai.com/%s/0" % code,
                "source": "rokuhentai",
                "cover": "https://rokuhentai.com/_images/cover-thumbnails/%s.jpg" % code,
            }
        )
    return items


def _rok_search_page(p, base, keyword):
    if p == 1:
        r = _get(base, params={"q": keyword})
        if r.status_code != 200:
            return []
        return _rok_cards_from_html(r.text, base)
    r = _get(base + "_search", params={"p": p, "q": keyword})
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    items = []
    for it in data.get("items") or data.get("results") or []:
        code = str(it.get("code") or it.get("id") or "")
        title = it.get("title") or ""
        if not code or not title:
            continue
        items.append(
            {
                "title": title[:120],
                "url": "https://rokuhentai.com/%s/0" % code,
                "source": "rokuhentai",
                "cover": "https://rokuhentai.com/_images/cover-thumbnails/%s.jpg" % code,
            }
        )
    return items


def _rok_pages(url, limit=None):
    parts = [x for x in url.split("/") if x]
    code = parts[-2] if parts else ""
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("rokuhentai 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
    title = _strip(tm.group(1)) if tm else ""
    nums = re.findall(r"https://rokuhentai\.com/_images/pages/%s/(\d+)\.jpg" % re.escape(code), r.text)
    nums = sorted(set(int(n) for n in nums))
    images = ["https://rokuhentai.com/_images/pages/%s/%d.jpg" % (code, n) for n in nums]
    if not images:
        raise ValueError("rokuhentai 未提取到图片地址")
    if limit and limit > 0:
        images = images[:limit]
    return {"title": title or code, "images": images}


# ============================== h-webtoon ==============================
def _hwt_search_page(p, base, keyword):
    r = _get("https://h-webtoon.com/api/series", params={"q": keyword, "page": p, "limit": 20})
    if r.status_code != 200:
        return []
    try:
        data = r.json()
    except Exception:
        return []
    items = []
    for it in data.get("items") or data.get("series") or []:
        sid = it.get("id")
        title = it.get("title") or ""
        if not sid or not title:
            continue
        items.append({"title": title[:120], "url": "https://h-webtoon.com/series/%s" % sid, "source": "h-webtoon", "cover": it.get("thumbnail")})
    return items


def _hwt_pages(url, limit=None):
    m = re.search(r"/series/(\d+)", url)
    if not m:
        raise ValueError("h-webtoon 链接无效")
    sid = m.group(1)
    d = _get("https://h-webtoon.com/api/series/%s" % sid)
    if d.status_code != 200:
        raise ValueError("h-webtoon 访问失败(HTTP %d)" % d.status_code)
    try:
        data = d.json()
    except Exception as e:
        raise ValueError("h-webtoon 数据解析失败: %s" % e)
    if isinstance(data, dict) and data.get("series"):
        data = data["series"]
    title = data.get("title") or ""
    chaps = []
    for c in data.get("chapters") or data.get("episodes") or []:
        if c.get("slug"):
            chaps.append(c["slug"])
    if not chaps:
        raise ValueError("h-webtoon 未找到章节")

    def fetch(slug):
        try:
            p = _get("https://h-webtoon.com/api/posts/%s" % slug)
            if p.status_code != 200:
                return []
            arr = p.json().get("post") or p.json() or {}
            arr = arr.get("images") or []
            return [u for u in arr if isinstance(u, str) and u.startswith("http")]
        except Exception:
            return []

    images = _grab_chapters(chaps, fetch, limit)
    if not images:
        raise ValueError("h-webtoon 未提取到图片地址")
    return {"title": title or sid, "images": images}


# ============================== cartoon18 ==============================
def _c18_search_page(p, base, keyword):
    url = base + ("page/%d/" % p if p > 1 else "")
    r = _get(url, params={"q": keyword})
    if r.status_code != 200:
        return []
    items = []
    for m in re.finditer(r'<a class="visited" href="(/v/[A-Za-z0-9]+)">\s*<img[^>]+alt="([^"]*)"[^>]*(?:data-src|src)="([^"]+)"', r.text):
        items.append({"title": m.group(2)[:120], "url": base.rstrip("/") + m.group(1), "source": "cartoon18", "cover": m.group(3)})
    return items


def _c18_pages(url, limit=None):
    m = re.search(r"/v/([A-Za-z0-9]+)", url)
    if not m:
        raise ValueError("cartoon18 链接无效")
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("cartoon18 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
    title = _strip(tm.group(1)) if tm else ""
    chaps = []
    for m in re.finditer(r'href="(/story/\d+/full)"', r.text):
        h = "https://www.cartoon18.com" + m.group(1)
        if h not in chaps:
            chaps.append(h)
    if not chaps:
        raise ValueError("cartoon18 未找到章节")

    def fetch(ch):
        try:
            p = _get(ch)
        except Exception:
            return []
        if p.status_code != 200:
            return []
        return re.findall(r'<img[^>]+src="(https://img\.cartoon18\.com/images/image/\d+/\d+\.avif[^"]*)"', p.text)

    images = _grab_chapters(chaps, fetch, limit)
    if not images:
        raise ValueError("cartoon18 未提取到图片地址")
    return {"title": title or url.split("/")[-1], "images": images}


# ============================== xhentai888 ==============================
def _x88_search_page(p, base, keyword):
    r = _get("https://xhentai888.xyz/?latest")
    if r.status_code != 200:
        return []
    txt = _decode_text(r)
    items = []
    seen = set()
    for m in re.finditer(r'<a href="\?novel(\d+)/" title="([^"]+)"', txt):
        url = "https://xhentai888.xyz/?novel%s/" % m.group(1)
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": m.group(2)[:120], "url": url, "source": "xhentai888", "cover": None})
    covers = re.findall(r'<img[^>]+src="(https://img1\.du8\.in/titlepic/[^"]+)"', txt)
    for i, it in enumerate(items):
        if i < len(covers):
            it["cover"] = covers[i]
    return items


def _x88_pages(url, limit=None):
    m = re.search(r"novel(\d+)", url)
    if not m:
        raise ValueError("xhentai888 链接无效")
    nid = m.group(1)
    chaps = []
    p = 0
    while True:
        u = "https://xhentai888.xyz/?novel%s/" % nid
        if p:
            u += "?p=%d" % p
        r = _get(u)
        if r.status_code != 200:
            break
        txt = _decode_text(r)
        found = sorted(set(int(x) for x in re.findall(r"chapter(\d+)\.html", txt)))
        new = [x for x in found if x not in chaps]
        chaps = sorted(set(chaps + new))
        if not new or p > 30:
            break
        p += 1
    if not chaps:
        raise ValueError("xhentai888 未找到章节")

    def fetch(cn):
        try:
            r = _get("https://xhentai888.xyz/?novel%s/chapter%d.html" % (nid, cn))
        except Exception:
            return []
        if r.status_code != 200:
            return []
        return re.findall(r"https://img1\.du8\.in/hmpic/[^\"'\s>]+", _decode_text(r))

    images = _grab_chapters(chaps, fetch, limit)
    if not images:
        raise ValueError("xhentai888 未提取到图片地址")
    try:
        r = _get("https://xhentai888.xyz/?novel%s/" % nid)
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", _decode_text(r), re.S)
        title = _strip(tm.group(1)) if tm else ""
    except Exception:
        title = ""
    return {"title": title or nid, "images": images}


# ============================== sexacg ==============================
def _sex_search_page(p, base, keyword):
    r = _get(base + "vodsearch/-------------/", params={"wd": keyword, "page": p})
    if r.status_code != 200:
        return []
    items = []
    for m in re.finditer(r'<a class="hl-item-thumb hl-lazy" href="(/voddetail-(\d+)/)" title="([^"]*)" data-original="([^"]+)"', r.text):
        cover = m.group(4) or ""
        if cover.startswith("//"):
            cover = "https:" + cover
        items.append({"title": m.group(3)[:120], "url": base.rstrip("/") + m.group(1), "source": "sexacg", "cover": cover})
    return items


def _sex_pages(url, limit=None):
    m = re.search(r"voddetail-(\d+)", url)
    if not m:
        raise ValueError("sexacg 链接无效")
    vid = m.group(1)
    d = _get("https://www.sexacg.xyz/voddetail-%s/" % vid)
    if d.status_code != 200:
        raise ValueError("sexacg 访问失败(HTTP %d)" % d.status_code)
    tm = re.search(r"<h2[^>]*>(.*?)</h2>", d.text, re.S)
    if not tm:
        tm = re.search(r'<meta property="og:title" content="([^"]+)"', d.text)
    title = _strip(tm.group(1)) if tm else ""
    eps = sorted(set(re.findall(r"/vodplay-%s-1-(\d+)/" % vid, d.text)), key=int)
    if not eps:
        eps = ["1"]

    def fetch(ep):
        try:
            p = _get("https://www.sexacg.xyz/vodplay-%s-1-%s/" % (vid, ep))
        except Exception:
            return []
        if p.status_code != 200:
            return []
        jm = re.search(r"imglist_string\s*=\s*'([^']*)'", p.text, re.S)
        if not jm:
            return []
        # 兼容多种格式：纯数组、或带 "第1集$" 前缀与 "#" 结尾、或分集拼接
        arrs = []
        s = jm.group(1)
        dec = json.JSONDecoder()
        l = s.find("[")
        while l != -1:
            try:
                obj, end = dec.raw_decode(s[l:])
            except Exception:
                break
            if isinstance(obj, list):
                arrs.extend(obj)
            s = s[l + end :]
            l = s.find("[")
        out = []
        for it in arrs:
            u = it.get("url") or ""
            if u.startswith("//"):
                u = "https:" + u
            if not u.startswith("http"):
                continue
            if "/themes/" in u:
                continue
            if it.get("caption"):
                continue
            out.append(u)
        return out

    images = _grab_chapters(eps, fetch, limit)
    if not images:
        raise ValueError("sexacg 未提取到图片地址")
    return {"title": title or vid, "images": images}


# ============================== hentaiclap ==============================
_GTH_EXT = {"j": "jpg", "w": "webp", "p": "png", "g": "gif"}


def _hcp_search_page(p, base, keyword):
    url = "https://hentaiclap.com/search/?q=%s" % keyword
    if p > 1:
        url += "&page=%d" % p
    r = _get(url)
    if r.status_code != 200:
        return []
    items = []
    seen = set()
    for m in re.finditer(r'<a href="/gallery/(\d+)/">\s*<h2>(.*?)</h2>', r.text, re.S):
        gid = m.group(1)
        if gid in seen:
            continue
        seen.add(gid)
        title = _strip(m.group(2))
        if len(title) < 2:
            continue
        items.append({"title": title[:120], "url": "https://hentaiclap.com/gallery/%s/" % gid, "source": "hentaiclap", "cover": None})
    covers = re.findall(r'<a href="/gallery/(\d+)/">.*?data-src="(https://[^"]+/thumb\.jpg)"', r.text, re.S)
    cmap = {g: c for g, c in covers}
    for it in items:
        gid = it["url"].rstrip("/").rsplit("/", 1)[-1]
        it["cover"] = cmap.get(gid)
    return items


def _hcp_pages(url, limit=None):
    m = re.search(r"/gallery/(\d+)/", url)
    if not m:
        raise ValueError("hentaiclap 链接无效")
    gid = m.group(1)
    read = _get("https://hentaiclap.com/read/%s/1/" % gid)
    if read.status_code != 200:
        raise ValueError("hentaiclap 访问失败(HTTP %d)" % read.status_code)
    im = re.search(r'data-src="(https://[^"]+/1\.(?:jpg|webp))"', read.text)
    if not im:
        raise ValueError("hentaiclap 未找到图片地址")
    base = im.group(1)[: im.group(1).rfind("/")]
    gth = re.search(r"var g_th\s*=\s*(\{[^;]+?\});", read.text, re.S)
    if not gth:
        raise ValueError("hentaiclap 未找到图片清单")
    try:
        th = json.loads(gth.group(1))
    except Exception as e:
        raise ValueError("hentaiclap 图片清单解析失败: %s" % e)
    nums = sorted(int(k) for k in th.keys())
    if not nums:
        raise ValueError("hentaiclap 未提取到图片地址")
    images = []
    for n in nums:
        ext = _GTH_EXT.get(str(th.get(str(n), "j"))[0], "jpg")
        images.append("%s/%d.%s" % (base, n, ext))
    if limit and limit > 0:
        images = images[:limit]
    title = ""
    tm = re.search(r"<h1[^>]*>(.*?)</h1>", read.text, re.S)
    if not tm:
        r = _get(url)
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.S)
    title = _strip(tm.group(1)) if tm else ""
    return {"title": title or gid, "images": images}


# ============================== hentairun (Next.js RSC) ==============================
def _next_flight(url):
    r = _get(url)
    if r.status_code != 200:
        return ""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:\\.|[^"])*)"\]\)', r.text)
    out = ""
    for c in chunks:
        try:
            out += json.loads('"' + c + '"')
        except Exception:
            out += c
    return out


def _hrun_search_page(p, base, keyword):
    out = _next_flight("https://hentairun.com/search?q=%s&page=%d" % (keyword, p))
    i = out.find('{"query"')
    if i < 0:
        return []
    try:
        obj, _ = json.JSONDecoder().raw_decode(out[i:])
    except Exception:
        return []
    docs = obj.get("initialDocs") or []
    items = []
    for d in docs:
        gid = (d.get("gallery_id") or [None])[0]
        title = (d.get("title") or [""])[0]
        if not gid or not title:
            continue
        items.append(
            {
                "title": title[:120],
                "url": "https://hentairun.com/gallery/%s/" % gid,
                "source": "hentairun",
                "cover": None,
            }
        )
    return items


def _hrun_pages(url, limit=None):
    m = re.search(r"/gallery/(\d+)/", url)
    if not m:
        raise ValueError("hentairun 链接无效")
    out = _next_flight(url)
    jm = re.search(
        r'\{"id":"(\d+)","server":(\d+),"img_dir":"([^"]+)","gallery_id":"([^"]+)","pages":(\d+),"title":"((?:\\.|[^"])*)"',
        out,
    )
    if not jm:
        raise ValueError("hentairun 图片信息未识别")
    server, img_dir, gal, pages = jm.group(2), jm.group(3), jm.group(4), int(jm.group(5))
    images = ["https://m%s.hentairun.com/%s/%s/%d.webp" % (server, img_dir, gal, n) for n in range(1, pages + 1)]
    if limit and limit > 0:
        images = images[:limit]
    title = jm.group(6)
    try:
        title = json.loads('"%s"' % title)
    except Exception:
        pass
    return {"title": title or gal, "images": images}


# ============================== allporncomic (Madara wp-manga) ==============================
_APC_IMG_RE = re.compile(
    r'data-src="\s*(https://cdn\.allporncomic\.com/wp-content/uploads/WP-manga/data/[^"]+\.(?:jpg|png|webp))"'
)


def _apc_search_page(p, base, keyword):
    if p <= 1:
        url = "%s?s=%s&post_type=wp-manga" % (base.rstrip("/"), keyword)
    else:
        url = "%s/page/%d/?s=%s&post_type=wp-manga" % (base.rstrip("/"), p, keyword)
    r = _get(url)
    if r.status_code != 200:
        return []
    items = []
    seen = set()
    for m in re.finditer(r'<h[123][^>]*>\s*<a[^>]+href="(https://allporncomic\.com/porncomic/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        u, title = m.group(1).strip(), _clean(m.group(2))
        if not u or not title or u in seen:
            continue
        seen.add(u)
        cover = None
        cm = re.search(r'src="(https://cdn\.allporncomic\.com/wp-content/uploads/[^"]+\.(?:jpg|png|webp))"', m.group(0))
        if cm and "cropped" not in cm.group(1) and "manifest" not in cm.group(1):
            cover = cm.group(1)
        items.append({"title": title[:120], "url": u, "source": "allporncomic", "cover": cover})
    return items


def _apc_fetch_chapter(chap):
    try:
        r = _get(chap)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    return [x.strip() for x in _APC_IMG_RE.findall(r.text)]


def _apc_pages(url, limit=None):
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("allporncomic 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.S) or re.search(r"<title>(.*?)</title>", r.text, re.S)
    title = _clean(tm.group(1)) if tm else ""
    if "| AllPornComic" in title:
        title = title.split("| AllPornComic")[0].strip()
    chaps = re.findall(r'class="wp-manga-chapter[^"]*"[^>]*>\s*<a[^>]+href="(https://[^"]+)"', r.text)
    chaps = list(dict.fromkeys(chaps))
    if not chaps:
        raise ValueError("allporncomic 未找到章节链接")
    images = _grab_chapters(chaps, _apc_fetch_chapter, limit)
    if not images:
        raise ValueError("allporncomic 未提取到图片地址")
    if limit and limit > 0:
        images = images[:limit]
    return {"title": title, "images": images}


# ============================== 8muses ==============================
def _8mus_search_page(p, base, keyword):
    if p > 1:
        return []
    variants = [keyword]
    if " " in keyword:
        variants.append(keyword.replace(" ", ""))
    elif not re.search(r"[_]", keyword):
        variants.append(keyword)
    albums = {}
    for kw in variants:
        r = _get("https://8muses.io/search?q=%s" % kw)
        if r.status_code != 200:
            continue
        for m in re.finditer(r'<a class="c-tile[^"]*" href="(/picture/.+?)" title="([^"]*)"[^>]*>(.*?)</a>', r.text, re.S):
            path, ttl, inner = m.group(1), m.group(2), m.group(3)
            pm = re.match(r"(.+?)/(\d+)$", path)
            if not pm:
                continue
            album = pm.group(1).replace("/picture/", "/album/", 1)
            if album not in albums:
                cm = re.search(r'data-src="([^"]+)"', inner)
                albums[album] = {"title": ttl, "cover": cm.group(1) if cm else None}
    items = []
    for album, info in albums.items():
        name = album.rstrip("/").rsplit("/", 1)[-1]
        name = re.sub(r"[_-]+", " ", name).strip()
        items.append(
            {
                "title": (name or info["title"])[:120],
                "url": "https://8muses.io" + album,
                "source": "8muses",
                "cover": "https://8muses.io" + info["cover"] if info["cover"] else None,
            }
        )
    return items


def _8mus_fetch_pic(pic):
    try:
        r = _get("https://8muses.io" + pic)
    except Exception:
        return None
    m = re.search(r'src="(/img/data/full_[^"]+\.(?:jpg|jpeg|png|webp))"', r.text)
    return m.group(1) if m else None


def _8mus_pages(url, limit=None):
    m = re.search(r"https?://8muses\.io(/album/.+)", url)
    if not m:
        raise ValueError("8muses 链接无效")
    album_path = m.group(1).rstrip("/")
    pics = []
    seen = set()
    page = 1
    while page <= 30:
        u = "https://8muses.io" + album_path + (("?page=%d" % page) if page > 1 else "")
        try:
            r = _get(u)
        except Exception:
            break
        if r.status_code != 200:
            break
        cur = []
        for pp in re.findall(r'href="(/picture/[^"]+)"', r.text):
            if pp not in seen:
                seen.add(pp)
                cur.append(pp)
        if not cur:
            break
        pics.extend(cur)
        if ("?page=%d" % (page + 1)) not in r.text:
            break
        page += 1
    if not pics:
        raise ValueError("8muses 未找到图片页面")
    imgs = []
    for i in range(0, len(pics), 8):
        if limit and len(imgs) >= limit:
            break
        batch = pics[i : i + 8]
        try:
            with ThreadPoolExecutor(max_workers=8) as ex:
                results = list(ex.map(_8mus_fetch_pic, batch))
        except Exception:
            results = []
        for x in results:
            if x:
                imgs.append("https://8muses.io" + x)
                if limit and len(imgs) >= limit:
                    break
    if not imgs:
        raise ValueError("8muses 未提取到图片地址")
    if limit and limit > 0:
        imgs = imgs[:limit]
    title = re.sub(r"[_-]+", " ", album_path.rsplit("/", 1)[-1]).strip()
    return {"title": title, "images": imgs}


# ============================== ilikecomix ==============================
def _ilc_search_page(p, base, keyword):
    url = "https://ilikecomix.com/?s=%s" % keyword
    if p > 1:
        url += "&paged=%d" % p
    r = _get(url)
    if r.status_code != 200:
        return []
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="(https://ilikecomix\.com/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        u, inner = m.group(1), m.group(2)
        if "/c-book/" in u or "/comics-tag/" in u or "/category/" in u:
            continue
        if not re.search(r"https://ilikecomix\.com/[a-z0-9-]+/[^/]+/$", u):
            continue
        title = _clean(inner)
        if len(title) < 3 or u in seen:
            continue
        seen.add(u)
        cover = None
        cm = re.search(r'data-src="(https://img\.ilikecomix\.com/[^"]+\.(?:jpg|png|webp))"', m.group(0))
        if not cm:
            cm = re.search(r'src="(https://img\.ilikecomix\.com/[^"]+\.(?:jpg|png|webp))"', m.group(0))
        if cm:
            cover = cm.group(1)
        items.append({"title": title[:120], "url": u, "source": "ilikecomix", "cover": cover})
    return items


def _ilc_pages(url, limit=None):
    r = _get(url)
    if r.status_code != 200:
        raise ValueError("ilikecomix 访问失败(HTTP %d)" % r.status_code)
    tm = re.search(r"<title>(.*?)</title>", r.text, re.S) or re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.S)
    title = _clean(tm.group(1)) if tm else ""
    if " | ILikeComix" in title:
        title = title.split(" | ILikeComix")[0].strip()
    title = re.split(r"\s*-\s*Porn\s*\w*\s*Comics?.*", title)[0].strip()
    imgs = re.findall(r'data-pswp-src="(https://[^"]+\.(?:jpg|png|webp|gif))"', r.text)
    if not imgs:
        imgs = re.findall(r'<img[^>]+src="(https://img\.ilikecomix\.com/comic/[^"]+\.(?:jpg|png|webp|gif))"', r.text)
    imgs = list(dict.fromkeys(imgs))
    if not imgs:
        raise ValueError("ilikecomix 未提取到图片地址")
    if limit and limit > 0:
        imgs = imgs[:limit]
    return {"title": title, "images": imgs}


# ============================== 分发 ==============================
_FN_PREFIX = {
    "wnacg": "_wnacg_",
    "177picyy": "_p177_",
    "ho5ho": "_ho5_",
    "caitlin": "_cai_",
    "rokuhentai": "_rok_",
    "h-webtoon": "_hwt_",
    "cartoon18": "_c18_",
    "xhentai888": "_x88_",
    "sexacg": "_sex_",
    "hentaiclap": "_hcp_",
    "hentairun": "_hrun_",
    "allporncomic": "_apc_",
    "8muses": "_8mus_",
    "ilikecomix": "_ilc_",
}
for _name, _conf in COMICS.items():
    _pfix = _FN_PREFIX[_name]
    _conf["search_page"] = globals()[_pfix + "search_page"]
    _conf["pages"] = globals()[_pfix + "pages"]


def search_comic(keyword, source="wnacg", page=1, per_page=20, count=None):
    """搜索漫画；count 指定需要的候选总数，自动跨页聚合"""
    if source not in COMICS:
        raise ValueError("不支持的漫画源: " + source)
    conf = COMICS[source]
    kw = keyword
    fn = SEARCH_LANG.get(conf.get("lang", "general"))
    if fn:
        kw = fn(keyword) or keyword

    def fetch(p):
        return conf["search_page"](p, conf["url"], kw)

    items, has_more = _paginate(fetch, page, per_page, count)
    if not items:
        raise ValueError("%s 没有搜索到结果" % conf["label"])
    tr = {}
    try:
        tr = translate_many([it["title"] for it in items], force=bool(conf.get("force_zh")))
    except Exception:
        tr = {}
    for it in items:
        zh = tr.get(it["title"], it["title"])
        it["title_zh"] = zh
        it["is_cn"] = _is_cn_tag(it["title"]) or _is_cn_tag(zh)
    items.sort(key=lambda it: (not it["is_cn"], it["title"]))
    return items, has_more


def comic_pages(url, limit=None):
    """图集/漫画链接 -> {title, images}；limit 限制返回张数（用于预览）"""
    host = re.sub(r"^www\.", "", (urlparse(url).hostname or "")).lower()
    for name, conf in COMICS.items():
        for d in conf.get("hosts", []):
            if host == d or host.endswith("." + d):
                res = conf["pages"](url, limit)
                if limit and limit > 0 and len(res["images"]) > limit:
                    res["images"] = res["images"][:limit]
                return res
    raise ValueError("不支持的漫画链接: " + url)
