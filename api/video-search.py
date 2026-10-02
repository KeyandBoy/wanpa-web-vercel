import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _auth import check_token, is_plus_video_source
from _core import classify_error, err_json, ok_json

# 随机源每次结果都不同，不参与缓存
_RANDOM_SOURCES = {"xjj"}
_CACHE = {}
_CACHE_TTL = 300


def _cached_get(key):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    return None


def _cached_set(key, value):
    _CACHE[key] = (time.time(), value)
    if len(_CACHE) > 200:
        for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:80]:
            _CACHE.pop(k, None)


def _search(source, keyword, count):
    """源 -> 搜索函数的分派表（jable 已整源移除：依赖浏览器）。"""
    if source == "youtube":
        from video_svc import search_youtube
        return search_youtube(keyword, count)
    if source == "bing":
        from video_svc import search_bing_video
        return search_bing_video(keyword, count)
    if source == "yahoo":
        from video_svc import search_yahoo
        return search_yahoo(keyword, count)
    if source == "pornhub":
        from video_svc import search_pornhub
        return search_pornhub(keyword, count)
    if source == "thothub":
        from video_svc import search_thothub
        return search_thothub(keyword, count)
    if source == "xnxx":
        from video_svc import search_xnxx
        return search_xnxx(keyword, count)
    if source == "xvideos":
        from video_svc import search_xvideos
        return search_xvideos(keyword, count)
    if source == "xhamster":
        from video_svc import search_xhamster
        return search_xhamster(keyword, count)
    if source == "bilibili":
        from video_svc import search_bilibili
        return search_bilibili(keyword, count)
    if source == "acfun":
        from video_svc import search_acfun
        return search_acfun(keyword, count)
    if source == "youku":
        from video_svc import search_youku
        return search_youku(keyword, count)
    if source == "mgtv":
        from video_svc import search_mgtv
        return search_mgtv(keyword, count)
    if source == "twitter":
        from twitter_svc import search_twitter
        return search_twitter(keyword, count)
    if source == "doll":
        from doll_svc import search_doll
        return search_doll(keyword, count)
    if source == "cg51":
        from cg51_svc import search_video_posts
        return search_video_posts(keyword, count)
    if source == "xjj":
        from random_svc import fetch_videos
        return fetch_videos(source, count)
    raise ValueError("不支持的视频源: " + source)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        source = (qs.get("source") or [""])[0].strip().lower()
        token = (qs.get("token") or [""])[0].strip()
        try:
            count = int((qs.get("count") or ["10"])[0] or "10")
        except ValueError:
            count = 10
        count = max(1, min(count, 30))

        if not keyword or not source:
            body, headers, status = err_json(400, "keyword 和 source 不能为空")
        elif is_plus_video_source(source) and not check_token(token):
            body, headers, status = err_json(
                403, f"{source} 视频为 Plus 专属功能，请先激活 Plus 版本"
            )
        else:
            cache_key = "video:%s:%s:%s" % (source, keyword, count)
            use_cache = source not in _RANDOM_SOURCES
            cached = _cached_get(cache_key) if use_cache else None
            if cached is not None:
                body, headers = ok_json(cached)
                status = 200
            else:
                try:
                    result = {"items": _search(source, keyword, count)}
                    if use_cache:
                        _cached_set(cache_key, result)
                    body, headers = ok_json(result)
                    status = 200
                except ValueError as e:
                    if "不支持的视频源" in str(e):
                        body, headers, status = err_json(400, str(e))
                    else:
                        body, headers, status = err_json(
                            500, str(e), error_type=classify_error(e)
                        )
                except Exception as e:
                    body, headers, status = err_json(
                        500, str(e), error_type=classify_error(e)
                    )
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
