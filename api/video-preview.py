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

        # 签名校验：播放类接口是开放代理，未签名的请求一律拒绝
        from stream_sign import sign, verify

        if not verify(url, sig):
            self._fail(403, "播放地址签名无效或已过期，请重新解析")
            return

        try:
            from url_guard import validate_public_url
            from video_svc import stream_direct

            safe_url = validate_public_url(url)
            # stream_direct 会按目标站补齐 UA/Referer/代理，B 站等 CDN 缺 Referer 会 403
            status, up_headers, chunks = stream_direct(
                safe_url, self.headers.get("Range")
            )

            self.send_response(status)
            for k, v in up_headers.items():
                self.send_header(k, v)
            if not up_headers.get("Accept-Ranges"):
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("X-Upstream-Status", str(status))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            for chunk in chunks:
                if chunk:
                    self.wfile.write(chunk)
        except Exception as e:
            self._fail(502, "视频代理失败: %s" % e)

    def do_HEAD(self):
        """播放器/CDN 探测用：校验签名后只回响应头，不写正文（缺这个会回 501）。"""
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0].strip()
        sig = (qs.get("sig") or [""])[0].strip()
        if not url:
            self._head_fail(400, "url 参数不能为空")
            return

        from stream_sign import verify

        if not verify(url, sig):
            self._head_fail(403, "播放地址签名无效或已过期，请重新解析")
            return

        try:
            from url_guard import validate_public_url
            from video_svc import stream_direct

            safe_url = validate_public_url(url)
            # 只取 range 首字节的响应头，够拿到 Content-Type/Content-Range，不下载正文
            status, up_headers, chunks = stream_direct(safe_url, "bytes=0-0")
            self.send_response(status)
            for k, v in up_headers.items():
                if k.lower() == "content-length":
                    continue
                self.send_header(k, v)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("X-Upstream-Status", str(status))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            close = getattr(chunks, "close", None)
            if close:
                close()
        except Exception:
            self._head_fail(502, "视频代理失败")

    def _head_fail(self, status, msg):
        _, headers, code = err_json(status, msg)
        try:
            self.send_response(code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
        except Exception:
            pass

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
