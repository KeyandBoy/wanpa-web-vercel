import base64
import gzip
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maccms_svc import search_novel as _h62_search, get_novel_content as _h62_content

import requests
from curl_cffi import requests as cr

from trans_svc import to_en, to_zh

# ---------- 辅助 ----------
def _t2s(text):
    """繁体中文 -> 简体中文（懒加载 opencc）"""
    if not text:
        return text
    try:
        from opencc import OpenCC
        return OpenCC("t2s").convert(text)
    except Exception:
        return text


def _proxy():
    try:
        from env_utils import proxy as _p

        return _p()
    except Exception:
        return None


def _session():
    s = cr.Session(impersonate="chrome")
    s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"})
    proxies = {"http": _proxy(), "https": _proxy()} if _proxy() else None
    s.proxies = proxies
    return s


def _get(url, params=None, session=None, retries=2):
    last_err = None
    for attempt in range(retries):
        try:
            if session:
                r = session.get(url, params=params, timeout=25)
            else:
                proxies = None
                p = _proxy()
                if p:
                    proxies = {"http": p, "https": p}
                r = cr.get(url, params=params, timeout=25, proxies=proxies, impersonate="chrome")
            if r.status_code != 200:
                raise ValueError(f"{url} 访问失败(HTTP {r.status_code})")
            return r
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                import time
                time.sleep(1)
    raise last_err


def _post(url, data=None, session=None, retries=2):
    last_err = None
    for attempt in range(retries):
        try:
            if session:
                r = session.post(url, data=data, timeout=25)
            else:
                proxies = None
                p = _proxy()
                if p:
                    proxies = {"http": p, "https": p}
                r = cr.post(url, data=data, timeout=25, proxies=proxies, impersonate="chrome")
            if r.status_code != 200:
                raise ValueError(f"{url} 访问失败(HTTP {r.status_code})")
            return r
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                import time
                time.sleep(1)
    raise last_err


def _extract_text(html):
    for pat in (
        r'<div[^>]*class="[^"]*(?:entry-content|post-content|single-content|article-content|thecontent)[^"]*"[^>]*>(.*?)</div>',
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*(?:content|post)[^"]*"[^>]*>(.*?)</div>',
    ):
        m = re.search(pat, html, re.S)
        if m:
            txt = m.group(1)
            txt = re.sub(r"<(?:p|div|br|h[1-6]|li)[^>]*>", "\n", txt, flags=re.I)
            txt = re.sub(r"</(?:p|div|h[1-6]|li)>", "\n", txt, flags=re.I)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
            if len(txt) > 100:
                return txt
    ps = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.S):
        t = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
        if len(t) > 30:
            ps.append(t)
    return "\n".join(ps) if ps else None


def _clean_text(text):
    """清理垃圾话/转载声明/广告/HTML实体"""
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&[a-z]+;", "", text)
    text = re.sub(r"&#\d+;", "", text)
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            lines.append("")
            continue
        if re.match(
            r"^(?:轉載|轉貼|轉自|轉載自|轉貼自|版權|版权所有|copyright|all rights|adsby|本文轉載|www\.|https?://)",
            line,
            re.I,
        ):
            continue
        line = re.sub(r"【[^】]*轉[^】]*】", "", line)
        line = re.sub(r"\(adsbyjuicy.*", "", line)
        lines.append(line.strip())
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def translate_to_zh(text):
    """英文内容分段翻译为简体中文"""
    paras = [p for p in text.split("\n") if p.strip()]
    chunks = []
    cur = ""
    for p in paras:
        if len(cur) + len(p) > 2800:
            if cur:
                chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    if not chunks:
        return ""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(to_zh, chunks))
    return "\n\n".join(results)


# ---------- 各源 ----------

