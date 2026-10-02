"""抖音单视频/图集解析（无水印）。

参考开源项目 douyin_crawl (https://github.com/zouzanyan/douyin_crawl) 的思路：
- 走移动端分享页 https://www.iesdouyin.com/share/video/{aweme_id}/ 提取 _ROUTER_DATA
- 无需 cookie、无需签名，稳定且匿名
- 图集返回无水印原图 URL 列表
"""

import json
import re

import requests

MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.6 Mobile/15E148 Safari/604.1"
)
HOMEPAGE_URL = "https://www.iesdouyin.com/"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": MOBILE_UA})

_URL_RE = re.compile(r"https?://[^\s，。]+")
_VIDEO_ID_RE = re.compile(r"/(?:video|note)/(\d+)")
_LONG_DIGIT_RE = re.compile(r"(\d{15,})")

_SHARE_PATHS = (
    "https://www.iesdouyin.com/share/video/{id}/",
    "https://www.iesdouyin.com/share/note/{id}/",
)
_PAGE_PATHS = (
    "https://www.douyin.com/video/{id}",
    "https://www.douyin.com/note/{id}",
)


class DouyinParseError(ValueError):
    """抖音解析失败"""


def extract_url(text):
    """从分享文本中提取 http(s) 链接。"""
    if not text:
        raise DouyinParseError("输入为空")
    m = _URL_RE.search(text)
    if not m:
        raise DouyinParseError(f"未在输入中找到链接: {text}")
    return m.group(0)


def get_aweme_id(url):
    """从抖音链接解析 aweme_id (支持短链重定向)。"""
    m = _VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)
    try:
        resp = _SESSION.get(url, headers={"User-Agent": MOBILE_UA}, allow_redirects=True, timeout=10)
        final_url = resp.url
    except Exception:
        final_url = url
    m = _VIDEO_ID_RE.search(final_url)
    if m:
        return m.group(1)
    m = _LONG_DIGIT_RE.search(final_url)
    if m:
        return m.group(1)
    raise DouyinParseError(f"无法从链接解析视频 ID: {url}")


