import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import ok_json, err_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        import book_svc
        body, headers = ok_json(book_svc.source_catalog())
        self.send_response(200)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
