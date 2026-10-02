"""统一环境变量与代理读取工具。

优先级：
1. 受保护键：系统环境变量（Vercel 云端 Environment Variables）优先，UI 不可覆盖
2. 用户配置（KV）：通过「设置」面板在线修改，存 Vercel KV，30 秒缓存
3. 系统环境变量（Vercel 云端使用 Environment Variables）
4. 项目根目录 .env 文件（本地运行使用，格式 KEY=VALUE）
5. .env.local 文件（本地覆盖，git 已忽略）

对外主要提供：
- env(name, default=None)：读取配置
- proxy()：返回爬虫代理地址（PROXY / HTTPS_PROXY / HTTP_PROXY）
- proxies()：返回 requests 可用的 proxies 字典
- user_config() / save_user_config()：KV 用户配置读写
"""
import json
import os
import sys
import time

_BASE = os.path.dirname(os.path.abspath(__file__))
_CACHE = None

# KV 中存放「设置」面板配置的键
KV_CONFIG_KEY = "config"
_KV_TTL = 30.0

# 这些键必须由平台环境变量决定，用户配置不可覆盖（否则可被改坏导致站点不可用）
PROTECTED_KEYS = frozenset(
    (
        "WANPA_PLUS_SECRET",
        "KV_REST_API_URL",
        "KV_REST_API_TOKEN",
        "VERCEL",
        "VERCEL_ENV",
        "NODE_ENV",
        "WANPA_MASTER_CODES",
    )
)

_KV_CACHE = {"data": None, "at": 0.0}
_KV_MOD = {}


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


def _kv_module():
    """惰性取 api/_kv（避免顶层导入造成 sys.path 相互污染）。"""
    mod = _KV_MOD.get("mod")
    if mod is not None:
        return mod
    try:
        api_dir = os.path.join(_BASE, "api")
        if api_dir not in sys.path:
            sys.path.insert(0, api_dir)
        import _kv  # noqa: WPS433

        _KV_MOD["mod"] = _kv
        return _kv
    except Exception:
        _KV_MOD["mod"] = False
        return None


def user_config():
    """返回 KV 里的用户配置 dict（KV 不可用时返回 {}）。"""
    kv = _kv_module()
    if not kv or not kv.available():
        return {}
    now = time.time()
    cached = _KV_CACHE["data"]
    if cached is not None and now - _KV_CACHE["at"] < _KV_TTL:
        return cached
    try:
        raw = kv.get(KV_CONFIG_KEY)
    except Exception:
        return cached or {}
    data = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = {}
    _KV_CACHE["data"] = data
    _KV_CACHE["at"] = now
    return data


def save_user_config(data):
    """把用户配置写入 KV 并刷新本地缓存。"""
    kv = _kv_module()
    if not kv:
        raise RuntimeError("KV 未配置，无法保存设置")
    payload = json.dumps(data or {}, ensure_ascii=False)
    kv.set(KV_CONFIG_KEY, payload)
    _KV_CACHE["data"] = data or {}
    _KV_CACHE["at"] = time.time()
    return True


def invalidate_config_cache():
    _KV_CACHE["data"] = None
    _KV_CACHE["at"] = 0.0


def env(name, default=None):
    v = _user_config_value(name) if name not in PROTECTED_KEYS else None
    if v:
        return v
    v = os.environ.get(name)
    if v is not None and v != "":
        return v
    return _load_dotenv_files().get(name, default)


def _user_config_value(name):
    data = _KV_CACHE["data"]
    if data is None:
        data = user_config()
    v = data.get(name)
    if v is None:
        return None
    v = str(v).strip()
    return v or None


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
