"""Nothing leaves the bank unless someone switches it on (INTEGRATION.md, section 1).

One setting, BT_OFFLINE, is on by default. While it is on:
- the public lookups are blocked: GLEIF (bt/adapters/gleif.py) and SEC EDGAR (bt/sec/edgar.py); their on-disk
  caches still work
- the investigator agent can't call hosted models, and its local model loads only from files already on disk
- DuckDB doesn't download extensions
Set BT_OFFLINE=0 to allow them, for example to refresh public data or on the free research GPUs (synthetic data).
Calls inside the bank (the case service, Kafka, the metrics gateway) are not affected.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

SETTING = "BT_OFFLINE"


class Offline(RuntimeError):
    """An outside call was blocked because BT_OFFLINE is on."""


def offline() -> bool:
    return os.environ.get(SETTING, "1").strip().lower() not in ("0", "false", "no", "off")


def message(what: str, url: str = "") -> str:
    host = urlparse(url).netloc if url else ""
    return (f"{what}{f' ({host})' if host else ''} is blocked: nothing leaves the bank while {SETTING} is on, "
            f"which is the default. Set {SETTING}=0 to allow it")


def require(what: str, url: str = "") -> None:
    if offline():
        raise Offline(message(what, url))


def duckdb_config() -> dict:
    """DuckDB fetches a missing extension from the internet unless told not to."""
    return {"autoinstall_known_extensions": False} if offline() else {}