SITES = {
    "aaanovel": {"url": "https://aaanovel.com/", "label": "AAA成人小说", "zh": True},
    "1000novel": {"url": "https://1000novel.com/", "label": "1000成人小说", "zh": True},
    "xbookcn": {"url": "https://xbookcn.net/", "label": "中文成人文学", "zh": True},
    "hhhbook": {"url": "https://hhhbook.com/", "label": "3H淫书", "zh": True},
    "canovel": {"url": "https://canovel.com/", "label": "CA情色小说", "zh": True},
    "h528": {"url": "http://www.h528.com/", "label": "风月文学网", "zh": True},
    "69story": {"url": "https://69story.com/", "label": "69成人小说", "zh": True},
    "biquga": {"url": "https://www.biquga.com/", "label": "笔趣阁", "zh": True},
    "txt800": {"url": "https://www.txt800.cc/", "label": "800小说网", "zh": True},
    "bqgnovels": {"url": "https://bqgnovels.com/", "label": "新笔趣阁", "zh": True},
    "ttkan": {"url": "https://cn.ttkan.co/", "label": "天天看小说", "zh": True},
    "bdsmcafe": {"url": "https://bdsmcafe.com/", "label": "BDSMCafe", "zh": False},
    "chyoa": {"url": "https://chyoa.com/", "label": "CHYOA", "zh": False},
    "alicesw": {"url": "https://alicesw.com/", "label": "爱丽丝书屋", "zh": True},
    "hhe62": {"url": "https://zfxdrshm.top:2549/", "label": "hhe62小说", "zh": True},
}

# 通用中文书站（非成人/非海外），与 biquga 同列为免费 Lite 源
_LITE_NOVEL_IDS = {"biquga", "txt800", "bqgnovels", "ttkan"}
# Plus 专属小说源（除通用书站外全部为成人/海外，需激活）
_PLUS_NOVEL_IDS = {k for k in SITES if k not in _LITE_NOVEL_IDS}
_PLUS_NOVEL_HOSTS = tuple(
    v["url"].split("//")[1].split("/")[0].split(":")[0].lower()
    for k, v in SITES.items()
    if k in _PLUS_NOVEL_IDS
)


def is_plus_novel_url(url):
    """按 URL 判定小说正文/章节是否属于 Plus 专属源"""
    if not url:
        return False
    u = url.lower()
    return any(host in u for host in _PLUS_NOVEL_HOSTS)


# ---- 天天看小说 (ttkan)：JSON API，支持按内容分类浏览 ----
TTKAN_BASE = "https://cn.ttkan.co"
TTKAN_API = "https://cn.ttkan.co/api"
TTKAN_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/131.0.0.0 Safari/537.36"
)
TTKAN_COVER = "https://static.ttkan.co/cover/"

# 天天看小说分类 type 参数 -> 中文名
TTKAN_CATEGORIES = [
    {"type": "", "name": "最新"},
    {"type": "xuanhuan", "name": "玄幻"},
    {"type": "dushi", "name": "都市"},
    {"type": "xianxia", "name": "仙侠"},
    {"type": "gudaiyanqing", "name": "言情"},
    {"type": "chuanyuechongsheng", "name": "穿越"},
    {"type": "youxi", "name": "游戏"},
    {"type": "kehuan", "name": "科幻"},
    {"type": "xuanyi", "name": "悬疑"},
    {"type": "lingyi", "name": "灵异"},
    {"type": "lishi", "name": "历史"},
    {"type": "qingchun", "name": "青春"},
    {"type": "junshi", "name": "军事"},
    {"type": "jingji", "name": "竞技"},
    {"type": "yanqing", "name": "现言"},
    {"type": "qita", "name": "其它"},
]


def ttkan_categories():
    """返回 ttkan 内容分类列表（供前端分类下拉）"""
    return [{"type": c["type"], "name": c["name"]} for c in TTKAN_CATEGORIES]


def _ttkan_extract_novel_id(url):
    """从 ttkan URL 提取 novel_id（支持详情页与正文页两种形态）"""
    if not url:
        return ""
    m = re.search(r"novel_id=([^&]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/novel/chapters/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    return ""


def _ttkan_get(url, params=None):
    proxies = None
    p = _proxy()
    if p:
        proxies = {"http": p, "https": p}
    return cr.get(
        url,
        params=params,
        headers={"User-Agent": TTKAN_UA, "Referer": TTKAN_BASE + "/"},
        timeout=20,
        proxies=proxies,
    )


def _search_ttkan(keyword, page=1, per_page=20):
    """天天看小说关键词搜索 -> 书籍列表"""
    items = []
    r = _ttkan_get(TTKAN_BASE + "/novel/search", {"q": keyword})
    if r.status_code != 200:
        raise ValueError(f"天天看小说搜索失败(HTTP {r.status_code})")
    for m in re.finditer(
        r'<a[^>]+href="(/novel/chapters/[^"]+)"[^>]*>\s*<img[^>]+src="([^"]+)"[^>]*alt="([^"]*)"',
        r.text,
    ):
        href, img, alt = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"\s+", " ", alt).strip() or keyword
        items.append(
            {
                "title": _t2s(title)[:120],
                "url": TTKAN_BASE + href,
                "cover": (
                    img.split("?")[0]
                    if img.startswith("http")
                    else TTKAN_COVER + img.split("?")[0]
                ),
                "source": "ttkan",
                "novel_id": href.replace("/novel/chapters/", ""),
            }
        )
        if len(items) >= per_page:
            break
    if not items:
        for m in re.finditer(
            r'<a[^>]+href="(/novel/chapters/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S
        ):
            href, inner = m.group(1), m.group(2)
            title = re.sub(r"<[^>]+>", "", inner).strip()
            if len(title) < 2:
                continue
            items.append(
                {
                    "title": _t2s(title)[:120],
                    "url": TTKAN_BASE + href,
                    "cover": None,
                    "source": "ttkan",
                    "novel_id": href.replace("/novel/chapters/", ""),
                }
            )
            if len(items) >= per_page:
                break
    if not items:
        raise ValueError("天天看小说没有搜索到结果")
    return items


