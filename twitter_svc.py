"""Twitter/X 图片/视频搜索与下载。

参考开源项目 twitter_download (https://github.com/caolvchong-top/twitter_download, MIT) 的思路：
- 使用 X 的 GraphQL SearchTimeline 接口
- 需要登录 cookie（auth_token + ct0），从 .env TWITTER_COOKIE 读取
"""

import json
import os
import re
from urllib.parse import quote

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SEARCH_HASH = "AIdc203rPpK_k_2KWSdm7g"

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": UA})

# SearchTimeline 标准 features 参数
_SEARCH_FEATURES = (
    '"rweb_video_sc_worker":true,"rweb_video_scripts":true,"creator_subscriptions_tweet_preview_api_enabled":true,'
    '"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,'
    '"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"premium_content_api_read_enabled":false,"responsive_web_media_download_video_enabled":true,'
    '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
    '"responsive_web_tweet_use_referrer_tag":true,"responsive_web_media_download_video_enabled":true,'
    '"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,'
    '"blue_business_profile_image_shape_enabled":false,"responsive_web_media_playing_enabled":true,'
    '"c9s_tweet_anatomy_moderator_badge_enabled":true,"responsive_web_tweet_tasks_enabled":true,'
    '"responsive_web_tweet_actions_limit_enabled":true,"responsive_web_tweet_actions_limit_initial_tweet_follow_rate":100'
)

def _proxy():
    """出站代理。Vercel 上由 PROXY 环境变量或「设置」面板提供。"""
    from env_utils import proxy as _env_proxy

    return _env_proxy()


def get_cookie():
    """从 .env TWITTER_COOKIE 读取登录 cookie。"""
    cookie = ""
    try:
        with open(os.path.join(BASE, ".env"), "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("TWITTER_COOKIE="):
                    cookie = line.strip().split("=", 1)[1].strip()
                    break
    except OSError:
        pass
    if not cookie:
        raise ValueError("未配置 Twitter 登录 Cookie，请在设置中填写 TWITTER_COOKIE（auth_token=...; ct0=...）")
    return cookie


def _csrf(cookie):
    m = re.search(r"ct0=([^;]+)", cookie)
    return m.group(1) if m else ""


def _search_request(raw_query, cursor="", count=50):
    """发起 SearchTimeline 请求，返回 JSON。"""
    cookie = get_cookie()
    variables = {"rawQuery": raw_query, "count": count, "cursor": cursor, "querySource": "typed_query", "product": "Media"}
    url = (
        f"https://x.com/i/api/graphql/{SEARCH_HASH}/SearchTimeline"
        f"?variables={quote(json.dumps(variables, ensure_ascii=False, separators=(',', ':')))}"
        f"&features={quote('{' + _SEARCH_FEATURES + '}')}"
    )
    proxies = {"http": _proxy(), "https": _proxy()} if _proxy() else None
    resp = _SESSION.get(
        url,
        headers={
            "User-Agent": UA,
            "Cookie": cookie,
            "x-csrf-token": _csrf(cookie),
            "Referer": f"https://x.com/search?q={quote(raw_query)}&src=typed_query&f=media",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=20,
        proxies=proxies,
    )
    if resp.status_code == 429:
        raise ValueError("Twitter API 请求次数已达上限（Rate limit exceeded），请稍后再试")
    if resp.status_code != 200:
        raise ValueError(f"Twitter 请求失败(HTTP {resp.status_code})")
    try:
        return resp.json()
    except ValueError:
        raise ValueError("Twitter 响应不是合法 JSON")


def _walk_entries(obj, results):
    """递归提取推文。"""
    if isinstance(obj, list):
        for v in obj:
            _walk_entries(v, results)
        return
    if not isinstance(obj, dict):
        return
    if obj.get("__typename") == "Tweet":
        results.append(obj)
    for v in obj.values():
        _walk_entries(v, results)


def _get_heighest_video(variants):
    best = None
    best_bitrate = -1
    for v in variants:
        if v.get("content_type") == "video/mp4":
            br = v.get("bitrate") or 0
            if br > best_bitrate:
                best_bitrate = br
                best = v.get("url")
    return best or (variants[0].get("url") if variants else None)


def search_twitter(keyword, count=30):
    """按关键词搜索 Twitter 含媒体推文，返回图片/视频条目。"""
    raw_query = f'{keyword} filter:media -filter:retweets lang:en'
    results = []
    cursor = ""
    seen_tweets = set()
    while len(results) < count and cursor is not None:
        data = _search_request(raw_query, cursor, 50)
        cursor = ""
        # 提取 entry 里的 tweet
        tweets = []
        _walk_entries(data, tweets)
        for tw in tweets:
            tw_id = tw.get("rest_id") or tw.get("legacy", {}).get("id_str")
            if not tw_id or tw_id in seen_tweets:
                continue
            seen_tweets.add(tw_id)
            legacy = tw.get("legacy") or {}
            media_lst = (legacy.get("extended_entities") or {}).get("media") or []
            for m in media_lst:
                mtype = m.get("type")
                if mtype == "photo":
                    url = m.get("media_url_https") or m.get("media_url") or ""
                    if url:
                        results.append({
                            "type": "image",
                            "title": (legacy.get("full_text") or keyword)[:200],
                            "url": url + "?format=png&name=4096x4096",
                            "thumb": url + "?format=jpg&name=small",
                            "source": "twitter",
                        })
                elif mtype in ("video", "animated_gif"):
                    vinfo = m.get("video_info") or {}
                    vurl = _get_heighest_video(vinfo.get("variants") or [])
                    if vurl:
                        results.append({
                            "type": "video",
                            "title": (legacy.get("full_text") or keyword)[:200],
                            "url": vurl,
                            "thumb": (m.get("media_url_https") or "") + "?format=jpg&name=small",
                            "source": "twitter",
                        })
                if len(results) >= count:
                    break
            if len(results) >= count:
                break
        # 找下一页 cursor
        c = _find_cursor(data)
        if not c:
            break
        cursor = c
    if not results:
        raise ValueError("Twitter 没有搜索到含媒体内容")
    return results


def _find_cursor(data):
    """递归找 cursor。"""
    if isinstance(data, list):
        for v in data:
            c = _find_cursor(v)
            if c:
                return c
        return ""
    if not isinstance(data, dict):
        return ""
    if data.get("cursorType") == "Bottom" and data.get("value"):
        return data["value"]
    for v in data.values():
        c = _find_cursor(v)
        if c:
            return c
    return ""
