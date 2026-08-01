import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _core import err_json, ok_json
from _ds_core import clean_content


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            body, headers, status = err_json(400, "请求体无效")
        else:
            text = (body.get("text") or "").strip()
            if not text:
                body, headers, status = err_json(400, "text 不能为空")
            else:
                try:
                    payload, headers = ok_json({"text": clean_content(text)})
                    status = 200
                    body = payload
                except Exception as e:
                    body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
