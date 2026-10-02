import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import err_json


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0].strip()
        sig = (qs.get("sig") or [""])[0].strip()
        if not url:
            self._fail(400, "url 参数不能为空")
            return

        from stream_sign import verify

        if not verify(url, sig):
            self._fail(403, "播放地址签名无效或已过期，请重新解析")
            return

        try:
            from url_guard import validate_public_url

            safe_url = validate_public_url(url)
            from video_svc import stream_hls_segment

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in stream_hls_segment(safe_url):
                self.wfile.write(chunk)
        except Exception as e:
            self._fail(500, "HLS 分片代理失败: %s" % e)

    def _fail(self, status, msg):
        body, headers, code = err_json(status, msg)
        try:
            self.send_response(code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass
