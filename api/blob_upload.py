import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import api_upload, err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        qs = parse_qs(urlparse(self.path).query)
        task_id = (qs.get("task_id") or [""])[0]
        seq = (qs.get("seq") or ["0"])[0]
        ext = (qs.get("ext") or ["jpg"])[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""
        if not task_id or not body:
            payload, headers, status = err_json(400, "task_id 和图片内容不能为空")
        else:
            try:
                payload, headers = ok_json(api_upload(task_id, seq, ext, body))
                status = 200
            except Exception as e:
                payload, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)
