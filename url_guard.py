"""Remote URL validation for proxy requests."""

import ipaddress
import socket
from urllib.parse import urlparse

# 端口策略：允许任意端口。
# 视频/图片 CDN 经常使用非标准端口（8443、18080 等），若限定 80/443 会让大量
# 分片代理直接 502。安全兜底由下面的 IP 校验负责——拒绝私网/回环/链路本地/
# 多播/保留/未指定地址，因此放开端口不会引入指向内网的 SSRF。
#
# 调用方仍应叠加业务级校验（例如视频接口的 HMAC 签名），防止被当成免费代理白嫖流量。


def validate_public_url(url):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 HTTP/HTTPS 下载地址")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("下载地址格式不合法")
    try:
        records = socket.getaddrinfo(
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
        )
    except (socket.gaierror, ValueError) as exc:
        raise ValueError("下载域名无法解析") from exc
    if not records:
        raise ValueError("下载域名没有可用地址")
    for record in records:
        address = record[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise ValueError("下载域名解析结果不合法")
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        ):
            raise ValueError("拒绝访问本机、局域网或保留地址")
    return parsed.geturl()
