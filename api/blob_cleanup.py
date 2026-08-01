import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import api_cleanup, err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            data = {}
        prefix = (data.get("prefix") or "").strip()
        if not prefix:
            payload, headers, status = err_json(400, "prefix 不能为空")
        else:
            try:
                payload, headers = ok_json(api_cleanup(prefix))
                status = 200
            except Exception as e:
                payload, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)
