"""视频流式接口的短期 HMAC 签名。

为什么需要：`/api/video-preview`、`/api/hls-playlist`、`/api/hls-seg` 都是
「带 url 参数的开放代理」，Vercel 公网上会被人当免费代理白嫖流量。签名要求
这些 URL 必须先经过 `/api/video-resolve` 拿到，签名本身自包含过期时间点，
无需服务端存储（serverless 无共享内存）。

签名是「证明 URL 走过本应用」，不区分用户等级——Lite 用户照样能播免费源，
差别只在搜索/解析阶段的 Plus 门禁（见 api/_auth.py 的 is_plus_video_source）。
"""

import hashlib
import hmac
import os
import time

_SECRET = (os.environ.get("WANPA_PLUS_SECRET") or "wanpa-plus-default-secret").encode()
_TTL = 900  # 15 分钟


def _mac(url, expire_at):
    msg = ("%d:%s" % (expire_at, url)).encode("utf-8")
    return hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()[:32]


def sign(url):
    """生成签名，格式 `expireAt.hmac`（前 32 位）。"""
    expire_at = int(time.time()) + _TTL
    return "%d.%s" % (expire_at, _mac(url, expire_at))


def verify(url, sig):
    """校验签名：格式正确、未过期、HMAC 匹配。"""
    if not url or not sig or "." not in sig:
        return False
    ts_s, _, mac = str(sig).partition(".")
    try:
        expire_at = int(ts_s)
    except ValueError:
        return False
    if expire_at < int(time.time()):
        return False
    return hmac.compare_digest(mac, _mac(url, expire_at))


def attach(url, sig=None):
    """把签名拼到代理路径后面：`/api/xxx?url=<quoted>&sig=<expireAt.hmac>`。"""
    from urllib.parse import quote

    return "%s?%s" % (quote(url, safe=""), "sig=" + (sig or sign(url)))
