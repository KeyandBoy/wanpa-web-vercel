import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import check_token, is_plus_source
from _core import classify_error, err_json, ok_json
from _novel_core import search_novel


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        source = (qs.get("source") or ["biquga"])[0].strip().lower() or "biquga"
        token = (qs.get("token") or [""])[0].strip()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        try:
            count = int((qs.get("count") or ["20"])[0] or "20")
        except ValueError:
            count = 20
        if not keyword:
            body, headers, status = err_json(400, "keyword 不能为空")
        elif is_plus_source(source) and not check_token(token):
            body, headers, status = err_json(403, f"{source} 小说为 Plus 专属功能，请先激活 Plus 版本")
        else:
            try:
                items, has_more = search_novel(keyword, source, page, count=count)
                payload, headers = ok_json({"items": items, "has_more": has_more})
                status = 200
                body = payload
            except Exception as e:
                etype = classify_error(e)
                body, headers, status = err_json(500, str(e), error_type=etype)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
