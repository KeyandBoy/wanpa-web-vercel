import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import issue_codes
from _core import err_json, ok_json

_ADMIN_KEY = os.environ.get("WANPA_ADMIN_KEY") or ""


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b"{}"
            data = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            body, headers, status = err_json(400, "请求体解析失败")
            self._send(status, body, headers)
            return
        admin_key = (data.get("admin_key") or "").strip()
        try:
            count = max(1, min(int(data.get("count") or 1), 50))
        except ValueError:
            count = 1
        if not _ADMIN_KEY or not admin_key or admin_key != _ADMIN_KEY:
            body, headers, status = err_json(403, "无权操作（admin_key 错误）")
        else:
            codes = issue_codes(count)
            payload, headers = ok_json({"ok": True, "codes": codes, "count": len(codes)})
            status = 200
            body = payload
        self._send(status, body, headers)

    def _send(self, status, body, headers):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
