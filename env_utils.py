"""统一环境变量与代理读取工具。

优先级：
1. 系统环境变量（Vercel 云端使用 Environment Variables）
2. 项目根目录 .env 文件（本地运行使用，格式 KEY=VALUE）
3. .env.local 文件（本地覆盖，git 已忽略）

对外主要提供：
- env(name, default=None)：读取配置（env -> .env -> .env.local）
- proxy()：返回爬虫代理地址（PROXY / HTTPS_PROXY / HTTP_PROXY）
- proxies()：返回 requests 可用的 proxies 字典
"""
import os

_BASE = os.path.dirname(os.path.abspath(__file__))
_CACHE = None


def _load_dotenv_files():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    data = {}
    for fname in (".env", ".env.local"):
        try:
            path = os.path.join(_BASE, fname)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in data:
                        data[k] = v
        except OSError:
            continue
    _CACHE = data
    return _CACHE


def env(name, default=None):
    v = os.environ.get(name)
    if v is not None and v != "":
        return v
    return _load_dotenv_files().get(name, default)


def proxy():
    p = (
        env("PROXY")
        or os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    return p or None


def proxies():
    p = proxy()
    return {"http": p, "https": p} if p else None
