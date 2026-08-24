"""Open-license music search and preview proxying (Vercel-adapted)."""

import concurrent.futures
import html
import os
import re
from urllib.parse import quote, urljoin, urlparse, urlsplit, urlunsplit

import requests

MUSIC_SOURCES = {
    "internet_archive": "Internet Archive Audio",
    "wikimedia": "Wikimedia Commons",
    "audius": "Audius",
    "jamendo": "Jamendo",
}

_BASE = os.path.dirname(os.path.abspath(__file__))
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36 WanpaWeb-Music/1.0"
_HEADERS = {"User-Agent": _UA, "Accept": "application/json"}
_AUDIO_EXTS = {"mp3", "flac", "ogg", "oga", "opus", "webm", "wav", "m4a"}
_MIME_EXTS = {
    "audio/mpeg": {"mp3"}, "audio/mp3": {"mp3"}, "audio/flac": {"flac"},
    "audio/x-flac": {"flac"}, "audio/ogg": {"ogg", "oga", "opus"},
    "application/ogg": {"ogg", "oga", "opus"}, "audio/opus": {"opus"},
    "audio/webm": {"webm"}, "audio/wav": {"wav"}, "audio/x-wav": {"wav"},
    "audio/wave": {"wav"}, "audio/mp4": {"m4a"}, "audio/x-m4a": {"m4a"},
}
_REDIRECTS = {301, 302, 303, 307, 308}


class MusicSourceError(RuntimeError):
    pass


def _config(name, default=""):
    return os.environ.get(name, default)


def _proxies():
    proxy = _config("PROXY")
    return {"http": proxy, "https": proxy} if proxy else None


def _request_json(source, url, params=None):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=_HEADERS, proxies=_proxies(), timeout=(10, 30))
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                response.close()
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                import time
                time.sleep(1.5 * (attempt + 1))
    raise MusicSourceError(f"{MUSIC_SOURCES.get(source, source)} 请求失败: {last_error}") from last_error


def _plain(value):
    if isinstance(value, dict):
        value = value.get("value", "")
    return re.sub(r"<[^>]+>", " ", html.unescape(str(value or ""))).strip()


def _first(value):
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _year(value):
    match = re.search(r"\b(1[0-9]{3}|20[0-9]{2}|2100)\b", _first(value))
    return int(match.group(1)) if match else None


def _duration(value):
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _license_allowed(license_url="", rights=""):
    url = _plain(license_url).lower()
    text = _plain(rights).lower()
    if "creativecommons.org/licenses/" in url or "creativecommons.org/publicdomain/" in url:
        return True
    if "rightsstatements.org/vocab/noc-" in url:
        return True
    if re.search(r"\b(cc0|cc[ -]by(?:[ -](?:sa|nc|nd))?|creative commons)\b", text):
        return True
    return bool(re.search(r"\b(public domain|no known copyright|公有领域|公共领域)\b", text))


def _result(source, item_id, title, artists="", album="", duration=None, year=None,
            cover_url="", detail_url="", license_name="", license_url="",
            preview_url="", candidates=None):
    if isinstance(artists, (list, tuple)):
        artist_list = [str(value) for value in artists if value]
    else:
        artist_list = [part.strip() for part in re.split(r"\s*[;,]\s*", str(artists or "")) if part.strip()]
    return {
        "id": str(item_id or ""),
        "source": source,
        "title": str(title or "Untitled"),
        "artists": artist_list,
        "album": str(album or ""),
        "duration": _duration(duration),
        "year": _year(year),
        "cover_url": str(cover_url or ""),
        "detail_url": str(detail_url or ""),
        "license": _plain(license_name),
        "license_url": _plain(license_url),
        "preview_url": str(preview_url or ""),
        "download_candidates": candidates or [],
    }


def _ia_candidate(identifier, file_info):
    name = str(file_info.get("name") or "")
    ext = os.path.splitext(urlparse(name).path)[1].lower().lstrip(".")
    if ext not in _AUDIO_EXTS:
        return None
    return {
        "url": "https://archive.org/download/{}/{}".format(quote(identifier, safe=""), quote(name, safe="/")),
        "format": ext, "mime": "", "size": int(file_info.get("size") or 0),
    }


