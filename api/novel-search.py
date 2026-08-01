import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import err_json, ok_json
from _novel_core import search_biquga


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        if not keyword:
            body, headers, status = err_json(400, "keyword 不能为空")
        else:
            try:
                items, has_more = search_biquga(keyword, page)
                payload, headers = ok_json({"items": items, "has_more": has_more})
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
