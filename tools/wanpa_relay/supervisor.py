# -*- coding: utf-8 -*-
r"""成人源中转看护进程（cloudflared 版）。

职责（循环执行）：
1. relay.py 不在则拉起（127.0.0.1:18082，Basic 认证 + /fetch 取回 API）
2. cloudflared quick tunnel 不在/失联则由 cf_start.py 拉起，URL 写 tunnel_url.txt
3. URL 变化时：更新 Vercel 环境变量 ADULT_RELAY（= 隧道URL/<secret>）并触发重新部署
   （quick tunnel 随机域名，重启会变；每日部署有上限）
4. 探测失败连续 2 次 -> 杀掉 cloudflared 重建

只打印打码后的地址（不含路径密钥）。日志：C:\wanpa_relay\supervisor.log
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
REPO = r"E:\computerProgram2\wanpaweb vercel版"
CREDS = json.load(open(os.path.join(BASE, "creds.json"), encoding="utf-8"))
STATE_F = os.path.join(BASE, "state.json")
URL_F = os.path.join(BASE, "tunnel_url.txt")
LOG = os.path.join(BASE, "supervisor.log")
RELAY_PORT = 18082
CLASH_PORT = 7897
MAX_DEPLOY_PER_DAY = 3
NO_VERCEL = "--no-vercel" in sys.argv


# 真实 quick tunnel 是三段以上子域；api.trycloudflare.com 只有单段，必须排除
_TUNNEL_RE = re.compile(r"https://([a-z0-9]+-){2,}[a-z0-9]+\.trycloudflare\.com")


def log(msg, tag=""):
    line = time.strftime("%m-%d %H:%M:%S ") + msg
    try:
        print(line, flush=True)
    except Exception:
        pass  # pythonw 下无控制台
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    if tag:
        _LOG_THROTTLE[tag] = (msg, time.time())


# 同一条日志（如「每日已达上限」）在静默期内不重复写，避免日志被刷爆
_LOG_THROTTLE = {}
_SILENCE = 600


def log_once(msg, tag):
    """同一 tag 的相同内容在 _SILENCE 秒内只写一次。"""
    prev = _LOG_THROTTLE.get(tag)
    now = time.time()
    if prev and prev[0] == msg and now - prev[1] < _SILENCE:
        return
    log(msg, tag)


def load_state():
    try:
        return json.load(open(STATE_F, encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    json.dump(st, open(STATE_F, "w", encoding="utf-8"))


def masked(url):
    return re.sub(r"(//|/)[0-9A-Za-z_-]{8,}", r"\1****", url)


def relay_value():
    """ADULT_RELAY 环境变量完整值：隧道URL + 路径密钥。"""
    try:
        tun = open(URL_F, encoding="utf-8").read().strip()
    except Exception:
        return None
    if not _TUNNEL_RE.fullmatch(tun.rstrip("/")):
        return None  # 非法/被写坏的地址一律视为无效
    return tun + "/" + CREDS["path"]


def port_open(host, port):
    import socket

    try:
        s = socket.create_connection((host, port), timeout=3)
        s.close()
        return True
    except Exception:
        return False


def ensure_relay():
    if port_open("127.0.0.1", RELAY_PORT):
        return
    log("relay 未运行，拉起 relay.py")
    subprocess.Popen(
        [sys.executable, "-X", "utf8", os.path.join(BASE, "relay.py")],
        cwd=BASE,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)


def _probe_once(tun):
    import urllib.error
    import urllib.parse
    import urllib.request

    base = (tun or "").rstrip("/")
    if not _TUNNEL_RE.fullmatch(base):
        return False
    probe = (
        base
        + "/"
        + CREDS["path"]
        + "/fetch?u="
        + urllib.parse.quote("http://probe.invalid/", safe="")
    )
    try:
        with urllib.request.urlopen(probe, timeout=8) as r:
            code, body = r.status, r.read(256)
    except urllib.error.HTTPError as e:
        code, body = e.code, (e.read(256) if e.fp else b"")
    except Exception:
        return False
    return code == 403 and b"host not allowed" in body


def probe_tunnel(tun, retries=3):
    """探测隧道是否真的通到本机 relay（决定性指纹，不是"随便有响应"）。

    请求白名单外的域名，我们的 relay 会回 403「host not allowed」——
    这是 relay 特有响应；404（如 api.trycloudflare.com）、502（relay 不通）、
    连接失败都判为不通。

    cloudflared 打印出 URL 后隧道要几秒才真正可用，所以连续重试几次。
    """
    for i in range(max(retries, 1)):
        if _probe_once(tun):
            return True
        if i < retries - 1:
            time.sleep(4)
    return False


def ensure_tunnel():
    val = relay_value()
    # 旧隧道要么活着要么已死，单次探测即可；失败就尽快换新的
    if val and probe_tunnel(val.rsplit("/", 1)[0], retries=1):
        return val
    log("启动 cloudflared 隧道 ...")
    try:
        r = subprocess.run(
            [sys.executable, "-X", "utf8", os.path.join(BASE, "cf_start.py")],
            cwd=BASE, capture_output=True, timeout=60,
        )
        out = (r.stdout or b"").decode("utf-8", "replace").strip()
        if "FAIL" in out or r.returncode != 0:
            log("cf_start 失败: %s" % (out or r.stderr.decode("utf-8", "replace")[:200]))
            return None
    except Exception as e:
        log("cf_start 异常: %r" % e)
        return None
    val = relay_value()
    if val:
        log("隧道就绪 %s" % masked(val))
    return val


def vercel_env_update(url):
    vercel = shutil.which("vercel") or "vercel"
    try:
        subprocess.run(
            [vercel, "env", "rm", "ADULT_RELAY", "production", "-y"],
            cwd=REPO, input=b"", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=60,
        )
    except Exception as e:
        log("env rm: %r" % e)
    try:
        r = subprocess.run(
            [vercel, "env", "add", "ADULT_RELAY", "production"],
            cwd=REPO, input=url.encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=90,
        )
        ok = r.returncode == 0
        log("env add: %s" % ("OK" if ok else ("FAIL " + r.stdout.decode("utf-8", "replace")[:160])))
        return ok
    except Exception as e:
        log("env add 异常: %r" % e)
        return False


def trigger_redeploy():
    try:
        r = subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "ops: ADULT_RELAY cloudflared"],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
        )
        if r.returncode != 0:
            log("commit FAIL: %s" % r.stdout.decode("utf-8", "replace")[:160])
            return False
        r = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
        )
        if r.returncode != 0:
            log("push FAIL: %s" % r.stdout.decode("utf-8", "replace")[:160])
            return False
        log("redeploy 已触发")
        return True
    except Exception as e:
        log("redeploy 异常: %r" % e)
        return False


def sync_env(url):
    st = load_state()
    today = date.today().isoformat()
    if st.get("url") == url:
        return
    if NO_VERCEL:
        st["url"] = url
        save_state(st)
        log("NO-VERCEL 模式，仅记录 %s" % masked(url))
        return
    if st.get("date") != today:
        st["date"] = today
        st["deploys"] = 0
    if int(st.get("deploys") or 0) >= MAX_DEPLOY_PER_DAY:
        log_once(
            "今日部署已达上限(%d)，跳过；%s" % (MAX_DEPLOY_PER_DAY, masked(url)),
            "deploy_cap",
        )
        return
    log("地址变化 -> 更新 Vercel: %s" % masked(url))
    if not vercel_env_update(url):
        return
    if trigger_redeploy():
        st = load_state()
        st["url"] = url
        st["date"] = today
        st["deploys"] = int(st.get("deploys") or 0) + 1
        save_state(st)
        log("状态已保存")


def kill_cloudflared():
    try:
        subprocess.run(
            ["taskkill", "/IM", "cloudflared.exe", "/F"],
            capture_output=True, timeout=15,
        )
    except Exception:
        pass


def _backoff(unhealthy):
    """指数退避：30→60→120→240→300 秒封顶。
    没有退避会每 15 秒反复重启 cloudflared，触发 trycloudflare 的 429 限流。"""
    return min(30 * (2 ** max(unhealthy - 1, 0)), 300)


def main():
    log("supervisor 启动 (no_vercel=%s)" % NO_VERCEL)
    fails = 0
    unhealthy = 0
    while True:
        try:
            ensure_relay()
            if not port_open("127.0.0.1", CLASH_PORT):
                log_once("clash(7897) 不在线（中转请求会失败，隧道照常保持）", "clash")
            url = ensure_tunnel()
            if url and probe_tunnel(url.rsplit("/", 1)[0]):
                if unhealthy:
                    log("隧道已恢复")
                unhealthy = 0
                fails = 0
                sync_env(url)
                time.sleep(15)
                continue
            unhealthy += 1
            if url:
                fails += 1
                log("隧道探测失败 %d" % fails)
                if fails >= 2:
                    kill_cloudflared()
                    fails = 0
            delay = _backoff(unhealthy)
            log_once("隧道未就绪，退避 %d 秒后重试" % delay, "backoff")
            time.sleep(delay)
        except KeyboardInterrupt:
            log("退出")
            break
        except Exception as e:
            log("循环异常: %r" % e)
            unhealthy += 1
            time.sleep(_backoff(unhealthy))


if __name__ == "__main__":
    main()
