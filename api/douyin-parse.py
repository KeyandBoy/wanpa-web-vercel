import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from _core import classify_error, err_json, ok_json


def _attach_play_url(result):
    """给无水印视频直链附带签名的播放地址（图片集无需代理播放）。"""
    video_url = (result or {}).get("video_url") or ""
    if not video_url:
        return result
    from stream_sign import sign

    result["play_url"] = "/api/video-preview?url=%s&sig=%s" % (
        quote(video_url, safe=""),
        sign(video_url),
    )
    return result


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0].strip()
        if not url:
            body, headers, status = err_json(400, "url 参数不能为空")
        else:
            try:
                from douyin_svc import parse_douyin

                body, headers = ok_json(_attach_play_url(parse_douyin(url)))
                status = 200
            except Exception as e:
                body, headers, status = err_json(
                    400, str(e), error_type=classify_error(e)
                )
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