def _search_internet_archive(keyword, page, page_size):
    ia_keyword = keyword.replace('"', '\\"')
    data = _request_json("internet_archive", "https://archive.org/advancedsearch.php", {
        "q": f'mediatype:audio AND licenseurl:* AND (title:"{ia_keyword}" OR creator:"{ia_keyword}")',
        "fl[]": ["identifier", "title", "creator", "date", "licenseurl", "rights"],
        "rows": page_size, "page": page, "output": "json",
    })
    output = []
    for doc in data.get("response", {}).get("docs", []):
        identifier = str(doc.get("identifier") or "")
        if not identifier:
            continue
        detail = _request_json("internet_archive", f"https://archive.org/metadata/{quote(identifier, safe='')}")
        metadata = detail.get("metadata") or {}
        license_url = _first(metadata.get("licenseurl") or doc.get("licenseurl"))
        rights = _first(metadata.get("rights") or doc.get("rights"))
        allowed = _license_allowed(license_url, rights)
        candidates = []
        if allowed:
            candidates = [c for c in (_ia_candidate(identifier, v) for v in detail.get("files", [])) if c]
        preview = next((v["url"] for v in candidates if v["format"] == "mp3"), "")
        if not preview:
            preview = next((v["url"] for v in candidates), "")
        output.append(_result(
            "internet_archive", identifier, metadata.get("title") or doc.get("title"),
            metadata.get("creator") or doc.get("creator"), metadata.get("album"),
            metadata.get("runtime"), metadata.get("date") or doc.get("date"),
            f"https://archive.org/services/img/{quote(identifier, safe='')}",
            f"https://archive.org/details/{quote(identifier, safe='')}",
            rights or ("Creative Commons" if allowed else ""), license_url, preview, candidates,
        ))
    return output


def _search_wikimedia(keyword, page, page_size):
    data = _request_json("wikimedia", "https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"filetype:audio {keyword}", "gsrnamespace": 6, "gsrlimit": page_size,
        "gsroffset": (page - 1) * page_size, "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
    })
    output = []
    for page_data in data.get("query", {}).get("pages", {}).values():
        info = (page_data.get("imageinfo") or [{}])[0]
        mime = str(info.get("mime") or "").lower().split(";", 1)[0]
        if mime not in _MIME_EXTS:
            continue
        metadata = info.get("extmetadata") or {}
        license_name = _plain(metadata.get("LicenseShortName") or metadata.get("UsageTerms"))
        license_url = _plain(metadata.get("LicenseUrl"))
        if not _license_allowed(license_url, license_name):
            continue
        media_url = str(info.get("url") or "")
        if urlparse(media_url).hostname == "upload.wikimedia.org":
            parts = urlsplit(media_url)
            media_url = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        ext = os.path.splitext(urlparse(media_url).path)[1].lower().lstrip(".")
        if ext not in _AUDIO_EXTS:
            ext = next(iter(_MIME_EXTS[mime]))
        title = re.sub(r"^File:", "", str(page_data.get("title") or ""), flags=re.I)
        output.append(_result(
            "wikimedia", page_data.get("pageid"), title,
            _plain(metadata.get("Artist")), "", None, _plain(metadata.get("DateTimeOriginal")),
            info.get("thumburl"), info.get("descriptionurl") or media_url,
            license_name, license_url, media_url,
            [{"url": media_url, "format": ext, "mime": mime, "size": int(info.get("size") or 0)}],
        ))
    return output


def _search_audius(keyword, page, page_size):
    data = _request_json("audius", "https://api.audius.co/v1/tracks/search", {
        "query": keyword, "limit": page_size, "offset": (page - 1) * page_size,
        "app_name": "WanpaWeb",
    })
    output = []
    for track in data.get("data", []):
        track_id = track.get("id")
        if not track_id:
            continue
        user = track.get("user") or {}
        artwork = track.get("artwork") or {}
        downloadable = bool(track.get("is_downloadable") or track.get("downloadable"))
        candidates = []
        if downloadable:
            candidates.append({
                "url": f"https://api.audius.co/v1/tracks/{quote(str(track_id), safe='')}/download?app_name=WanpaWeb",
                "format": "mp3", "mime": "audio/mpeg", "size": 0,
            })
        permalink = str(track.get("permalink") or "")
        if permalink.startswith("/"):
            permalink = "https://audius.co" + permalink
        output.append(_result(
            "audius", track_id, track.get("title"), user.get("name"), track.get("album_name"),
            track.get("duration"), track.get("release_date") or track.get("created_at"),
            artwork.get("1000x1000") or artwork.get("480x480") or artwork.get("150x150"),
            permalink, "Audius uploader terms", "",
            f"https://api.audius.co/v1/tracks/{quote(str(track_id), safe='')}/stream?app_name=WanpaWeb",
            candidates,
        ))
    return output


