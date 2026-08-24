"""hhe62（zfxdrshm.top:2549，MacCMS 成人站）图片/小说数据源（Vercel 版）。

页面 HTML 经 AES-128-CBC 加密 + gzip 混淆：
  密钥 = 该页首个 div[data-content] 文本前 16 字符，IV = 同密钥。
加密仅用于防爬/混淆，非安全用途，本地解密后即为正常 HTML。

数据获取方式：该站无可用关键词搜索，遍历各分类最新列表按标题本地匹配。

分类：
  图片（美图）: 42 精品图集 / 43 欧美风情 / 44 亚洲情色 / 45 性爱自拍 / 47 美腿丝袜 / 48 唯美写真 / 49 人体艺术
  小说: 51-58 共 8 类（正文在详情页 .newsbody）
"""

import base64
import gzip
import html
import os
import re
import threading
import urllib3
from concurrent.futures import ThreadPoolExecutor

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from trans_svc import to_ja, translate_many

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_BASE = "https://zfxdrshm.top:2549"
BASE = os.environ.get("MACCMS_BASE") or DEFAULT_BASE

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

PIC_CATES = [42, 43, 44, 45, 47, 48, 49]  # 美图分类
TXT_CATES = [51, 52, 53, 54, 55, 56, 57, 58]  # 小说分类
PAGES = 3  # 每分类翻页深度（默认 3 页，约 60 条）

MAX_ALBUMS = 8  # 图片源最多抓取前几个匹配图集的图片

_LABELS = {
    42: "精品图集",
    43: "欧美风情",
    44: "亚洲情色",
    45: "性爱自拍",
    47: "美腿丝袜",
    48: "唯美写真",
    49: "人体艺术",
    51: "都市情感",
    52: "人妻熟女",
    53: "玄幻武侠",
    54: "另类其它",
    55: "明星校园",
    56: "家庭乱伦",
    57: "成人小说",
    58: "暴力虐待",
}


def _decrypt(text):
    """AES-128-CBC(密钥=首个 data-content 前16字符, IV=同密钥) + gzip 解压"""
    texts = re.findall(r'<div[^>]*data-content=""[^>]*>([^<]*)</div>', text)
    if not texts:
        return text
    key = texts[0][:16].encode("utf-8")
    if len(key) != 16:
        return text
    parts = []

    def _dec(data):
        try:
            raw = base64.b64decode(data)
        except Exception:
            return ""
        cipher = Cipher(algorithms.AES(key), modes.CBC(key)).decryptor()
        try:
            pt = cipher.update(raw) + cipher.finalize()
        except Exception:
            return ""
        pad = pt[-1]
        if 1 <= pad <= 16:
            pt = pt[:-pad]
        try:
            return gzip.decompress(pt).decode("utf-8", "replace")
        except Exception:
            return ""

    for i, t in enumerate(texts):
        parts.append(_dec(t[16:] if i == 0 else t))
    return "".join(parts)


def _fetch(url, timeout=20):
    """抓取页面并解密为正常 HTML；无加密 div 时原样返回"""
    try:
        from env_utils import proxies as _proxies

        proxies = _proxies()
    except Exception:
        proxies = None
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout, verify=False, proxies=proxies)
    r.raise_for_status()
    return _decrypt(r.text)


def _list_url(channel, cate_id, page):
    return f"{BASE}/{channel}/list.html?cate_id={cate_id}&page={page}"


def _parse_pic_list(h):
    """图片/漫画列表页 -> [(detail_url, title)]"""
    out = []
    for block in re.split(r'<div class="listpic">', h)[1:]:
        um = re.search(r'<a[^>]*href="([^"]*detail\.html\?id=\d+[^"]*)"[^>]*>', block)
        nm = re.search(r'class="vodname">([^<]+)</div>', block)
        if um and nm:
            out.append((html.unescape(um.group(1)), nm.group(1).strip()))
    return out


