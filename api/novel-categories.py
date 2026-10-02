import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import classify_error, err_json, ok_json
from _novel_core import ttkan_categories


class handler(BaseHTTPRequestHandler):
    """列出支持分类浏览的小说源分类（当前为天天看小说）。"""

    def do_GET(self):
        try:
            payload, headers = ok_json(
                {"source": "ttkan", "categories": ttkan_categories()}
            )
            status = 200
            body = payload
        except Exception as e:
            body, headers, status = err_json(500, str(e), error_type=classify_error(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
