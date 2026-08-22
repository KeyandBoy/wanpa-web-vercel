import argparse
import importlib.util
import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
API = os.path.join(ROOT, "api")
PUBLIC = os.path.join(ROOT, "public")
sys.path.insert(0, API)
sys.path.insert(0, ROOT)

ROUTES = {
    "search": "search",
    "page-images": "page_images",
    "proxy": "proxy",
    "blob-upload": "blob_upload",
    "blob-cleanup": "blob_cleanup",
    "novel-search": "novel-search",
    "novel-content": "novel-content",
    "novel-chapters": "novel-chapters",
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
}

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}

_cache = {}


def _load(modname):
    if modname in _cache:
        return _cache[modname]
    path = os.path.join(API, modname + ".py")
    spec = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[modname] = m
    spec.loader.exec_module(m)
    _cache[modname] = m
    return m


class Router(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, status, body, headers):
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _route_api(self):
        parts = [p for p in self.path.split("?")[0].strip("/").split("/") if p]
        name = parts[1] if len(parts) >= 2 and parts[0] == "api" else ""
        return ROUTES.get(name)

    def _handle(self):
        path = self.path.split("?")[0]
        if path == "/api/health":
            self._send(200, b'{"ok":true}', {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "11",
            })
            return
        modname = self._route_api()
        if modname:
            try:
                h = _load(modname).handler
                inst = h.__new__(h)
                inst.__dict__.update(self.__dict__)
                inst.requestline = self.requestline
                inst.request_version = self.request_version
                inst.command = self.command
                if self.command == "GET":
                    inst.do_GET()
                else:
                    inst.do_POST()
            except Exception:
                tb = traceback.format_exc()
                print(tb, file=sys.stderr)
                try:
                    self._send(500, tb.encode("utf-8"),
                               {"Content-Type": "text/plain; charset=utf-8",
                                "Content-Length": str(len(tb.encode("utf-8")))})
                except Exception:
                    pass
            return
        self._serve_static(path)

    def _serve_static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        fp = os.path.join(PUBLIC, path.lstrip("/"))
        if not os.path.isfile(fp):
            fp = os.path.join(PUBLIC, "index.html")
        ext = os.path.splitext(fp)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        try:
            with open(fp, "rb") as f:
                body = f.read()
        except Exception:
            self._send(404, b"not found", {"Content-Type": "text/plain", "Content-Length": "9"})
            return
        self._send(200, body, {"Content-Type": ctype, "Content-Length": str(len(body))})

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=7732)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Router)
    print(f"Server ready at http://127.0.0.1:{args.port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
