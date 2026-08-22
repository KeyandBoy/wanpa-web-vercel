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
        filename = (qs.get("filename") or [""])[0].strip() or "download"
        fmt = (qs.get("format") or [""])[0].strip().lower()
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
            resp = _requests.get(safe_url, timeout=(10, 120), stream=True)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            content_length = resp.headers.get("Content-Length", "")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if content_length:
                self.send_header("Content-Length", content_length)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in resp.iter_content(1 << 16):
                if chunk:
                    self.wfile.write(chunk)
        except Exception as e:
            body, headers, status = err_json(500, f"下载失败: {e}")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
