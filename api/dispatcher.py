"""统一入口分发器（Vercel 单入口后端框架模式）。

Vercel 将本项目按“单入口”Python 函数构建，所有 /api/* 请求都会落到
本文件的 handler 上。这里按路径分发给 api/ 下各端点模块的 handler 类，
等价于每个端点独立运行的效果。
"""

import importlib.util
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

_API = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _API)

ROUTES = {
    "search": "search",
    "page-images": "page_images",
    "proxy": "proxy",
    "blob-upload": "blob_upload",
    "blob-cleanup": "blob_cleanup",
    "novel-search": "novel-search",
    "novel-content": "novel-content",
    "novel-chapters": "novel-chapters",
    "novel-categories": "novel-categories",
    "novel-category": "novel-category",
    "comic-search": "comic-search",
    "comic-pages": "comic-pages",
    "verify": "verify",
    "issue-code": "issue-code",
    "ds-summarize": "ds-summarize",
    "ds-filter": "ds-filter",
    "ds-clean": "ds-clean",
    "music-sources": "music-sources",
    "music-search": "music-search",
    "music-preview": "music-preview",
    "music-download": "music-download",
    "book-sources": "book-sources",
    "book-search": "book-search",
    "book-download": "book-download",
    "file-proxy": "file-proxy",
    # 视频：搜索 / 解析 / 播放（Tier1，无下载转码）
    "video-search": "video-search",
    "video-resolve": "video-resolve",
    "video-preview": "video-preview",
    "hls-playlist": "hls-playlist",
    "hls-seg": "hls-seg",
    "douyin-parse": "douyin-parse",
}

_loaded = {}


def _load(modname):
    if modname in _loaded:
        return _loaded[modname]
    path = os.path.join(_API, modname + ".py")
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[modname] = m
    spec.loader.exec_module(m)
    _loaded[modname] = m
    return m


class _HeadSink:
    """HEAD 兜底用的假 wfile：把 do_GET 的输出全接住，最后只回放头部。"""

    def __init__(self):
        self.buf = bytearray()

    def write(self, b):
        self.buf.extend(b)

    def flush(self):
        pass


class handler(BaseHTTPRequestHandler):
    def _dispatch(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        parts = [p for p in path.strip("/").split("/") if p]
        name = parts[1] if len(parts) >= 2 and parts[0] == "api" else ""
        modname = ROUTES.get(name)
        if not modname:
            body = b'{"error":"not found"}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        try:
            h = _load(modname).handler
            inst = h.__new__(h)
            inst.__dict__.update(self.__dict__)
            inst.requestline = self.requestline
            inst.request_version = self.request_version
            inst.command = self.command
            if self.command == "HEAD":
                self._head_dispatch(inst)
            elif self.command == "GET":
                inst.do_GET()
            else:
                inst.do_POST()
        except Exception:
            tb = traceback.format_exc()
            print(tb, file=sys.stderr)
            try:
                body = tb.encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
            except Exception:
                pass

    def _head_dispatch(self, inst):
        """Vercel 单入口下 HEAD 的分发：子模块有 do_HEAD 就用它的，
        没有就跑一次 do_GET、把输出掐在头部回放（Content-Length 照常给出）。"""
        if hasattr(inst, "do_HEAD"):
            inst.do_HEAD()
            return
        sink = _HeadSink()
        inst.wfile = sink
        inst.do_GET()
        data = bytes(sink.buf)
        head = data.split(b"\r\n\r\n", 1)[0]
        self.wfile.write(head + b"\r\n\r\n")

    def do_GET(self):
        self._dispatch()

    def do_HEAD(self):
        self._dispatch()

    def do_POST(self):
        self._dispatch()

    def log_message(self, *a):
        pass
