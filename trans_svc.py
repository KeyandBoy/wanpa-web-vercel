import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

_cache = {}
_lock = threading.Lock()

LATIN = re.compile(r"[A-Za-z]{3,}")
CN = re.compile(r"[\u4e00-\u9fff]")
JP = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]")


def _proxy():
    try:
        from env_utils import proxy as _p

        return _p()
    except Exception:
        return None


def has_chinese(text):
    return bool(CN.search(text or ""))


def needs_translate(text):
    """标题翻译判定：英文为主、或含日文假名的标题需要翻成中文"""
    if not text:
        return False
    if JP.search(text):
        return True
    cn_chars = len(CN.findall(text))
    if cn_chars / max(len(text), 1) > 0.3:
        return False
    return bool(LATIN.search(text))


def _one(text, target):
    with _lock:
        if (text, target) in _cache:
            return _cache[(text, target)]
    out = text
    for attempt in range(3):
        try:
            proxies = None
            p = _proxy()
            if p:
                proxies = {"http": p, "https": p}
            # 含日文假名的文本强制以日语为源语言，否则 auto 会因汉字多而误判为中文
            sl = "ja" if (target == "zh-CN" and JP.search(text)) else "auto"
            r = requests.get(
                "https://translate.googleapis.com/translate_a/single",
                params={"client": "gtx", "sl": sl, "tl": target, "dt": "t", "q": text},
                timeout=15,
                proxies=proxies,
            )
            r.raise_for_status()
            parts = r.json()[0]
            joined = "".join(x[0] for x in parts if x and x[0]).strip()
            if joined:
                out = joined
                break
        except Exception:
            time.sleep(0.4 * (attempt + 1))
    with _lock:
        _cache[(text, target)] = out
    return out


def to_zh(text, force=False):
    if not text:
        return text
    if not force and not needs_translate(text):
        return text
    return _one(text, "zh-CN")


def to_en(text):
    if not text or not has_chinese(text):
        return text
    return _one(text, "en")


def _to_lang(text, lang):
    if not text or not has_chinese(text):
        return text
    return _one(text, lang)


def to_ko(text):
    return _to_lang(text, "ko")


def to_ja(text):
    return _to_lang(text, "ja")


def to_zh_hant(text):
    return _to_lang(text, "zh-TW")


def translate_many(texts, force=False):
    """并发翻译一批标题(只翻需要翻的)，返回 {原文本: 翻译后}；force=True 时强制全部翻译（用于日文源）"""
    texts = list(texts)
    todo = texts if force else [t for t in texts if t and needs_translate(t)]
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda t: _one(t, "zh-CN"), todo))
    out = {}
    with _lock:
        for t in texts:
            out[t] = _cache.get((t, "zh-CN"), t)
    return out