def _get(url):
    """请求页面，返回 HTML 文本或 None"""
    try:
        resp = _SESSION.get(
            url,
            headers={
                "User-Agent": MOBILE_UA,
                "Referer": HOMEPAGE_URL,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            allow_redirects=True,
            timeout=10,
        )
    except Exception:
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    return resp.text


def fetch_page_data(aweme_id):
    """请求分享页/原网页并解析数据，返回 (html, data)。

    依次尝试: /share/video/ → /share/note/ → douyin.com/video|note
    每个页面依次尝试: _ROUTER_DATA → RENDER_DATA
    """
    last_html = None
    for tpl in _SHARE_PATHS + _PAGE_PATHS:
        html = _get(tpl.format(id=aweme_id))
        if not html:
            continue
        last_html = html
        data = extract_router_data(html) or extract_render_data(html)
        if data:
            return html, data
    raise DouyinParseError("无法解析页面数据，抖音接口可能已变更")


def extract_render_data(html):
    """兜底：提取 <script id="RENDER_DATA"> 里的 URL 编码 JSON"""
    m = re.search(r'<script[^>]+id\s*=\s*"RENDER_DATA"[^>]*>(.*?)</script>', html, re.S | re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if not raw:
        return None
    try:
        from urllib.parse import unquote

        return json.loads(unquote(raw))
    except Exception:
        try:
            return json.loads(raw)
        except Exception:
            return None


def extract_router_data(html):
    """括号深度匹配提取 _ROUTER_DATA JSON。"""
    marker = "window._ROUTER_DATA = "
    idx = html.find(marker)
    if idx < 0:
        idx = html.find("_ROUTER_DATA")
        if idx < 0:
            return None
        eq = html.find("=", idx)
        if eq < 0:
            return None
        start = eq + 1
    else:
        start = idx + len(marker)
    while start < len(html) and html[start].isspace():
        start += 1
    if start >= len(html) or html[start] != "{":
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(html)):
        c = html[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except (ValueError, json.JSONDecodeError):
                    return None
    return None


class _VideoMeta:
    """_walk_find 的累加器。"""

    __slots__ = ("play_urls", "video_id", "title", "author")

    def __init__(self):
        self.play_urls = []
        self.video_id = None
        self.title = None
        self.author = None


def _walk_find(obj, found):
    """递归在 JSON 树中提取视频信息。"""
    if isinstance(obj, list):
        for v in obj:
            _walk_find(v, found)
        return
    if not isinstance(obj, dict):
        return
    url_list = obj.get("url_list")
    if isinstance(url_list, list) and url_list:
        urls = [u for u in url_list if isinstance(u, str) and u]
        if urls and any("play" in u for u in urls):
            found.play_urls.extend(urls)
    uri = obj.get("uri")
    if isinstance(uri, str) and not found.video_id:
        if re.match(r"^v[0-9a-f]+$", uri):
            found.video_id = uri
    if isinstance(obj.get("desc"), str) and not found.title:
        found.title = obj["desc"]
    if isinstance(obj.get("nickname"), str) and not found.author:
        found.author = obj["nickname"]
    for v in obj.values():
        _walk_find(v, found)


def build_play_url(video_id, ratio="default", base_url=None):
    """构造无水印播放地址。"""
    if base_url:
        m = re.search(r"(https?://[^/]+/aweme/v1/play(?:wm)?/)", base_url)
        if m:
            prefix = m.group(1).replace("playwm", "play")
        else:
            prefix = "https://aweme.snssdk.com/aweme/v1/play/"
        extra = ""
        em = re.search(r"&(line=\d+)", base_url)
        if em:
            extra = "&" + em.group(1)
        return f"{prefix}?video_id={video_id}&ratio={ratio}{extra}"
    return f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio={ratio}&line=0"


def _find_album_node(data):
    """递归查找含 images 数组的节点 (图集)。"""
    if not isinstance(data, (dict, list)):
        return None
    if isinstance(data, list):
        for v in data:
            r = _find_album_node(v)
            if r:
                return r
        return None
    images = data.get("images")
    if isinstance(images, list) and len(images) > 0:
        return data
    for v in data.values():
        r = _find_album_node(v)
        if r:
            return r
    return None


def _get_album_image_urls(data):
    """提取图集无水印原图 URL 列表。"""
    node = _find_album_node(data)
    if not node:
        return []
    images = node.get("images")
    if not isinstance(images, list):
        return []
    urls = []
    for img in images:
        if not isinstance(img, dict):
            continue
        dl = img.get("download_url_list")
        ul = img.get("url_list")
        url = ""
        if isinstance(dl, list) and dl and isinstance(dl[0], str):
            url = dl[0]
        elif isinstance(ul, list) and ul and isinstance(ul[0], str):
            url = ul[0]
        if url:
            urls.append(url)
    return urls


def parse_douyin(text):
    """解析抖音分享链接，返回 dict。

    - 视频: {"type": "video", "aweme_id", "title", "author", "video_url", "source_url"}
    - 图集: {"type": "album", "aweme_id", "title", "author", "image_urls": [...], "source_url"}
    """
    url = extract_url(text)
    aweme_id = get_aweme_id(url)
    html, data = fetch_page_data(aweme_id)

    meta = _VideoMeta()
    _walk_find(data, meta)
    title = meta.title or aweme_id
    author = meta.author or ""

    # 图集
    if _find_album_node(data):
        image_urls = _get_album_image_urls(data)
        if image_urls:
            return {
                "type": "album",
                "aweme_id": aweme_id,
                "title": title,
                "author": author,
                "image_urls": image_urls,
                "source_url": url,
            }
        raise DouyinParseError("未能从页面提取图集图片")

    # 视频
    video_id = meta.video_id
    if not video_id:
        for u in meta.play_urls:
            m = re.search(r"video_id=([0-9a-zA-Z]+)", u)
            if m:
                video_id = m.group(1)
                break
    if not video_id:
        raise DouyinParseError("未能从页面找到视频地址")

    template = next((u for u in meta.play_urls if "video_id=" in u), None)
    video_url = build_play_url(video_id, "default", template)
    return {
        "type": "video",
        "aweme_id": aweme_id,
        "title": title,
        "author": author,
        "video_url": video_url,
        "source_url": url,
    }
