# -*- coding: utf-8 -*-
"""成人源中转（双协议）。

- 正向代理（CONNECT / 绝对URI）：仅 127.0.0.1:18082，Basic 认证，供本机/serveo 用
- HTTP 取回 API：GET /<secret>/fetch?u=<urlencoded>，经 cloudflared 隧道暴露给 Vercel
  兜底抓取成人源（Vercel IP 被源站封，本机出口走 clash）
- 白名单与 wanpaweb main_engine._ADULT_HOST_SUFFIXES 一致，上游固定 clash 7897
"""
import base64
import hmac
import json
import os
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

BASE = os.path.dirname(os.path.abspath(__file__))
CREDS = json.load(open(os.path.join(BASE, "creds.json"), encoding="utf-8"))
LISTEN = ("127.0.0.1", 18082)
UPSTREAM = ("127.0.0.1", 7897)
ALLOW = (
    "pornhub.com", "phncdn.com", "pornpics.com", "photos18.com",
    "asiantolick.com", "knit.bid", "foamgirl.net", "xiurenai.com", "afxfl.com",
    "meitulu.me", "xsnvshen.com", "xsnvshen.co", "anime-pictures.net",
    "pixiv.net", "pximg.net", "qvujkzrd.cc", "hhe62.com", "xhamster.com",
    "wnacg.com", "wnacg.org", "177picyy.com", "ho5ho.com", "caitlin.top",
    "rokuhentai.com", "h-webtoon.com", "cartoon18.com", "xhentai888.xyz",
    "sexacg.xyz", "hentaiclap.com", "hentairun.com", "allporncomic.com",
    "8muses.io", "ilikecomix.com",
)
LOG = os.path.join(BASE, "relay.log")
_lock = threading.Lock()


def _log(msg):
    with _lock:
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(time.strftime("%m-%d %H:%M:%S ") + msg + "\n")
        except Exception:
            pass


def _host_ok(host):
    host = (host or "").lower().split(":")[0].strip(".")
    return any(host == s or host.endswith("." + s) for s in ALLOW)


def _auth_ok(header):
    exp = "Basic " + base64.b64encode(
        ("%s:%s" % (CREDS.get("user", ""), CREDS.get("pass", ""))).encode()
    ).decode()
    return hmac.compare_digest(header or "", exp)


def _upstream_connect():
    s = socket.create_connection(UPSTREAM, timeout=20)
    s.settimeout(60)
    return s