def _jamendo_client_id():
    return str(_config("JAMENDO_CLIENT_ID") or "").strip()


def _search_jamendo(keyword, page, page_size):
    client_id = _jamendo_client_id()
    if not client_id:
        return []
    try:
        from trans_svc import has_chinese, to_en
        if has_chinese(keyword):
            keyword = to_en(keyword)
    except Exception:
        pass
    data = _request_json("jamendo", "https://api.jamendo.com/v3.0/tracks/", {
        "client_id": client_id, "format": "json", "search": keyword,
        "limit": page_size, "offset": (page - 1) * page_size,
        "include": "musicinfo", "audioformat": "mp32",
    })
    if data.get("headers", {}).get("status") not in (None, "success"):
        raise MusicSourceError(f"Jamendo 请求失败: {data.get('headers', {}).get('error_message', '未知错误')}")
    output = []
    for track in data.get("results", []):
        allowed = bool(track.get("audiodownload_allowed"))
        download_url = str(track.get("audiodownload") or "")
        candidates = []
        if allowed and download_url:
            candidates.append({"url": download_url, "format": "mp3", "mime": "audio/mpeg", "size": 0})
        license_url = str(track.get("license_ccurl") or "")
        output.append(_result(
            "jamendo", track.get("id"), track.get("name"), track.get("artist_name"),
            track.get("album_name"), track.get("duration"), track.get("releasedate"),
            track.get("album_image") or track.get("image"), track.get("shareurl"),
            "Creative Commons" if license_url else "", license_url, track.get("audio"), candidates,
        ))
    return output


_SEARCHERS = {
    "internet_archive": _search_internet_archive,
    "wikimedia": _search_wikimedia,
    "audius": _search_audius,
    "jamendo": _search_jamendo,
}
_SOURCE_ALIASES = {"ia": "internet_archive", "internet archive audio": "internet_archive",
                    "wikimedia commons": "wikimedia"}


def search_music(keyword, source="all", page=1, page_size=12):
    keyword = str(keyword or "").strip()
    if not keyword:
        raise ValueError("搜索关键词不能为空")
    page, page_size = int(page), int(page_size)
    if page < 1 or not 1 <= page_size <= 50:
        raise ValueError("page 必须大于 0, page_size 必须在 1 到 50 之间")
    source = _SOURCE_ALIASES.get(str(source or "all").strip().lower(), str(source or "all").strip().lower())
    if source != "all" and source not in _SEARCHERS:
        raise ValueError("不支持的音乐来源")
    if source != "all":
        return _SEARCHERS[source](keyword, page, page_size)
    enabled = [name for name in MUSIC_SOURCES if name != "jamendo" or _jamendo_client_id()]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(enabled)) as pool:
        futures = {pool.submit(_SEARCHERS[name], keyword, page, page_size): name for name in enabled}
        for future in concurrent.futures.as_completed(futures):
            try:
                results.extend(future.result())
            except MusicSourceError:
                continue
    return results


def stream_music(url, range_header=None):
    if range_header and not re.fullmatch(r"bytes=(?:\d+-\d*|-\d+)", str(range_header).strip()):
        raise ValueError("Range 请求格式不合法")
    current_url = str(url)
    for _ in range(6):
        headers = {"User-Agent": _UA, "Accept": "audio/*,application/ogg", "Referer": ""}
        if range_header:
            headers["Range"] = str(range_header).strip()
        response = None
        for attempt in range(3):
            response = requests.get(current_url, headers=headers, proxies=_proxies(),
                                     timeout=(15, 45), stream=True, allow_redirects=False)
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                response.close()
                import time
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        if response.status_code in _REDIRECTS:
            target = response.headers.get("Location")
            response.close()
            if not target:
                raise ValueError("重定向缺少目标地址")
            current_url = urljoin(current_url, target)
            continue
        response.raise_for_status()
        content_type = str(response.headers.get("Content-Type") or "").lower().split(";", 1)[0].strip()
        if content_type not in _MIME_EXTS:
            response.close()
            raise ValueError(f"远端 Content-Type 不是受支持的音频: {content_type or '缺失'}")
        resp_headers = {}
        for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
            if response.headers.get(name):
                resp_headers[name] = response.headers[name]
        def chunks(r=response):
            try:
                yield from r.iter_content(1 << 16)
            finally:
                r.close()
        return response.status_code, resp_headers, chunks()
    raise ValueError("重定向次数过多")
