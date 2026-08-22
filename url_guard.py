"""Remote URL validation for proxy requests."""

import ipaddress
import socket
from urllib.parse import urlparse


def validate_public_url(url):
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError("仅支持 HTTP/HTTPS 下载地址")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("下载地址格式不合法")
    if parsed.port and parsed.port not in (80, 443):
        raise ValueError("下载地址使用了非标准端口")
    try:
        records = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise ValueError("下载域名无法解析") from exc
    if not records:
        raise ValueError("下载域名没有可用地址")
    for record in records:
        address = record[4][0].split("%", 1)[0]
        ip = ipaddress.ip_address(address)
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            raise ValueError("拒绝访问本机、局域网或保留地址")
    return parsed.geturl()
