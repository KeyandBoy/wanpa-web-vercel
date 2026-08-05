import base64
import re

import requests

BASE = "https://www.biquga.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": BASE + "/"})
    return s


def search_biquga(keyword, page=1, per_page=20):
    try:
        r = _session().post(BASE + "/search.html", data={"s": keyword}, timeout=25)
    except Exception as e:
        raise ValueError(f"笔趣阁访问失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"笔趣阁访问失败(HTTP {r.status_code})")
    items = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if not re.match(r"/\d+_\d+/$", href):
            continue
        if len(title) < 2:
            continue
        url = BASE + href
        if url in seen:
            continue
        seen.add(url)
        items.append({"title": title[:120], "url": url, "source": "biquga"})
    if not items:
        raise ValueError("笔趣阁没有搜索到结果")
    start = max(page - 1, 0) * per_page
    return items[start : start + per_page], bool(items)


def get_biquga_content(url):
    ch_url = url if re.search(r"/\d+_\d+/\d+\.html", url) else _first_chapter(url)
    if not ch_url:
        raise ValueError("未找到章节链接")
    try:
        r = _session().get(ch_url, timeout=25)
    except Exception as e:
        raise ValueError(f"笔趣阁访问失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"笔趣阁访问失败(HTTP {r.status_code})")
    text = _decode(r.text)
    if not text:
        text = _extract_text(r.text)
    if not text:
        raise ValueError("未提取到正文内容")
    return _clean(text)


def get_biquga_chapters(url):
    try:
        r = _session().get(url, timeout=25)
    except Exception as e:
        raise ValueError(f"笔趣阁访问失败: {e}") from e
    if r.status_code != 200:
        raise ValueError(f"笔趣阁访问失败(HTTP {r.status_code})")
    chapters = []
    seen = set()
    for m in re.finditer(r'<a[^>]+href="(/\d+_\d+/\d+\.html)"[^>]*>(.*?)</a>', r.text, re.S):
        href, inner = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if not title:
            continue
        url = BASE + href
        if url in seen:
            continue
        seen.add(url)
        chapters.append({"title": title[:120], "url": url})
    if not chapters:
        raise ValueError("未获取到章节目录")
    return chapters


def _first_chapter(url):
    try:
        r = _session().get(url, timeout=25)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    chs = re.findall(r'href="(/\d+_\d+/\d+\.html)"', r.text)
    if not chs:
        return None
    chs = sorted(set(chs), key=lambda h: int(re.search(r"/(\d+)\.html", h).group(1)))
    return BASE + chs[0]


def _decode(html):
    parts = re.findall(r"qsbs\.bb\(\s*['\"]([^'\"]+)['\"]\s*\)", html)
    if not parts:
        return None
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
    return text or None


def _extract_text(html):
    m = re.search(r'<div[^>]*id="content"[^>]*>(.*?)</div>', html, re.S)
    if m:
        txt = m.group(1)
        txt = re.sub(r"<(?:p|div|br)[^>]*>", "\n", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = re.sub(r"[ \t]+", " ", txt)
        txt = re.sub(r"\n\s*\n+", "\n", txt).strip()
        if len(txt) > 50:
            return txt
    ps = []
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.S):
        t = re.sub(r"<[^>]+>", " ", m.group(1)).strip()
        if len(t) > 30:
            ps.append(t)
    return "\n".join(ps) if ps else None


def _clean(text):
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            lines.append("")
            continue
        if (
            "请关闭浏览器阅读模式" in line
            or "本站所有小说" in line
            or "搜索功能" in line
            or "回到目录" in line
            or "加入书签" in line
        ):
            continue
        if re.match(r"^(上一章|下一章|章节目录|返回目录|回到书页|手机阅读|设置|加入书架|书签)", line):
            continue
        if re.match(r"^.{0,4}章.{0,4}推荐|^推荐.{0,6}本章", line):
            continue
        if re.search(r"(微信公众号|qq\s*群|qq\s*号|官方群|加群|粉丝群|vx|微信)", line, re.I):
            continue
        lines.append(line)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


# ============================== 多源分发 ==============================
def search_novel(keyword, source, page=1, per_page=20, count=None):
    """小说搜索分发：biquga=笔趣阁 / hhe62=hhe62成人小说"""
    source = (source or "").lower()
    if source == "hhe62":
        from maccms_svc import search_novel as _h62_search

        items, has_more = _h62_search(keyword, page, per_page, count=count)
        return items, has_more
    items, has_more = search_biquga(keyword, page, per_page)
    return items, has_more


def get_novel_content(url, translate=False):
    """正文获取分发：按 URL 判定数据源"""
    if "hhe62" in url or "zfxdrshm.top" in url:
        from maccms_svc import get_novel_content as _h62_content

        return _h62_content(url, translate)
    return get_biquga_content(url)


def get_novel_chapters(url):
    """章节目录分发：仅支持章节式站点；hhe62 为单页正文，返回空"""
    if "hhe62" in url or "zfxdrshm.top" in url:
        return []
    return get_biquga_chapters(url)
