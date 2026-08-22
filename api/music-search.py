import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import ok_json, err_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        keyword = (qs.get("keyword") or [""])[0].strip()
        source = (qs.get("source") or ["all"])[0].strip()
        try:
            page = int((qs.get("page") or ["1"])[0] or "1")
        except ValueError:
            page = 1
        try:
            page_size = int((qs.get("page_size") or ["20"])[0] or "20")
        except ValueError:
            page_size = 20

        if not keyword:
            body, headers, status = err_json(400, "搜索关键词不能为空")
        else:
            try:
                import music_svc
                results = music_svc.search_music(keyword, source, page, page_size)
                payload, headers = ok_json({"items": results, "count": len(results)})
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))

        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
