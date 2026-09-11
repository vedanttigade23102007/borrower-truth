"""Live GLEIF adapter: real "who owns whom" data, with a cache and a stale fallback.

This is the production path for S6's ownership input (design §7, §12). GLEIF's
API is public and free (VERIFY D1). The synthetic book's companies are, of
course, not in GLEIF; this adapter is proven against real companies.

Fallback (design §12, "public data source is down"): every response is cached
on disk. If GLEIF can't be reached, the cached answer is served with
stale=True and the time it was fetched. With no cache, GleifUnavailable is raised
and S6 reports reduced coverage instead of failing.

    uv run python -m bt.adapters.gleif "Wells Fargo & Company"
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.gleif.org/api/v1"
CACHE_DIR = os.environ.get("BT_CACHE_DIR", os.path.join("data", "cache", "gleif"))
TTL_S = 7 * 24 * 3600


class GleifUnavailable(Exception):
    pass


def _get(url: str, timeout: float = 10.0) -> tuple[dict, bool, float]:
    """Returns (json, stale, fetched_at). Fresh cache first, then network, then stale cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, hashlib.sha1(url.encode()).hexdigest() + ".json")
    cached = json.load(open(path)) if os.path.exists(path) else None
    if cached and time.time() - cached["fetched_at"] < TTL_S:
        return cached["body"], False, cached["fetched_at"]
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.api+json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as he:
            if he.code != 404:
                raise
            body = {"data": None}  # GLEIF answers 404 when there is simply nothing to report (e.g. no parent)
        now = time.time()
        json.dump({"url": url, "fetched_at": now, "body": body}, open(path, "w"))
        return body, False, now
    except Exception as e:
        if cached:
            return cached["body"], True, cached["fetched_at"]
        raise GleifUnavailable(f"{type(e).__name__}: {e}") from e


def _record(d: dict) -> dict:
    a = d.get("attributes", {})
    ent = a.get("entity", {})
    return dict(lei=a.get("lei") or d.get("id"), name=ent.get("legalName", {}).get("name"),
                status=ent.get("status"), country=ent.get("legalAddress", {}).get("country"),
                registration=a.get("registration", {}).get("status"))


def parents(lei: str) -> dict:
    out, stale_any = {}, False
    for rel in ("direct-parent", "ultimate-parent"):
        try:
            body, stale, _ = _get(f"{API}/lei-records/{lei}/{rel}")
            stale_any |= stale
            data = body.get("data")
            out[rel.replace("-", "_")] = _record(data) if isinstance(data, dict) else None
        except GleifUnavailable:
            raise
        except Exception:
            out[rel.replace("-", "_")] = None  # 404 = no parent reported
    out["stale"] = stale_any
    return out


def lookup(name: str, limit: int = 3) -> dict:
    # exact legal name first (how a credit file names a borrower); full-text search only as a fallback
    q = urllib.parse.urlencode({"filter[entity.legalName]": name, "page[size]": limit})
    body, stale, fetched = _get(f"{API}/lei-records?{q}")
    match = "exact legal name"
    if not body.get("data"):
        q = urllib.parse.urlencode({"filter[fulltext]": name, "page[size]": limit})
        body, stale, fetched = _get(f"{API}/lei-records?{q}")
        match = "full-text (no exact legal-name match)"
    # active registrations first
    data = sorted(body.get("data") or [], key=lambda d: d.get("attributes", {}).get("entity", {}).get("status") != "ACTIVE")
    records = []
    for d in data[:limit]:
        r = _record(d)
        try:
            p = parents(r["lei"])
            stale = stale or p.pop("stale")
            r.update(p)
        except GleifUnavailable:
            r.update(direct_parent=None, ultimate_parent=None, parents_unavailable=True)
        records.append(r)
    return dict(query=name, match=match, records=records, source="cache" if stale else "live", stale=stale,
                fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(fetched)))


if __name__ == "__main__":
    print(json.dumps(lookup(" ".join(sys.argv[1:]) or "Wells Fargo & Company"), indent=1))
