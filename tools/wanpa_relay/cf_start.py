# -*- coding: utf-8 -*-
"""启动 cloudflared quick tunnel，把公网 URL 写入 tunnel_url.txt，保活。"""
import os
import re
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(BASE, "cloudflared.exe")
URL_F = os.path.join(BASE, "tunnel_url.txt")
OUT_F = os.path.join(BASE, "cloudflared.log")

# 真实 quick tunnel 是三段以上子域（adjective-noun-verb.trycloudflare.com）；
# api.trycloudflare.com 只有单段，必须排除，否则会把报错文案里的 API 端点当成隧道地址。
_URL_RE = re.compile(r"https://([a-z0-9]+-){2,}[a-z0-9]+\.trycloudflare\.com")


def _is_real_tunnel(url):
    return bool(url) and _URL_RE.fullmatch(url.rstrip("/"))


def main():
    # 已有隧道还活着就复用（必须是合法隧道地址，避免复用历史写坏的值）
    try:
        old = open(URL_F, encoding="utf-8").read().strip()
        if _is_real_tunnel(old):
            import urllib.request

            try:
                urllib.request.urlopen(old + "/", timeout=8)
                print("REUSE", old)
                return
            except Exception:
                pass
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/IM", "cloudflared.exe", "/F"],
            capture_output=True,
            timeout=15,
        )
        time.sleep(1)
    except Exception:
        pass
    # 只读本次启动之后追加的日志，避免读到历史残留的旧隧道地址
    try:
        start_size = os.path.getsize(OUT_F)
    except OSError:
        start_size = 0
    out = open(OUT_F, "ab")
    proc = subprocess.Popen(
        [EXE, "tunnel", "--url", "http://127.0.0.1:18082", "--no-autoupdate"],
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )
    url = None
    t0 = time.time()
    while time.time() - t0 < 45:
        try:
            with open(OUT_F, "rb") as f:
                f.seek(start_size)
                data = f.read().decode("utf-8", "replace")
        except Exception:
            data = ""
        m = _URL_RE.search(data)
        if m:
            url = m.group(0)
            break
        if proc.poll() is not None:
            break
        time.sleep(1)
    if not url:
        print("FAIL no url, exit=%s" % proc.poll())
        sys.exit(1)
    open(URL_F, "w", encoding="utf-8").write(url + "\n")
    print("URL", url)


if __name__ == "__main__":
    main()
