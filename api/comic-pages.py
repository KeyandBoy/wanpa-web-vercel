import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import check_token
from _core import api_comic_pages, err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0]
        token = (qs.get("token") or [""])[0].strip()
        limit = None
        if qs.get("limit"):
            try:
                limit = max(1, min(int(qs["limit"][0]), 200))
            except ValueError:
                limit = None
        if not url:
            body, headers, status = err_json(400, "url 不能为空")
        elif not check_token(token):
            body, headers, status = err_json(403, "漫画为 Plus 专属功能，请先激活 Plus 版本")
        else:
            try:
                payload, headers = ok_json(api_comic_pages(url, limit))
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
