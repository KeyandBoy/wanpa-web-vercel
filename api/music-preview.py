import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import err_json


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
            import music_svc
            range_header = self.headers.get("Range")
            status_code, resp_headers, chunks = music_svc.stream_music(url, range_header)
            self.send_response(status_code)
            for k, v in resp_headers.items():
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in chunks:
                self.wfile.write(chunk)
        except Exception as e:
            body, headers, status = err_json(500, f"预览代理失败: {e}")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