def _pump(a, b, label="?"):
    try:
        first = True
        while True:
            d = a.recv(65536)
            if not d:
                _log("pump[%s] EOF" % label)
                break
            if first:
                _log("pump[%s] first %d bytes %r" % (label, len(d), d[:40]))
                first = False
            b.sendall(d)
    except Exception as e:
        _log("pump[%s] ERR %r" % (label, e))
    finally:
        try:
            b.shutdown(socket.SHUT_WR)
        except Exception:
            pass


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 60

    def log_message(self, fmt, *args):
        pass

    def _deny(self, code, msg):
        body = msg.encode("utf-8", "replace")
        try:
            self.send_response(code)
            if code == 407:
                self.send_header("Proxy-Authenticate", 'Basic realm="wanpa"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def _check(self, host):
        if not _auth_ok(self.headers.get("Proxy-Authorization", "")):
            self._deny(407, "proxy auth required")
            return False
        if not _host_ok(host):
            self._deny(403, "host not allowed")
            _log("403 %s" % host)
            return False
        return True

    def do_CONNECT(self):
        hostport = self.path
        host = hostport.split(":")[0]
        if not self._check(host):
            return
        try:
            up = _upstream_connect()
            up.sendall(
                ("CONNECT %s HTTP/1.1\r\nHost: %s\r\n\r\n" % (hostport, hostport)).encode()
            )
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = up.recv(4096)
                if not chunk:
                    break
                resp += chunk
            status = resp.split(b"\r\n", 1)[0]
            if b" 200 " not in status:
                self._deny(502, "upstream refused: " + status.decode("latin-1", "replace"))
                up.close()
                _log("CONNECT fail %s %s" % (host, status[:60]))
                return
            self.connection.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            _log("CONNECT ok %s (200 sent)" % host)
        except Exception as e:
            self._deny(502, "upstream error: %r" % e)
            _log("CONNECT err %s %r" % (host, e))
            return
        self._tunnel(self.connection, up)

    def _forward(self, method):
        try:
            parsed = self.path
            if not parsed.startswith("http"):
                host = self.headers.get("Host", "")
            else:
                host = parsed.split("/")[2]
        except Exception:
            host = ""
        if not self._check(host.split(":")[0]):
            return
        try:
            up = _upstream_connect()
            n = int(self.headers.get("Content-Length", "0") or "0")
            req = ("%s %s HTTP/1.1\r\n" % (method, self.path)).encode("latin-1")
            skip = {"proxy-authorization", "proxy-connection", "connection", "keep-alive"}
            for k, v in self.headers.items():
                if k.lower() in skip:
                    continue
                req += ("%s: %s\r\n" % (k, v)).encode("latin-1")
            req += b"Connection: close\r\n\r\n"
            up.sendall(req)
            if n:
                remain = n
                while remain:
                    d = self.rfile.read(min(65536, remain))
                    if not d:
                        break
                    up.sendall(d)
                    remain -= len(d)
            # 回程：强制 Connection:close 上游，直接泵到 EOF
            down = self.connection
            self.close_connection = True
            _pump(up, down, "u2c-fwd")
            up.close()
            _log("%s %s" % (method, host))
        except Exception as e:
            _log("%s err %s %r" % (method, host, e))
            try:
                self._deny(502, "relay error")
            except Exception:
                pass

    def _fetch_api(self):
        """GET /<secret>/fetch?u=<abs-url> 由 Vercel 侧 ADULT_RELAY 调用。"""
        m = re.match(r"^/([^/]+)/fetch(?:\?(.*))?$", self.path, re.S)
        secret = m.group(1) if m else ""
        query = (m.group(2) or "") if m else ""
        path_secret = CREDS.get("path", "")
        if not path_secret or not hmac.compare_digest(secret, path_secret):
            self._deny(403, "bad relay token")
            return
        target = (parse_qs(query).get("u") or [""])[0]
        if not target.startswith(("http://", "https://")):
            self._deny(400, "missing u")
            return
        try:
            host = target.split("/")[2].split(":")[0]
        except IndexError:
            self._deny(400, "bad u")
            return
        if not _host_ok(host):
            self._deny(403, "host not allowed")
            _log("fetch403 %s" % host)
            return
        fwd = {}
        for k in ("User-Agent", "Accept", "Accept-Language", "Referer", "Cookie", "Range"):
            v = self.headers.get(k)
            if v:
                fwd[k] = v
        try:
            import requests as rq

            r = rq.get(
                target,
                headers=fwd,
                timeout=(10, 35),
                allow_redirects=True,
                proxies={"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"},
                stream=True,
            )
            ctype = r.headers.get("Content-Type", "application/octet-stream")
            body = bytearray()
            over = False
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) > 30 * 1024 * 1024:
                    over = True
                    break
            r.close()
            if over:
                _log("fetch too large %s" % host)
                self._deny(502, "response too large")
                return
            furl = r.url if r.url.isascii() else quote(r.url, safe=":/?&=%")
            try:
                self.send_response(r.status_code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Final-Url", furl)
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(bytes(body))
                _log("fetch %s %d %d" % (host, r.status_code, len(body)))
            except Exception as e:
                _log("fetch send err %s %r" % (host, e))
        except Exception as e:
            _log("fetch err %s %r" % (host, e))
            try:
                self._deny(502, "upstream: %r" % e)
            except Exception:
                pass

    def do_GET(self):
        if re.match(r"^/[^/]+/fetch(?:\?|$)", self.path):
            self._fetch_api()
            return
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_HEAD(self):
        self._forward("HEAD")

    def do_PUT(self):
        self._forward("PUT")

    def do_DELETE(self):
        self._forward("DELETE")

    def do_OPTIONS(self):
        self._forward("OPTIONS")

    def _tunnel(self, a, b):
        t = threading.Thread(target=_pump, args=(a, b, "c2u"), daemon=True)
        t.start()
        _pump(b, a, "u2c")
        t.join(timeout=5)
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass


def main():
    srv = ThreadingHTTPServer(LISTEN, ProxyHandler)
    srv.daemon_threads = True
    _log("relay listen %s:%d -> upstream %s:%d" % (LISTEN[0], LISTEN[1], UPSTREAM[0], UPSTREAM[1]))
    srv.serve_forever()


if __name__ == "__main__":
    main()
