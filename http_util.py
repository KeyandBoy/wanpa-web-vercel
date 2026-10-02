"""轻量 HTTP GET 工具，替代 GetPhoto 的 `main.http_get` / `main.HEADERS`。

GetPhoto 把这些放在 `main.py`（本地服务入口），绿色版没有 `main` 模块，
所以独立成文件。行为对齐原实现：国内站 `trust_env=False`（不吃系统代理），
带重试与 `raise_for_status`。原版的「镜像域名」逻辑依赖 GetPhoto 本地的
镜像表文件，绿色版没有，故略去，只保留重试。
"""

import time

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_DOMESTIC_SUFFIXES = (
    ".cn",
    ".com.cn",
    ".net.cn",
    ".org.cn",
    ".gov.cn",
    ".edu.cn",
    ".ac.cn",
)
_DOMESTIC_HOSTS = (
    "bilibili.com",
    "bilivideo.com",
    "hdslb.com",
    "baidu.com",
    "qq.com",
    "iqiyi.com",
    "youku.com",
    "acfun.cn",
    "mgtv.com",
    "douyin.com",
    "douyinvod.com",
    "kuleu.com",
    "kuaishou.com",
    "weibo.com",
    "sina.com.cn",
    "taobao.com",
    "tmall.com",
    "aliyun.com",
    "alicdn.com",
    "jd.com",
    "163.com",
    "126.com",
    "sohu.com",
    "sogou.com",
    "360.cn",
    "zhihu.com",
    "bilibili.tv",
)


def _host_of(url):
    try:
        return url.split("/")[2].lower().split(":")[0]
    except (IndexError, ValueError):
        return ""


def is_domestic(url):
    host = _host_of(url)
    if not host:
        return False
    if host in _DOMESTIC_HOSTS:
        return True
    return any(host.endswith(s) for s in _DOMESTIC_SUFFIXES) or ".cn" in host


def http_get(url, params=None, timeout=20, retries=3, session=None, verify=True, headers=None):
    if is_domestic(url):
        if session is None:
            session = requests.Session()
        session.trust_env = False

    last = None
    for i in range(max(1, int(retries or 1))):
        try:
            client = session if session is not None else requests
            r = client.get(
                url,
                headers=headers or HEADERS,
                params=params,
                timeout=timeout,
                verify=verify,
            )
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            if i + 1 < retries:
                time.sleep(1.5 * (i + 1))
    raise last
