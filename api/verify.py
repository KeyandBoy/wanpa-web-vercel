import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import verify_code
from _core import err_json, ok_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        code = (qs.get("code") or [""])[0].strip()
        if not code:
            body, headers, status = err_json(400, "激活码不能为空")
        else:
            token = verify_code(code)
            if token is None:
                body, headers, status = err_json(404, "激活码无效，请检查后重试")
            else:
                payload, headers = ok_json({"ok": True, "token": token, "code": code.upper()})
                status = 200
                body = payload
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
