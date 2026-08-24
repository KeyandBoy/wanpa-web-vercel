"""大学教材与电子书多源搜索 (Vercel-adapted, search-only)."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import re
import unicodedata
from urllib.parse import quote

import requests

BOOK_SOURCES = [
    {"id": "google", "name": "Google Books", "language": "中英文", "kind": "书目/预览", "access_mode": "preview"},
    {"id": "openlibrary", "name": "Open Library", "language": "中英文", "kind": "书目/借阅", "access_mode": "mixed"},
    {"id": "archive", "name": "Internet Archive", "language": "中英文", "kind": "开放文件/借阅", "access_mode": "mixed"},
    {"id": "doab", "name": "DOAB / OAPEN", "language": "外文为主", "kind": "开放学术书", "access_mode": "open"},
    {"id": "gutenberg", "name": "Project Gutenberg", "language": "多语言", "kind": "公版电子书", "access_mode": "open"},
    {"id": "wikibooks", "name": "Wikibooks", "language": "中英文", "kind": "开放教材", "access_mode": "open"},
    {"id": "wikisource", "name": "Wikisource", "language": "中英文", "kind": "公开书目/原文", "access_mode": "open"},
]

_SOURCE_IDS = {item["id"] for item in BOOK_SOURCES}
_HEADERS = {"User-Agent": "WanpaWeb-BookSearch/1.0 (educational discovery tool)"}
_TIMEOUT = 18


def _config(name, default=""):
    try:
        from env_utils import env as _env

        return _env(name, default)
    except Exception:
        return os.environ.get(name, default)


def _proxies():
    proxy = _config("PROXY")
    return {"http": proxy, "https": proxy} if proxy else None


def _get_json(url, params=None, retries=2):
    last_err = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=_HEADERS, proxies=_proxies(), timeout=_TIMEOUT)
            if response.status_code == 429:
                raise RuntimeError("远程书源请求过于频繁 (HTTP 429), 请稍后重试并减少连续搜索")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                import time
                time.sleep(1)
    raise last_err


def _clean_list(value):
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


def _nfkc(value):
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _valid_isbn10(value):
    return len(value) == 10 and value[:9].isdigit() and (value[9].isdigit() or value[9] == "X") and sum(
        (10 - index) * (10 if char == "X" else int(char)) for index, char in enumerate(value)
    ) % 11 == 0


def _valid_isbn13(value):
    return len(value) == 13 and value.isdigit() and sum(
        int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(value[:12])
    ) % 10 == (10 - int(value[12])) % 10


def _isbn13_from10(value):
    body = "978" + value[:9]
    check = (10 - sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(body)) % 10) % 10
    return body + str(check)


def _isbn10_from13(value):
    if not value.startswith("978"):
        return ""
    body = value[3:12]
    check = (11 - sum((10 - index) * int(char) for index, char in enumerate(body)) % 11) % 11
    return body + ("X" if check == 10 else str(check))


def _isbn_values(values):
    isbn10 = ""
    isbn13 = ""
    for value in _clean_list(values):
        compact = re.sub(r"[^0-9Xx]", "", _nfkc(value)).upper()
        if _valid_isbn13(compact) and not isbn13:
            isbn13 = compact
        elif _valid_isbn10(compact) and not isbn10:
            isbn10 = compact
    if isbn10 and not isbn13:
        isbn13 = _isbn13_from10(isbn10)
    if isbn13 and not isbn10:
        isbn10 = _isbn10_from13(isbn13)
    return isbn10, isbn13


def _query_isbn(query):
    isbn10, isbn13 = _isbn_values([query])
    return isbn13 or isbn10


def _book(source, title, **extra):
    item = {
        "id": extra.pop("id", ""),
        "source": source,
        "sources": [source],
        "title": str(title or "未命名教材").strip(),
        "authors": [],
        "publisher": "",
        "published_year": "",
        "edition": "",
        "isbn10": "",
        "isbn13": "",
        "language": "",
        "subjects": [],
        "description": "",
        "cover_url": "",
        "detail_url": "",
        "access_type": "metadata",
        "license": "",
        "download_candidates": [],
    }
    item.update(extra)
    return item


def _search_google(query, page, limit):
    start = max(0, (page - 1) * limit)
    isbn = _query_isbn(query)
    search_query = "isbn:" + isbn if isbn else 'intitle:"' + _nfkc(query).replace('"', " ") + '"'
    params = {"q": search_query, "startIndex": start, "maxResults": min(limit, 40), "printType": "books"}
    api_key = _config("GOOGLE_BOOKS_KEY")
    if api_key:
        params["key"] = api_key
    data = _get_json("https://www.googleapis.com/books/v1/volumes", params)
    items = []
    for row in data.get("items") or []:
        info = row.get("volumeInfo") or {}
        access = row.get("accessInfo") or {}
        identifiers = [x.get("identifier") for x in info.get("industryIdentifiers") or []]
        isbn10, isbn13 = _isbn_values(identifiers)
        candidates = []
        for fmt in ("pdf", "epub"):
            fmt_info = access.get(fmt) or {}
            url = fmt_info.get("downloadLink") or fmt_info.get("acsTokenLink")
            if fmt_info.get("isAvailable") and url:
                candidates.append({"url": url, "format": fmt, "source": "Google Books"})
        viewability = access.get("viewability") or ""
        access_type = "open_access" if viewability in ("ALL_PAGES", "ALL_PAGES_NO_TOKEN") else "preview"
        if viewability in ("NO_PAGES", "NONE", ""):
            access_type = "metadata"
        images = info.get("imageLinks") or {}
        items.append(_book(
            "Google Books", info.get("title"),
            id="google:" + str(row.get("id") or ""),
            authors=_clean_list(info.get("authors")),
            publisher=info.get("publisher") or "",
            published_year=str(info.get("publishedDate") or "")[:4],
            isbn10=isbn10, isbn13=isbn13,
            language=info.get("language") or "",
            subjects=_clean_list(info.get("categories")),
            description=info.get("description") or "",
            cover_url=images.get("thumbnail") or images.get("smallThumbnail") or "",
            detail_url=info.get("infoLink") or row.get("selfLink") or "",
            access_type=access_type,
            download_candidates=_sort_candidates(candidates),
        ))
    return items, start + limit < int(data.get("totalItems") or 0)


def _search_openlibrary(query, page, limit):
    fields = "key,title,author_name,first_publish_year,publisher,isbn,language,cover_i,ia,ebook_access,subject"
    isbn = _query_isbn(query)
    params = {"page": page, "limit": limit, "fields": fields}
    params["isbn" if isbn else "title"] = isbn or _nfkc(query)
    data = _get_json("https://openlibrary.org/search.json", params)
    docs = data.get("docs") or []
    public_ids = []
    for row in docs:
        if row.get("ebook_access") == "public":
            public_ids.extend(_clean_list(row.get("ia")))
    files_by_id = _archive_files_many(public_ids)
    items = []
    for row in docs:
        isbn10, isbn13 = _isbn_values(row.get("isbn"))
        access_value = row.get("ebook_access") or ""
        access_type = {"public": "open_access", "borrowable": "borrow"}.get(access_value, "metadata")
        cover_id = row.get("cover_i")
        candidates = []
        license_url = ""
        for identifier in _clean_list(row.get("ia")):
            found, found_license = files_by_id.get(identifier, ([], ""))
            candidates.extend(found)
            license_url = license_url or found_license
        items.append(_book(
            "Open Library", row.get("title"),
            id="openlibrary:" + str(row.get("key") or ""),
            authors=_clean_list(row.get("author_name")),
            publisher=(_clean_list(row.get("publisher")) or [""])[0],
            published_year=str(row.get("first_publish_year") or ""),
            isbn10=isbn10, isbn13=isbn13,
            language=(_clean_list(row.get("language")) or [""])[0],
            subjects=_clean_list(row.get("subject"))[:8],
            cover_url=f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else "",
            detail_url="https://openlibrary.org" + str(row.get("key") or ""),
            access_type=access_type, license=license_url,
            download_candidates=_sort_candidates(candidates),
        ))
    return items, page * limit < int(data.get("numFound") or 0)


def _archive_files(identifier):
    try:
        data = _get_json("https://archive.org/metadata/" + quote(identifier, safe=""))
    except Exception:
        return [], ""
    metadata = data.get("metadata") or {}
    restricted = str(metadata.get("access-restricted-item") or "").lower() == "true"
    if restricted:
        return [], metadata.get("licenseurl") or ""
    result = []
    for file_info in data.get("files") or []:
        name = str(file_info.get("name") or "")
        lower = name.lower()
        if lower.endswith(".pdf"):
            fmt = "pdf"
        elif lower.endswith(".epub"):
            fmt = "epub"
        elif lower.endswith(".txt") and not lower.endswith("_djvu.txt"):
            fmt = "txt"
        else:
            continue
        if file_info.get("private") or str(file_info.get("viruscheck") or "").lower() == "virus_found":
            continue
        result.append({
            "url": f"https://archive.org/download/{quote(identifier, safe='')}/{quote(name, safe='')}",
            "format": fmt, "size": int(file_info.get("size") or 0),
            "source": "Internet Archive",
            "original": str(file_info.get("source") or "").lower() == "original",
        })
    return _sort_candidates(result)[:6], metadata.get("licenseurl") or ""


def _archive_files_many(identifiers):
    identifiers = list(dict.fromkeys(identifier for identifier in identifiers if identifier))
    result = {}
    if not identifiers:
        return result
    with ThreadPoolExecutor(max_workers=min(4, len(identifiers))) as pool:
        jobs = {pool.submit(_archive_files, identifier): identifier for identifier in identifiers}
        for job in as_completed(jobs):
            identifier = jobs[job]
            try:
                result[identifier] = job.result()
            except Exception:
                result[identifier] = ([], "")
    return result


def _ia_escape(value):
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", _nfkc(value))


def _search_archive(query, page, limit):
    isbn = _query_isbn(query)
    search_clause = f'isbn:"{isbn}"' if isbn else f'title:"{_ia_escape(query)}"'
    data = _get_json("https://archive.org/advancedsearch.php", {
        "q": f"{search_clause} AND mediatype:texts",
        "fl[]": ["identifier", "title", "creator", "year", "language", "description"],
        "rows": min(limit, 12), "page": page, "output": "json",
    })
    response = data.get("response") or {}
    docs = response.get("docs") or []
    files_by_id = _archive_files_many(str(row.get("identifier") or "") for row in docs)
    items = []
    for row in docs:
        identifier = str(row.get("identifier") or "")
        candidates, license_url = files_by_id.get(identifier, ([], ""))
        items.append(_book(
            "Internet Archive", row.get("title"),
            id="archive:" + identifier,
            authors=_clean_list(row.get("creator")),
            published_year=str(row.get("year") or "")[:4],
            language=(_clean_list(row.get("language")) or [""])[0],
            description=str(row.get("description") or "")[:1200],
            cover_url=f"https://archive.org/services/img/{quote(identifier, safe='')}",
            detail_url=f"https://archive.org/details/{quote(identifier, safe='')}",
            access_type="open_access" if candidates else "borrow",
            license=license_url, download_candidates=candidates,
        ))
    return items, page * limit < int(response.get("numFound") or 0)


def _metadata_map(row):
    result = {}
    for meta in row.get("metadata") or []:
        key = meta.get("key")
        value = meta.get("value")
        if key and value:
            result.setdefault(key, []).append(str(value))
    for bitstream in row.get("bitstreams") or []:
        for meta in bitstream.get("metadata") or []:
            key = meta.get("key")
            value = meta.get("value")
            if key and value:
                result.setdefault(key, []).append(str(value))
    return result


def _download_format(url, mime=""):
    lower = (str(url) + " " + str(mime)).lower()
    if "epub" in lower:
        return "epub"
    if "pdf" in lower:
        return "pdf"
    if "text/plain" in lower or re.search(r"\.txt(?:$|[?#])", lower):
        return "txt"
    return ""


def _sort_candidates(candidates):
    unique = {}
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if url.startswith(("http://", "https://")):
            unique[url] = candidate
    format_order = {"epub": 0, "pdf": 1, "txt": 2}
    return sorted(unique.values(), key=lambda item: (
        0 if item.get("original") else 1,
        format_order.get(str(item.get("format") or "").lower(), 9),
        int(item.get("size") or 0) if int(item.get("size") or 0) > 0 else 2 ** 63,
        str(item.get("url") or ""),
    ))


def _urls_from_value(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [value.get(key) for key in ("retrieveLink", "content", "url", "downloadUrl", "href") if value.get(key)]
    if isinstance(value, list):
        result = []
        for entry in value:
            result.extend(_urls_from_value(entry))
        return result
    return []


def _search_doab(query, page, limit):
    data = _get_json("https://directory.doabooks.org/rest/search", {
        "query": query, "expand": "metadata,bitstreams",
        "offset": (page - 1) * limit, "limit": limit,
    })
    items = []
    for row in data if isinstance(data, list) else []:
        meta = _metadata_map(row)
        isbn10, isbn13 = _isbn_values(meta.get("dc.identifier.isbn") or meta.get("oapen.relation.isbn"))
        downloads = []
        download_values = []
        for key, values in meta.items():
            if "download" in key.lower():
                download_values.extend(values)
        for bitstream in row.get("bitstreams") or []:
            hint = " ".join(str(bitstream.get(key) or "") for key in ("name", "mimeType", "format"))
            for url in _urls_from_value(bitstream):
                fmt = _download_format(url, hint)
                if fmt:
                    downloads.append({"url": url, "format": fmt, "source": "DOAB / OAPEN"})
        for url in _urls_from_value(download_values):
            fmt = _download_format(url)
            if fmt:
                downloads.append({"url": url, "format": fmt, "source": "DOAB / OAPEN"})
        handle = row.get("handle") or ""
        items.append(_book(
            "DOAB / OAPEN", (meta.get("dc.title") or [row.get("name") or ""])[0],
            id="doab:" + str(handle),
            authors=(meta.get("dc.contributor.author") or meta.get("dc.creator") or meta.get("dc.contributor.editor") or []),
            publisher=(meta.get("dc.publisher") or meta.get("publisher.name") or [""])[0],
            published_year=((meta.get("dc.date.issued") or [""])[0])[:4],
            isbn10=isbn10, isbn13=isbn13,
            language=(meta.get("dc.language") or [""])[0],
            subjects=(meta.get("dc.subject.other") or [])[:8],
            description=(meta.get("dc.description.abstract") or [""])[0],
            detail_url=(meta.get("dc.identifier.uri") or [f"https://directory.doabooks.org/handle/{handle}"])[0],
            access_type="open_access",
            license=(meta.get("dc.rights.uri") or [""])[0],
            download_candidates=_sort_candidates(downloads),
        ))
    return items, len(items) >= limit


def _search_gutenberg(query, page, limit):
    data = _get_json("https://gutendex.com/books/", {"search": _nfkc(query), "page": page})
    items = []
    for row in (data.get("results") or [])[:limit]:
        formats = row.get("formats") or {}
        downloads = []
        cover_url = ""
        for mime, url in formats.items():
            if not url:
                continue
            if mime.startswith("image/") and not cover_url:
                cover_url = url
                continue
            fmt = _download_format(url, mime)
            if fmt and (fmt == "epub" or "zip" not in mime.lower()) and not str(url).lower().endswith(".zip"):
                downloads.append({"url": url, "format": fmt, "source": "Project Gutenberg"})
        book_id = str(row.get("id") or "")
        authors = [author.get("name") for author in row.get("authors") or [] if author.get("name")]
        items.append(_book(
            "Project Gutenberg", row.get("title"),
            id="gutenberg:" + book_id, authors=authors,
            language=(_clean_list(row.get("languages")) or [""])[0],
            subjects=_clean_list(row.get("subjects"))[:8],
            cover_url=cover_url,
            detail_url=f"https://www.gutenberg.org/ebooks/{book_id}",
            access_type="open_access",
            license="Public domain in the USA; verify status in your jurisdiction",
            download_candidates=_sort_candidates(downloads),
        ))
    return items, bool(data.get("next"))


def _wiki_language(query):
    return "zh" if re.search(r"[\u4e00-\u9fff]", query) else "en"


def _search_wiki_project(project, source_name, query, page, limit):
    language = _wiki_language(query)
    data = _get_json(f"https://{language}.{project}.org/w/api.php", {
        "action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 0,
        "gsrlimit": limit, "gsroffset": (page - 1) * limit, "prop": "info|pageimages",
        "inprop": "url", "pithumbsize": 300, "format": "json", "origin": "*",
    })
    pages = list(((data.get("query") or {}).get("pages") or {}).values())
    pages.sort(key=lambda row: row.get("index") or 9999)
    items = []
    for row in pages:
        items.append(_book(
            source_name, row.get("title"),
            id=f"{project}:{language}:{row.get('pageid')}", language=language,
            cover_url=((row.get("thumbnail") or {}).get("source") or ""),
            detail_url=row.get("fullurl") or "",
            access_type="open_access", license="CC BY-SA",
        ))
    return items, bool(data.get("continue"))


def _search_wikibooks(query, page, limit):
    return _search_wiki_project("wikibooks", "Wikibooks", query, page, limit)


def _search_wikisource(query, page, limit):
    return _search_wiki_project("wikisource", "Wikisource", query, page, limit)


_SEARCHERS = {
    "google": _search_google,
    "openlibrary": _search_openlibrary,
    "archive": _search_archive,
    "doab": _search_doab,
    "gutenberg": _search_gutenberg,
    "wikibooks": _search_wikibooks,
    "wikisource": _search_wikisource,
}


def _normal(value):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", _nfkc(value).casefold())


def _source_order(item):
    source_ids = {entry["name"]: index for index, entry in enumerate(BOOK_SOURCES)}
    return source_ids.get(item.get("source"), len(source_ids))


def _merge_results(items):
    merged = {}
    order = []
    for item in items:
        isbn10, isbn13 = _isbn_values([item.get("isbn13"), item.get("isbn10")])
        item["isbn10"], item["isbn13"] = isbn10, isbn13
        key = "isbn:" + isbn13 if isbn13 else "isbn10:" + isbn10 if isbn10 else ""
        if not key:
            key = "book:" + _normal(item.get("title")) + ":" + _normal((item.get("authors") or [""])[0])
        if not key or key not in merged:
            merged[key or item.get("id")] = item
            order.append(key or item.get("id"))
            continue
        current = merged[key]
        current["sources"] = list(dict.fromkeys(current.get("sources", []) + item.get("sources", [])))
        current["download_candidates"] = _sort_candidates(current.get("download_candidates", []) + item.get("download_candidates", []))
        for field in ("cover_url", "description", "publisher", "published_year", "isbn10", "isbn13", "license", "detail_url"):
            if not current.get(field) and item.get(field):
                current[field] = item[field]
        if item.get("access_type") == "open_access":
            current["access_type"] = "open_access"
    return [merged[key] for key in order]


def _rank_key(item, query, english_query=""):
    query_texts = [_normal(query)]
    if english_query and _normal(english_query) not in query_texts:
        query_texts.append(_normal(english_query))
    title = _normal(item.get("title"))
    authors = _normal(" ".join(item.get("authors") or []))
    query_isbn = _query_isbn(query)
    item_isbns = {item.get("isbn10"), item.get("isbn13")}
    isbn_match = bool(query_isbn and query_isbn in item_isbns)
    exact_title = any(value and title == value for value in query_texts)
    title_coverage = any(value and (value in title or (len(title) >= 3 and title in value)) for value in query_texts)
    author_match = any(value and value in authors for value in query_texts)
    query_has_zh = bool(re.search(r"[\u4e00-\u9fff]", _nfkc(query)))
    title_has_zh = bool(re.search(r"[\u4e00-\u9fff]", _nfkc(item.get("title"))))
    language = str(item.get("language") or "").lower()
    language_match = (query_has_zh and (title_has_zh or language.startswith(("zh", "chi", "zho")))) or not query_has_zh
    downloads = item.get("download_candidates") or []
    access_rank = {"open_access": 0, "borrow": 1, "preview": 2, "metadata": 3}.get(item.get("access_type"), 4)
    return (
        0 if isbn_match else 1, 0 if exact_title else 1, 0 if title_coverage else 1,
        0 if author_match else 1, 0 if language_match else 1, 0 if downloads else 1,
        access_rank, -min(len(downloads), 9), _source_order(item), title, str(item.get("id") or ""),
    )


def search_books(keyword, source="all", page=1, page_size=12, english_keyword=""):
    keyword = _nfkc(keyword)
    if not keyword:
        raise ValueError("关键词不能为空")
    if len(keyword) > 120:
        raise ValueError("关键词不能超过 120 个字符")
    page = max(1, int(page))
    page_size = max(1, min(20, int(page_size)))
    source_ids = [item["id"] for item in BOOK_SOURCES] if source == "all" else [source]
    source_ids = [item for item in source_ids if item in _SEARCHERS]
    if not source_ids:
        raise ValueError("未知书源")
    english_keyword = _nfkc(english_keyword)
    items_by_source = {source_id: [] for source_id in source_ids}
    errors = {}
    more_by_source = {source_id: False for source_id in source_ids}
    requests_to_run = [(source_id, keyword, "primary") for source_id in source_ids]
    if english_keyword and _normal(english_keyword) != _normal(keyword):
        supplement_ids = [source_id for source_id in source_ids if source_id in ("doab", "gutenberg", "wikisource")]
        if source != "all" and source_ids and not supplement_ids:
            supplement_ids = source_ids[:1]
        requests_to_run.extend((source_id, english_keyword, "english") for source_id in supplement_ids[:3])
    with ThreadPoolExecutor(max_workers=min(8, len(requests_to_run))) as pool:
        jobs = {}
        for source_id, query, query_kind in requests_to_run:
            jobs[pool.submit(_SEARCHERS[source_id], query, page, page_size)] = (source_id, query_kind)
        for job in as_completed(jobs):
            source_id, query_kind = jobs[job]
            try:
                source_items, source_more = job.result()
                items_by_source[source_id].extend(source_items)
                more_by_source[source_id] = more_by_source[source_id] or source_more
            except Exception as exc:
                message = str(exc)
                if source_id in errors and message not in errors[source_id]:
                    errors[source_id] += "; " + message
                else:
                    errors[source_id] = message
    source_stats = {}
    ordered_items = []
    for source_id in source_ids:
        source_items = _merge_results(items_by_source[source_id])
        source_stats[source_id] = {"hits": len(source_items), "downloadable": sum(bool(item.get("download_candidates")) for item in source_items)}
        ordered_items.extend(source_items)
    items = _merge_results(ordered_items)
    items.sort(key=lambda item: _rank_key(item, keyword, english_keyword))
    return {"items": items, "page": page, "has_more": any(more_by_source.values()), "errors": errors, "source_stats": source_stats}


def source_catalog():
    return BOOK_SOURCES
