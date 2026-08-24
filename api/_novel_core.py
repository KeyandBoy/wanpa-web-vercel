import base64
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    p = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    if p:
        return p
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
    "bdsmcafe": {"url": "https://bdsmcafe.com/", "label": "BDSMCafe", "zh": False},
    "chyoa": {"url": "https://chyoa.com/", "label": "CHYOA", "zh": False},
    "alicesw": {"url": "https://alicesw.com/", "label": "爱丽丝书屋", "zh": True},
    "hhe62": {"url": "https://zfxdrshm.top:2549/", "label": "hhe62小说", "zh": True},
}

# Plus 专属小说源（除 biquga 外全部为成人/海外，需激活）
_PLUS_NOVEL_IDS = {k for k in SITES if k != "biquga"}
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


def search_novel(keyword, source, page=1, per_page=20, count=None):
    if source not in SITES:
        raise ValueError("不支持的小说源: " + source)
    if source == "hhe62":
        return _h62_search(keyword, page, per_page, count=count)
    if source == "biquga":
        return _search_biquga(keyword, page, per_page)
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
    """笔趣阁/爱丽丝书屋目录页 -> 全部章节 [{title, url}]（按章节顺序，第一章在前）"""
    if "alicesw.com" in url:
        return _alicesw_chapters_url(url)
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
