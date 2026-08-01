import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import api_search, err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        source = (qs.get("source") or [""])[0].strip().lower()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        if not keyword or not source:
            body, headers, status = err_json(400, "keyword 和 source 不能为空")
        else:
            try:
                payload, headers = ok_json(api_search(keyword, source, page))
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
