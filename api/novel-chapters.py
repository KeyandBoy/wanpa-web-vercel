import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import err_json, ok_json
from _novel_core import get_biquga_chapters


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0]
        if not url:
            body, headers, status = err_json(400, "url 不能为空")
        else:
            try:
                chapters = get_biquga_chapters(url)
                payload, headers = ok_json({"chapters": chapters})
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