def _parse_txt_list(h):
    """小说列表页 -> [(detail_url, title)]"""
    out = []
    for m in re.finditer(
        r'<a[^>]+href="(/txt/detail\.html\?id=\d+[^"]*)"[^>]*>\s*([^<]{2,60})\s*</a>',
        h,
        re.S,
    ):
        out.append((html.unescape(m.group(1)), m.group(2).strip()))
    return out


def _abs(u):
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return BASE + u
    return BASE + "/" + u


def _collect_matches(channel, cates, keyword, kw2=None, per_page=20, pages=PAGES, translate_match=False, target=None, max_pages=None):
    """并发遍历各分类列表，按关键词子串匹配标题，返回 [(detail_url, title)]

    translate_match=True 时（漫画源，标题多为日文假名），额外对每页标题批量翻译后
    再检测中文关键词，能匹配到「マンガ」这类假名标题。

    target 指定目标匹配数量：达到即提前停止，并据此动态扩大翻页深度。
    max_pages 覆盖单分类最大翻页数（防过度请求）。
    """
    if max_pages:
        pages = min(pages, max_pages)
    if target is not None and max_pages:
        # 目标数量下命中稀疏（尤其翻译匹配），直接用最大翻页深度收集
        pages = max_pages
    pairs = []
    seen = set()

    def _scan(cate_id, pg):
        try:
            h = _fetch(_list_url(channel, cate_id, pg), timeout=15)
        except Exception:
            return []
        items = _parse_pic_list(h) if channel != "txt" else _parse_txt_list(h)
        if not items:
            return []
        zh_map = {}
        if translate_match:
            try:
                zh_map = translate_many([t for _, t in items], force=True)
            except Exception:
                zh_map = {}
        found = []
        for u, t in items:
            hit = keyword in t or (kw2 and kw2 in t)
            if not hit and translate_match:
                z = zh_map.get(t, t)
                hit = keyword in z
            if hit:
                found.append((u, t))
        return found

    def _page_for(cate_id, pg):
        items = _scan(cate_id, pg)
        return [(u, t) for u, t in items if u not in seen]

    workers = min(4, len(cates))
    for pg in range(1, pages + 1):
        if target is not None and len(pairs) >= target:
            break
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda c: _page_for(c, pg), cates))
        for items in results:
            for u, t in items:
                seen.add(u)
                pairs.append((u, t))
                if target is not None and len(pairs) >= target:
                    break
            if target is not None and len(pairs) >= target:
                break
    return pairs


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


def _extract_detail_imgs(h):
    """详情页提取全部大图 URL（jpg/jpeg/png/webp）"""
    imgs = []
    seen = set()
    for m in re.finditer(r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)', h):
        u = m.group(0)
        if u in seen:
            continue
        seen.add(u)
        imgs.append(u)
    return imgs


# ============================== 图片（美图） ==============================
_cache = {}
_cache_lock = threading.Lock()