def _ttkan_category(type_, page=1, per_page=20):
    """天天看小说按内容分类浏览 -> 书籍列表（JSON API）"""
    items = []
    r = _ttkan_get(
        TTKAN_API + "/nq/amp_novel_list",
        {
            "type": type_ or "",
            "filter": "*",
            "page": str(page),
            "limit": str(min(per_page, 40)),
            "language": "cn",
            "__amp_source_origin": TTKAN_BASE,
        },
    )
    if r.status_code != 200:
        raise ValueError(f"天天看小说分类获取失败(HTTP {r.status_code})")
    try:
        j = r.json()
    except Exception:
        raise ValueError("天天看小说分类响应不是合法 JSON")
    for d in j.get("items") or []:
        if not isinstance(d, dict):
            continue
        name = str(d.get("name") or "").strip()
        author = str(d.get("author") or "").strip()
        novel_id = str(d.get("novel_id") or "").strip()
        if not name or not novel_id:
            continue
        items.append(
            {
                "title": _t2s(name)[:120],
                "url": TTKAN_BASE + "/novel/chapters/" + novel_id,
                "cover": (
                    TTKAN_COVER + str(d.get("topic_img") or "").split("?")[0]
                    if d.get("topic_img")
                    else None
                ),
                "author": _t2s(author),
                "source": "ttkan",
                "novel_id": novel_id,
                "description": (str(d.get("description") or "").strip())[:200],
            }
        )
    return items


def _ttkan_chapters(novel_id):
    """天天看小说章节列表 -> [{title, url}]"""
    r = _ttkan_get(
        TTKAN_API + "/nq/amp_novel_chapters",
        {"novel_id": novel_id, "language": "cn", "__amp_source_origin": TTKAN_BASE},
    )
    if r.status_code != 200:
        raise ValueError(f"天天看小说目录获取失败(HTTP {r.status_code})")
    try:
        j = r.json()
    except Exception:
        raise ValueError("天天看小说目录响应不是合法 JSON")
    chapters = []
    for c in j.get("items") or []:
        if not isinstance(c, dict):
            continue
        name = str(c.get("chapter_name") or "").strip()
        cid = c.get("chapter_id")
        if not name or cid is None:
            continue
        chapters.append(
            {
                "title": _t2s(name)[:120],
                "url": f"{TTKAN_BASE}/novel/user/page_direct?novel_id={novel_id}&page={cid}",
                "chapter_id": cid,
            }
        )
    if not chapters:
        raise ValueError("目录页没有章节链接")
    return chapters


def _ttkan_content(url):
    """天天看小说章节正文 -> 文本（page_direct 分页直到无下页）"""
    parts = []
    cur = url
    seen = set()
    while cur:
        if cur in seen:
            break
        seen.add(cur)
        r = _ttkan_get(cur)
        if r.status_code != 200:
            if parts:
                break
            raise ValueError(f"天天看小说正文获取失败(HTTP {r.status_code})")
        m = re.search(r'class="content"[^>]*>(.*?)</(?:div|section)>', r.text, re.S)
        if m:
            txt = re.sub(r"<p[^>]*>", "\n", m.group(1))
            txt = re.sub(r"</p>", "\n", txt)
            txt = re.sub(r"<br\s*/?>", "\n", txt)
            txt = re.sub(r"<[^>]+>", "", txt)
            txt = re.sub(r"&nbsp;", " ", txt)
            txt = re.sub(r"[ \t]+", " ", txt)
            txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
            if txt:
                parts.append(txt)
        nm = re.search(r'id="next_url"[^>]+href="([^"]+)"', r.text)
        if not nm:
            break
        nxt = nm.group(1)
        if "_" not in nxt:
            break
        cur = TTKAN_BASE + nxt if nxt.startswith("/") else nxt
    if not parts:
        raise ValueError("未提取到正文内容")
    return "\n\n".join(parts)


