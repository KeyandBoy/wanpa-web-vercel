import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import check_token, is_plus_source
from _core import api_search, err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        source = (qs.get("source") or [""])[0].strip().lower()
        token = (qs.get("token") or [""])[0].strip()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        try:
            count = int((qs.get("count") or ["20"])[0] or "20")
        except ValueError:
            count = 20
        if not keyword or not source:
            body, headers, status = err_json(400, "keyword 和 source 不能为空")
        elif is_plus_source(source) and not check_token(token):
            body, headers, status = err_json(403, "该数据源为 Plus 专属，请先激活 Plus 版本")
        else:
            try:
                payload, headers = ok_json(api_search(keyword, source, page, count))
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