def search_pic(keyword, page=1, per_page=20, count=None):
    """关键词 -> 匹配的美图图集全部图片（交错排列，缓存整个结果）

    count 为目标图片数量：动态翻页直到匹配图集足够提供该数量图片。
    返回 ([{url, title, width, height, group}], has_more)
    """
    global _cache
    key = ("pic", keyword, count or per_page)
    with _cache_lock:
        pairs = _cache.get(key)
    if pairs is None:
        kw2 = None
        try:
            ja = to_ja(keyword)
            kw2 = ja if ja and ja != keyword else None
        except Exception:
            kw2 = None
        need_albums = MAX_ALBUMS
        if count:
            need_albums = max(MAX_ALBUMS, (count + 20 - 1) // 20 + 2)
            need_albums = min(need_albums, 40)
        matched = _collect_matches("pic", PIC_CATES, keyword, kw2, target=need_albums, max_pages=8)
        matched = matched[:need_albums]
        if not matched:
            raise ValueError("hhe62美图 没有搜索到结果")
        all_pairs = []
        for u, title in matched:
            try:
                h = _fetch(_abs(u), timeout=15)
            except Exception:
                continue
            imgs = _extract_detail_imgs(h)
            if not imgs:
                continue
            for img in imgs:
                all_pairs.append((u, img))
        pairs = _interleave(all_pairs)
        if not pairs:
            raise ValueError("hhe62美图 没有提取到图片")
        with _cache_lock:
            _cache[key] = pairs
    start = max(page - 1, 0) * per_page
    slice_ = pairs[start : start + per_page]
    if not slice_:
        return [], False
    tr = {}
    try:
        tr = translate_many([keyword])
    except Exception:
        tr = {}
    zh = tr.get(keyword, keyword)
    items = [
        {"url": u, "title": zh, "width": None, "height": None, "group": g}
        for g, u in slice_
    ]
    has_more = len(pairs) > start + per_page
    return items, has_more


# ============================== 小说 ==============================
def search_novel(keyword, page=1, per_page=20, count=None):
    """关键词 -> 匹配的小说列表（标题+详情链接）

    count 为目标数量：动态翻页直到匹配到足够条目。
    """
    kw2 = None
    try:
        ja = to_ja(keyword)
        kw2 = ja if ja and ja != keyword else None
    except Exception:
        kw2 = None
    target = count if count else per_page
    matched = _collect_matches("txt", TXT_CATES, keyword, kw2, target=target, max_pages=10)
    if not matched:
        raise ValueError("hhe62小说 没有搜索到结果")
    items = []
    for u, title in matched:
        items.append({"title": title[:120], "url": _abs(u), "source": "hhe62"})
    tr = {}
    try:
        tr = translate_many([it["title"] for it in items])
    except Exception:
        tr = {}
    for it in items:
        zh = tr.get(it["title"], it["title"])
        if zh != it["title"]:
            it["title_en"] = it["title"]
            it["title"] = zh
    start = max(page - 1, 0) * per_page
    if count:
        start = 0
        slice_ = items[:count]
        has_more = False
    else:
        slice_ = items[start : start + per_page]
        has_more = len(items) > start + per_page
    return slice_, has_more


def get_novel_content(url, translate=False):
    """小说详情页 -> 正文（优先 .nbodys，回退 .newsbody / 全页）"""
    try:
        h = _fetch(_abs(url), timeout=15)
    except Exception as e:
        raise ValueError(f"hhe62小说 访问失败: {e}") from e
    m = re.search(r'<div[^>]*class="[^"]*nbodys[^"]*"[^>]*>(.*?)</div>', h, re.S)
    if not m:
        m = re.search(r'<div[^>]*class="[^"]*newsbody[^"]*"[^>]*>(.*?)</div>', h, re.S)
    text = m.group(1) if m else None
    if not text:
        text = re.sub(r"<script.*?</script>", "", h, flags=re.S)
        text = re.sub(r"<style.*?</style>", "", text, flags=re.S)
        text = re.sub(r"<(?:p|div|br|h[1-6]|li)[^>]*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if not text or len(text) < 100:
            raise ValueError("未提取到正文内容")
    else:
        text = re.sub(r"<(?:p|div|br|h[1-6]|li)[^>]*>", "\n", text, flags=re.I)
        text = re.sub(r"</(?:p|div|h[1-6]|li)>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if len(text) < 100:
            raise ValueError("未提取到正文内容")
    if translate:
        try:
            from trans_svc import to_zh

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
            if chunks:
                from concurrent.futures import ThreadPoolExecutor

                with ThreadPoolExecutor(max_workers=4) as ex:
                    results = list(ex.map(to_zh, chunks))
                text = "\n\n".join(results)
        except Exception:
            pass
    return text


def clear_cache():
    global _cache
    with _cache_lock:
        _cache.clear()