# ---- 800小说网 (txt800)：搜索 -> 书页 -> TXT 直链整本下载 ----
def _fetch_txt800_author(book_url):
    """从800小说网书页提取作者名"""
    try:
        r = _get(book_url)
        m = re.search(
            r'class="mt10 gray"[^>]*>作者[：:]?\s*<a[^>]*>([^<]+)</a>', r.text, re.S
        )
        if m:
            return _t2s(m.group(1).strip())
        m2 = re.search(r"作者[：:]\s*<a[^>]*>([^<]+)</a>", r.text)
        if m2:
            return _t2s(m2.group(1).strip())
    except Exception:
        pass
    return None


def _search_txt800(keyword, page=1, per_page=20):
    try:
        r = _post(
            "https://www.txt800.cc/e/search/index.php",
            {"keyboard": keyword, "show": "title", "tbname": "download", "tempid": "1"},
        )
    except Exception as e:
        raise ValueError(f"800小说网 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="(/[^"]*txt\d+\.html)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if len(title) < 2:
            continue
        url = "https://www.txt800.cc" + href
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": title[:120], "url": url, "source": "txt800"})
    if not items:
        raise ValueError("800小说网 没有搜索到结果")
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=5) as ex:
        authors = list(ex.map(_fetch_txt800_author, [it["url"] for it in items]))
    for it, author in zip(items, authors):
        if author:
            it["author"] = author
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def _txt800_resolve_download_url(book_url):
    try:
        r = _get(book_url)
    except Exception as e:
        raise ValueError(f"800小说网 书页访问失败: {e}") from e
    m = re.search(r'<a[^>]+href="(/down/[^"]+)"', r.text)
    if not m:
        raise ValueError("800小说网 未找到下载页入口")
    down_page = "https://www.txt800.cc" + m.group(1)
    try:
        r2 = _get(down_page)
    except Exception as e:
        raise ValueError(f"800小说网 下载页访问失败: {e}") from e
    for mm in re.finditer(r'(https?://down\.\d+txt\.com/d/file/down/[^\s"\']+\.txt)', r2.text):
        return mm.group(1)
    raise ValueError("800小说网 下载页未找到 TXT 直链")


def _txt800_chapters(url):
    try:
        dl = _txt800_resolve_download_url(url)
    except Exception:
        return [{"title": "全本", "url": url}]
    return [{"title": "全本", "url": dl}]


def _txt800_content(url):
    try:
        r = _get(url)
    except Exception as e:
        raise ValueError(f"800小说网 下载失败: {e}") from e
    raw = r.content
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    for enc in ("utf-8", "gbk", "gb2312", "gb18030", "big5"):
        try:
            text = raw.decode(enc)
            if len(text) > 100:
                return text.strip()
        except Exception:
            continue
    raise ValueError("800小说网 无法解码 TXT 内容")


# ---- 新笔趣阁 (bqgnovels)：JSON API，可读/可下 ----
def _search_bqgnovels(keyword, page=1, per_page=20):
    try:
        r = _get("https://bqgnovels.com/api/query/search", {"keyword": keyword})
    except Exception as e:
        raise ValueError(f"新笔趣阁 访问失败: {e}") from e
    try:
        data = r.json()
    except Exception:
        raise ValueError("新笔趣阁 响应不是合法 JSON")
    if data.get("code") != 200 or not data.get("data", {}).get("list"):
        raise ValueError("新笔趣阁 没有搜索到结果")
    items = []
    seen = set()
    for book in data["data"]["list"]:
        bid = book.get("id")
        title = re.sub(r"<[^>]+>", "", book.get("title", "")).strip()
        author = book.get("author", "") or ""
        if not bid or not title:
            continue
        url = f"https://bqgnovels.com/book/{bid}"
        if url in seen:
            continue
        seen.add(url)
        item = {"title": title[:120], "url": url, "source": "bqgnovels"}
        if author:
            item["author"] = author.strip()
        items.append(item)
    if not items:
        raise ValueError("新笔趣阁 没有搜索到结果")
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def _bqgnovels_chapters(url):
    m = re.search(r"/book/(\d+)", url)
    if not m:
        return []
    bid = m.group(1)
    try:
        r = _get(f"https://bqgnovels.com/api/query/get_book_list?bookId={bid}")
        data = r.json()
    except Exception:
        return []
    if data.get("code") != 200:
        return []
    chapters = []
    for ch in data.get("data", {}).get("list") or []:
        chid = ch.get("chapter_id")
        title = ch.get("tit", "")
        if not chid or not title:
            continue
        chapters.append(
            {"title": title[:120], "url": f"https://bqgnovels.com/book/{bid}/{chid}"}
        )
    return chapters


def _bqgnovels_content(url):
    m = re.search(r"/book/(\d+)/(\d+)", url)
    if not m:
        raise ValueError("新笔趣阁 无法解析章节链接")
    bid, chid = m.group(1), m.group(2)
    try:
        r = _get(f"https://bqgnovels.com/api/query/get_book_text?bookId={bid}&id={chid}")
        data = r.json()
    except Exception as e:
        raise ValueError(f"新笔趣阁 章节访问失败: {e}") from e
    if data.get("code") != 200 or not data.get("data", {}).get("text"):
        raise ValueError("新笔趣阁 未提取到正文内容")
    combined_parts = []
    for t in data["data"]["text"]:
        raw = t.get("text", "")
        if not raw:
            continue
        raw = re.sub(r"<!--.*?-->", "", raw)
        raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
        raw = re.sub(r"&nbsp;", " ", raw)
        raw = re.sub(r"<[^>]+>", "", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw).strip()
        if raw:
            combined_parts.append(raw)
    combined = "\n\n".join(combined_parts)
    if len(combined) > 50:
        return combined
    raise ValueError("新笔趣阁 未提取到正文内容")


def search_novel(keyword, source, page=1, per_page=20, count=None):
    if source not in SITES:
        raise ValueError("不支持的小说源: " + source)
    if source == "hhe62":
        return _h62_search(keyword, page, per_page, count=count)
    if source == "biquga":
        return _search_biquga(keyword, page, per_page)
    if source == "txt800":
        return _search_txt800(keyword, page, per_page)
    if source == "bqgnovels":
        return _search_bqgnovels(keyword, page, per_page)
    if source == "ttkan":
        items = _search_ttkan(keyword, page, per_page)
        return items, bool(items)
    if source == "alicesw":
        return _alicesw_search(keyword, page, per_page)
    # xbookcn / 69story 搜索仅返回分类标签或需繁体词，直接提示
    if source == "xbookcn":
        raise ValueError("中文成人文学(xbookcn)站内搜索只返回作品分类，无法按关键词直接检索文章；建议改用 AAA成人小说/3H淫书等支持关键词搜索的源")
    if source == "69story":
        raise ValueError("69成人小说搜索接口异常（站点反爬/需繁体关键词），建议改用 AAA成人小说/3H淫书等源")
    base = SITES[source]["url"]
    # 英文源：中文搜索词翻译成英文
    search_kw = to_en(keyword) if not SITES[source]["zh"] else keyword
    session = _session()
    try:
        r = _post(base, data={"s": search_kw})
    except Exception as e:
        raise ValueError(f"{SITES[source]['label']} 访问失败: {e}") from e
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if len(title) < 4 or re.search(r"(login|register|feed|favicon|\.css|\.js)", href, re.I):
            continue
        if href.startswith("/"):
            url = base + href
        elif href.startswith("http") and base in href:
            url = href
        else:
            continue
        path = url[len(base):]
        if path in ("", "/", "/page/") or re.match(r"^/(category|tag|author|feed)/", path):
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": title[:120], "url": url, "source": source})
        if len(items) >= per_page:
            break
    if not items:
        raise ValueError(f"{SITES[source]['label']} 没有搜索到结果")
    # 标题统一为简体中文；英文源再额外翻译
    if not SITES[source]["zh"]:
        for it in items:
            t = _t2s(to_zh(it["title"]))
            if t != it["title"]:
                it["title_en"] = it["title"]
                it["title"] = t
    else:
        for it in items:
            it["title"] = _t2s(it["title"])
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def _biquga_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Referer": "https://www.biquga.com/",
    })
    return s


