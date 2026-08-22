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
        url = (qs.get("url") or [""])[0].strip()
        if not url:
            body, headers, status = err_json(400, "url 参数不能为空")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            import requests as _requests
            from url_guard import validate_public_url
            safe_url = validate_public_url(url)
            range_header = self.headers.get("Range")
            req_headers = {"User-Agent": "WanpaWeb-Proxy/1.0", "Accept": "*/*"}
            if range_header:
                req_headers["Range"] = range_header
            resp = _requests.get(safe_url, headers=req_headers, timeout=(15, 120), stream=True)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            self.send_response(resp.status_code)
            for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                val = resp.headers.get(name)
                if val:
                    self.send_header(name, val)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in resp.iter_content(1 << 16):
                if chunk:
                    self.wfile.write(chunk)
        except Exception as e:
            body, headers, status = err_json(500, f"代理请求失败: {e}")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
