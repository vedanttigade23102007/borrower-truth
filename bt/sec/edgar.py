"""A polite EDGAR client: a declared User-Agent, at most 5 requests a second, an on-disk cache.

SEC fair-access rules: automated requests must declare a User-Agent with a contact
email, and stay under 10 requests a second
(https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).
The contact email is used for SEC requests only; Vedant approved it on 14 Sep 2026.
"""
from __future__ import annotations

import gzip
import json
import os
import time
import urllib.error
import urllib.request

UA = "Vedant Tigade research your-email@example.com"
CACHE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", "sec")
MIN_GAP = 0.2  # seconds between requests: 5/s, half the SEC's limit
_last = [0.0]


def _open(url: str):
    wait = MIN_GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    for attempt in range(5):
        try:
            _last[0] = time.time()
            return urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < 4:
                time.sleep(2 ** attempt * 2)
                continue
            raise


def cache_path(url: str) -> str:
    rel = url.split("://", 1)[1].replace("/", "_")
    return os.path.abspath(os.path.join(CACHE, "http", rel[:200]))


def get(url: str, cache: bool = True) -> bytes:
    """Small documents (indexes, JSON). Cached on disk."""
    p = cache_path(url)
    if cache and os.path.exists(p):
        return open(p, "rb").read()
    r = _open(url)
    body = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    if cache:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(body)
    return body


def get_json(url: str, cache: bool = True):
    return json.loads(get(url, cache))


def download(url: str, dest: str) -> str:
    """Large files (loan-level XML), streamed to disk; skipped if already there."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = _open(url)
    gz = r.headers.get("Content-Encoding") == "gzip"
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        src = gzip.GzipFile(fileobj=r) if gz else r
        while chunk := src.read(1 << 20):
            f.write(chunk)
    os.replace(tmp, dest)
    return dest