def _search_biquga(keyword, page=1, per_page=20):
    s = _biquga_session()
    try:
        r = s.post(
            "https://www.biquga.com/search.html", data={"s": keyword}, timeout=25
        )
    except Exception as e:
        try:
            r = s.post(
                "https://www.biquga.com/search.html", data={"s": keyword}, timeout=25
            )
        except Exception as e2:
            raise ValueError(f"笔趣阁 访问失败: {e2}") from e2
    if r.status_code != 200:
        raise ValueError(f"笔趣阁 访问失败(HTTP {r.status_code})")
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if not re.match(r"/\d+_\d+/$", href):
            continue
        if len(title) < 2:
            continue
        url = "https://www.biquga.com" + href
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": title[:120], "url": url, "source": "biquga"})
    if not items:
        raise ValueError("笔趣阁 没有搜索到结果")
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def _biquga_content(html):
    """笔趣阁正文为 document.writeln(qsbs.bb('base64')) 加密，base64 解码为 HTML 文本"""
    parts = re.findall(r"qsbs\.bb\(\s*['\"]([^'\"]+)['\"]\s*\)", html)
    if parts:
        out = []
        for b in parts:
            try:
                raw = base64.b64decode(b).decode("utf-8", "replace")
            except Exception:
                continue
            raw = re.sub(r"<(?:p|br|div)[^>]*>", "\n", raw, flags=re.I)
            raw = re.sub(r"<[^>]+>", " ", raw)
            out.append(raw)
        text = "".join(out)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if text:
            return text
    return None


