"""Gọi WDQS và MediaWiki API có cache SQLite, giãn cách request và retry."""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from vidbpedia.common import CACHE_PATH

logger = logging.getLogger(__name__)

USER_AGENT = os.environ.get(
    "VI_DBPEDIA_UA",
    "VietnameseDBpedia-coursework/2.0 (https://github.com/stephen-do/vietnamese-dbpedia; Semantic Web course project)",
)
WDQS_URL = "https://query.wikidata.org/sparql"
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
MIN_INTERVAL = {"wdqs": 2.0, "wiki": 1.0}  # giây giữa hai request liên tiếp
LIST_PROPS = ("categories", "redirects", "links", "templates", "extlinks", "langlinks")


class OfflineMiss(RuntimeError):
    pass


class Cache:
    """(kind, key) → JSON trong SQLite. refresh: bỏ qua cache; offline: báo lỗi thay vì gọi mạng."""

    def __init__(self, path=CACHE_PATH, refresh=False, offline=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS kv (kind TEXT, key TEXT, value TEXT, fetched_at TEXT, PRIMARY KEY (kind, key))"
        )
        self.refresh = refresh
        self.offline = offline

    def get(self, kind, key):
        if self.refresh:
            return None
        row = self.db.execute("SELECT value FROM kv WHERE kind=? AND key=?", (kind, key)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, kind, key, value):
        self.db.execute(
            "INSERT OR REPLACE INTO kv VALUES (?, ?, ?, ?)",
            (kind, key, json.dumps(value, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def require_online(self, what):
        if self.offline:
            raise OfflineMiss(f"--offline nhưng chưa có trong cache: {what}")


def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    retry = Retry(
        total=5,
        backoff_factor=1.2,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


SESSION = _session()
_last_call = {"wdqs": 0.0, "wiki": 0.0}


def _throttle(service):
    wait = MIN_INTERVAL[service] - (time.monotonic() - _last_call[service])
    if wait > 0:
        time.sleep(wait)
    _last_call[service] = time.monotonic()


def wdqs_select(query, cache, name="query", attempts=4):
    """SELECT trên WDQS → list[dict[biến, giá trị]], cache theo sha1 của truy vấn."""
    key = hashlib.sha1(query.encode("utf-8")).hexdigest()
    hit = cache.get("wdqs", key)
    if hit is not None:
        return hit
    cache.require_online(f"WDQS {name}")
    for attempt in range(1, attempts + 1):
        _throttle("wdqs")
        try:
            resp = SESSION.post(
                WDQS_URL,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=(10, 90),
            )
        except requests.RequestException as e:
            logger.warning("[WDQS] %s lần %d lỗi mạng: %s", name, attempt, e)
            time.sleep(5 * attempt)
            continue
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "30"))
            logger.warning("[WDQS] 429, chờ %ss", wait)
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            logger.warning("[WDQS] %s lần %d: HTTP %s", name, attempt, resp.status_code)
            time.sleep(10 * attempt)
            continue
        resp.raise_for_status()
        rows = [{k: v["value"] for k, v in b.items()} for b in resp.json()["results"]["bindings"]]
        cache.put("wdqs", key, rows)
        logger.info("[WDQS] %s: %d dòng", name, len(rows))
        return rows
    raise RuntimeError(f"WDQS thất bại sau {attempts} lần: {name}")


def wiki_api(params, lang="vi", attempts=5):
    params = {"format": "json", "formatversion": 2, "maxlag": 5, **params}
    url = WIKI_API.format(lang=lang)
    for attempt in range(1, attempts + 1):
        _throttle("wiki")
        try:
            resp = SESSION.get(url, params=params, timeout=(10, 60))
        except requests.RequestException as e:
            logger.warning("[WIKI] lần %d lỗi mạng: %s", attempt, e)
            time.sleep(3 * attempt)
            continue
        if resp.status_code == 429:
            time.sleep(int(resp.headers.get("Retry-After", "10")))
            continue
        resp.raise_for_status()
        data = resp.json()
        err = data.get("error")
        if err and err.get("code") == "maxlag":
            wait = int(resp.headers.get("Retry-After", "5"))
            logger.info("[WIKI] maxlag, chờ %ss", wait)
            time.sleep(wait)
            continue
        if err:
            raise RuntimeError(f"MediaWiki API lỗi: {err}")
        return data
    raise RuntimeError("MediaWiki API thất bại sau nhiều lần thử")


def query_pages(kind, titles, params, cache, batch=50, lang="vi"):
    """{tiêu đề gốc: trang | None} cho action=query, theo lô và theo `continue`; cache theo (kind, tiêu đề)."""
    out, todo = {}, []
    for t in dict.fromkeys(titles):
        hit = cache.get(kind, t)
        if hit is not None:
            out[t] = hit.get("page")
        else:
            todo.append(t)
    if todo:
        cache.require_online(f"{kind}: {len(todo)} trang")
    for i in range(0, len(todo), batch):
        chunk = todo[i : i + batch]
        merged, cont = {}, {}
        alias = {t: t for t in chunk}  # tiêu đề gốc → tiêu đề sau khi chuẩn hoá và đi theo redirect
        while True:
            data = wiki_api({"action": "query", "titles": "|".join(chunk), **params, **cont}, lang=lang)
            q = data.get("query", {})
            for n in q.get("normalized", []) + q.get("redirects", []):
                for src, dst in alias.items():
                    if dst == n["from"]:
                        alias[src] = n["to"]
            for p in q.get("pages", []):
                cur = merged.setdefault(p["title"], {})
                for k, v in p.items():
                    if k in LIST_PROPS and isinstance(v, list):
                        cur.setdefault(k, []).extend(v)
                    elif k != "revisions" or "revisions" not in cur:
                        cur[k] = v
            if "continue" not in data:
                break
            cont = data["continue"]
        for src in chunk:
            page = merged.get(alias[src])
            if page is not None and page.get("missing"):
                page = None
            cache.put(kind, src, {"page": page})
            out[src] = page
        logger.info("[WIKI] %s: %d/%d trang", kind, min(i + batch, len(todo)), len(todo))
    return out
