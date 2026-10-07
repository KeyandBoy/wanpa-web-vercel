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


def main():
    try:
        old = open(URL_F, encoding="utf-8").read().strip()
        if old and "trycloudflare.com" in old:
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
    out = open(OUT_F, "ab")
    proc = subprocess.Popen(
        [EXE, "tunnel", "--url", "http://127.0.0.1:18082", "--no-autoupdate"],
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )
    url = None
    t0 = time.time()
    while time.time() - t0 < 30:
        try:
            data = open(OUT_F, "rb").read()[-4000:].decode("utf-8", "replace")
        except Exception:
            data = ""
        m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", data)
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