def biquga_chapters(url):
    """笔趣阁/爱丽丝书屋/天天看/新笔趣阁/800小说网目录页 -> 全部章节 [{title, url}]（第一章在前）"""
    if "ttkan.co" in url:
        nid = _ttkan_extract_novel_id(url)
        if not nid:
            raise ValueError("无法解析天天看小说目录")
        return _ttkan_chapters(nid)
    if "alicesw.com" in url:
        return _alicesw_chapters_url(url)
    if "bqgnovels.com" in url:
        return _bqgnovels_chapters(url)
    if "txt800.cc" in url:
        return _txt800_chapters(url)
    if re.search(r"/\d+_\d+/\d+\.html", url):
        return []
    try:
        r = _biquga_session().get(url, timeout=25)
    except Exception as e:
        raise ValueError(f"目录获取失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"目录获取失败(HTTP {r.status_code})")
    chapters = []
    seen = set()
    skip = {"开始阅读", "章节目录", "返回目录", "本书简介", "最新章节"}
    for m in re.finditer(r'<a[^>]+href="(/\d+_\d+/\d+\.html)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if not title or len(title) < 1 or title in skip:
            continue
        url = "https://www.biquga.com" + href
        if url in seen:
            continue
        seen.add(url)
        chapters.append({"title": _t2s(title)[:120], "url": url})
    if not chapters:
        raise ValueError("目录页没有章节链接")
    chapters.sort(key=lambda c: int(re.search(r"/(\d+)\.html", c["url"]).group(1)))
    return chapters


def get_novel_chapters(url):
    """公共入口：任意小说目录页 -> 全部章节 [{title, url}]（按 host 分发）"""
    if not url or not str(url).strip():
        raise ValueError("url 不能为空")
    return biquga_chapters(str(url).strip())


def _alicesw_text(url):
    """爱丽丝书屋：正文从 .read-content 容器提取"""
    for _ in range(3):
        try:
            r = _get(url)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        m = re.search(r'<div[^>]*class="[^"]*read-content[^"]*"[^>]*>(.*?)</div>', r.text, re.S)
        if not m:
            txt = _extract_text(r.text)
            if txt and len(txt) > 100:
                return txt
            continue
        txt = m.group(1)
        txt = re.sub(r"<(?:p|div|br|h[1-6]|li)[^>]*>", "\n", txt, flags=re.I)
        txt = re.sub(r"</(?:p|div|h[1-6]|li)>", "\n", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
        if len(txt) > 100:
            return txt
    return None


def _alicesw_chapters_url(url):
    """详情页 -> 章节列表（与 biquga_chapters 同签名）"""
    if "/other/chapters/" in url:
        try:
            rc = _get(url)
        except Exception:
            return []
        if rc.status_code != 200:
            return []
        chapters = []
        seen = set()
        for m in re.finditer(r'<a[^>]+href="(/book/\d+/[^"]+\.html)"[^>]*>(.*?)</a>', rc.text, re.S):
            href, inner = m.group(1), m.group(2)
            title = re.sub(r"<[^>]+>", "", inner).strip()
            if not title:
                continue
            u = "https://alicesw.com" + href
            if u in seen:
                continue
            seen.add(u)
            chapters.append({"title": _t2s(title)[:120], "url": u})
        return chapters
    try:
        r = _get(url)
    except Exception as e:
        raise ValueError(f"目录获取失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"目录获取失败(HTTP {r.status_code})")
    cm = re.search(r'href="(/other/chapters/id/\d+\.html)"', r.text)
    if not cm:
        return []
    return _alicesw_chapters_url("https://alicesw.com" + cm.group(1))


def _alicesw_search(keyword, page=1, per_page=20):
    try:
        r = _get("https://alicesw.com/search", {"q": keyword})
    except Exception as e:
        raise ValueError(f"爱丽丝书屋 访问失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"爱丽丝书屋 访问失败(HTTP {r.status_code})")
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="(/novel/\d+\.html)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        title = re.sub(r"^\d+[\.、]\s*", "", title)
        if len(title) < 2:
            continue
        url = "https://alicesw.com" + href
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": _t2s(title)[:120], "url": url, "source": "alicesw"})
    if not items:
        raise ValueError("爱丽丝书屋 没有搜索到结果")
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def get_novel_content(url, translate=False):
    if "ttkan.co" in url:
        text = _ttkan_content(url)
        if not text:
            raise ValueError("正文内容为空")
        if translate:
            text = translate_to_zh(text)
        return _t2s(text)
    if "hhe62" in url or "zfxdrshm.top" in url:
        return _h62_content(url, translate)
    if "biquga.com" in url:
        ch = _biquga_chapter_url(url)
        if not ch:
            raise ValueError("未找到章节链接")
        text = _biquga_text(ch)
        if not text:
            raise ValueError("未提取到正文内容")
        text = _clean_text(text)
        if not text:
            raise ValueError("正文内容为空")
        if translate:
            text = translate_to_zh(text)
        return _t2s(text)
    if "txt800.cc" in url or "8080txt.com" in url or "txt8080.com" in url:
        text = _clean_text(_txt800_content(url))
        if not text:
            raise ValueError("正文内容为空")
        if translate:
            text = translate_to_zh(text)
        return _t2s(text)
    if "bqgnovels.com" in url:
        text = _clean_text(_bqgnovels_content(url))
        if not text:
            raise ValueError("正文内容为空")
        if translate:
            text = translate_to_zh(text)
        return _t2s(text)
    if "alicesw.com" in url:
        text = _alicesw_text(url)
        if not text:
            raise ValueError("未提取到正文内容")
        text = _clean_text(text)
        if not text:
            raise ValueError("正文内容为空")
        if translate:
            text = translate_to_zh(text)
        return _t2s(text)
    text = None
    for attempt in range(3):
        try:
            r = _get(url)
        except Exception:
            continue
        if r.status_code == 200:
            text = _extract_text(r.text)
            if text and len(text) > 100:
                break
    if not text:
        raise ValueError("未提取到正文内容")
    text = _clean_text(text)
    if not text:
        raise ValueError("正文内容为空")
    if translate:
        text = translate_to_zh(text)
    return _t2s(text)


def _biquga_chapter_url(url):
    """目录页 -> 第一章章节页 URL；已是章节页则原样返回"""
    if re.search(r"/\d+_\d+/\d+\.html", url):
        return url
    try:
        r = _biquga_session().get(url, timeout=25)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    chs = re.findall(r'href="(/\d+_\d+/\d+\.html)"', r.text)
    if not chs:
        return None
    chs = sorted(set(chs), key=lambda h: int(re.search(r"/(\d+)\.html", h).group(1)))
    return "https://www.biquga.com" + chs[0]


def _biquga_text(url):
    for _ in range(3):
        try:
            r = _biquga_session().get(url, timeout=25)
        except Exception:
            continue
        if r.status_code == 200:
            text = _biquga_content(r.text)
            if text:
                return text
            text = _extract_text(r.text)
            if text and len(text) > 100:
                return text
    return None


if __name__ == "__main__":
    # quick test
    items, has = search_novel("盗墓笔记", "biquga")
    print(items[:2])
