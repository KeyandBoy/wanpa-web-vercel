import json
import os

import requests

_URL = os.environ.get("KV_REST_API_URL") or ""
_TOKEN = os.environ.get("KV_REST_API_TOKEN") or ""
_mem = {}


def _is_prod():
    return bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))


def available():
    return bool(_URL and _TOKEN)


def _headers():
    return {"Authorization": "Bearer " + _TOKEN, "Content-Type": "application/json"}


def get(key):
    if not available():
        return _mem.get(key)
    r = requests.get(_URL.rstrip("/") + "/get/" + key, headers=_headers(), timeout=10)
    if r.status_code != 200:
        raise RuntimeError("KV get failed: HTTP %s %s" % (r.status_code, r.text[:200]))
    return r.json().get("result")


def set(key, value, ttl=None):
    if not available():
        _mem[key] = value
        return True
    body = {"value": value}
    if ttl:
        body["ttl"] = ttl
    r = requests.put(_URL.rstrip("/") + "/set/" + key, headers=_headers(), json=body, timeout=10)
    if r.status_code not in (200, 201):
        raise RuntimeError("KV set failed: HTTP %s %s" % (r.status_code, r.text[:200]))
    return True


def delete(key):
    if not available():
        _mem.pop(key, None)
        return True
    r = requests.delete(_URL.rstrip("/") + "/del/" + key, headers=_headers(), timeout=10)
    return r.status_code in (200, 201, 204)
