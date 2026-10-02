import os
import sys
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import classify_error, err_json, ok_json
from _novel_core import _ttkan_category

_PER_PAGE = 20
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


class handler(BaseHTTPRequestHandler):
    """按分类浏览天天看小说（ttkan）书籍列表。"""

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        ctype = (qs.get("type") or [""])[0].strip()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        page = max(page, 1)
        cache_key = f"ttkan_cat:{ctype}:{page}"
        cached = _cached_get(cache_key)
        if cached is not None:
            payload, headers = ok_json(cached)
            status = 200
            body = payload
        else:
            try:
                items = _ttkan_category(ctype, page, _PER_PAGE)
                result = {
                    "source": "ttkan",
                    "type": ctype,
                    "page": page,
                    "items": items,
                    "has_more": len(items) >= _PER_PAGE,
                }
                _cached_set(cache_key, result)
                payload, headers = ok_json(result)
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e), error_type=classify_error(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
