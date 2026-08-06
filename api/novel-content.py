import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _auth import check_token
from _core import err_json, ok_json
from _novel_core import get_novel_content, is_plus_novel_url


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        url = (qs.get("url") or [""])[0]
        translate = (qs.get("translate") or ["0"])[0] in ("1", "true", "yes")
        token = (qs.get("token") or [""])[0].strip()
        is_plus = is_plus_novel_url(url)
        if not url:
            body, headers, status = err_json(400, "url 不能为空")
        elif is_plus and not check_token(token):
            body, headers, status = err_json(403, "该小说源为 Plus 专属功能，请先激活 Plus 版本")
        else:
            try:
                content = get_novel_content(url, translate)
                payload, headers = ok_json({"content": content})
                status = 200
                body = payload
            except Exception as e:
                body, headers, status = err_json(500, str(e))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)
