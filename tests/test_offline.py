"""Nothing leaves the bank by default (bt/common/network.py, INTEGRATION.md section 1).

The pipeline is run with outbound network blocked twice: inside Python, where an audit hook records and refuses
every connection or name lookup (even one some code might catch and hide), and, on macOS, inside an operating-system
sandbox that denies the whole process any network, which also covers DuckDB's own C++ code."""
import json
import os
import shutil
import subprocess
import sys

import duckdb
import pytest

from bt.common import network
from bt.datagen.generate import main as generate
from bt.pipeline.run import main as pipeline_main

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NET_EVENTS = {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr", "socket.sendto",
              "urllib.Request", "http.client.connect"}
BLOCK, SEEN = [False], []


def _hook(event, args):
    if BLOCK[0] and event in NET_EVENTS:
        SEEN.append((event, repr(args)[:120]))
        raise PermissionError(f"outbound network blocked in this test: {event}")


sys.addaudithook(_hook)  # an audit hook can't be removed; it only acts while BLOCK is set


@pytest.fixture()
def blocked(monkeypatch):
    monkeypatch.delenv(network.SETTING, raising=False)  # the default
    SEEN.clear()
    BLOCK[0] = True
    yield SEEN
    BLOCK[0] = False


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("offline") / "book"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(out)])
    return out


def test_offline_is_the_default(monkeypatch):
    monkeypatch.delenv(network.SETTING, raising=False)
    assert network.offline()
    monkeypatch.setenv(network.SETTING, "0")
    assert not network.offline()


def test_the_pipeline_runs_with_outbound_network_blocked(book, tmp_path, blocked):
    work = tmp_path / "book"
    shutil.copytree(book, work)
    pipeline_main(["--data", str(work)])
    BLOCK[0] = False
    cases = json.load(open(work / "run" / "cases.json"))
    assert len(cases) == 30
    assert blocked == [], blocked  # nothing even tried to call out


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("sandbox-exec"), reason="macOS sandbox only")
def test_the_pipeline_runs_in_an_os_sandbox_with_no_network(book, tmp_path):
    work = tmp_path / "book"
    shutil.copytree(book, work)
    env = {k: v for k, v in os.environ.items() if k != network.SETTING}
    p = subprocess.run(["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", sys.executable, "-m",
                        "bt.pipeline.run", "--data", str(work)], cwd=ROOT, env=env, capture_output=True, text=True,
                       timeout=600)
    assert p.returncode == 0, p.stderr[-2000:]
    assert len(json.load(open(work / "run" / "cases.json"))) == 30


def test_public_lookups_and_hosted_models_are_blocked_by_default(tmp_path, monkeypatch, blocked):
    from bt.adapters import gleif
    from bt.agent import investigate
    from bt.sec import edgar
    monkeypatch.setattr(gleif, "CACHE_DIR", str(tmp_path / "gleif"))
    with pytest.raises(network.Offline, match="SEC EDGAR"):
        edgar._open("https://www.sec.gov/cgi-bin/browse-edgar")
    with pytest.raises(gleif.GleifUnavailable, match=network.SETTING):
        gleif._get(gleif.API + "/lei-records?filter[entity.legalName]=X")
    with pytest.raises(network.Offline, match="hosted model"):
        investigate.chat("any-model", [{"role": "user", "content": "hi"}], None, "token")
    with pytest.raises(SystemExit, match=network.SETTING):
        investigate.main(["--backend", "hf", "--data", str(tmp_path)])
    assert blocked == []  # refused by the setting, before any connection


def test_the_setting_lets_a_public_lookup_through_when_switched_on(tmp_path, monkeypatch):
    from bt.adapters import gleif

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"data": []}'

    monkeypatch.setenv(network.SETTING, "0")
    monkeypatch.setattr(gleif, "CACHE_DIR", str(tmp_path / "gleif"))
    monkeypatch.setattr(gleif.urllib.request, "urlopen", lambda req, timeout=None: Reply())
    body, stale, _ = gleif._get(gleif.API + "/lei-records?filter[entity.legalName]=X")
    assert body == {"data": []} and not stale


def test_duckdb_never_downloads_extensions_offline(monkeypatch, book):
    from bt.systems.base import Ctx
    monkeypatch.delenv(network.SETTING, raising=False)
    ctx = Ctx(str(book), 23)
    assert ctx.con.execute("SELECT current_setting('autoinstall_known_extensions')").fetchone()[0] is False
    monkeypatch.setenv(network.SETTING, "0")
    assert duckdb.connect(config=network.duckdb_config()).execute(
        "SELECT current_setting('autoinstall_known_extensions')").fetchone()[0] is True


# the controls: the blockers above must actually catch an attempt, or "nothing called out" would prove nothing
def test_control_the_audit_hook_catches_an_attempt(blocked):
    import urllib.request
    with pytest.raises(PermissionError):
        urllib.request.urlopen("http://192.0.2.1/", timeout=1)  # TEST-NET-1: reserved, never routed
    BLOCK[0] = False
    assert blocked and blocked[0][0] in NET_EVENTS


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("sandbox-exec"), reason="macOS sandbox only")
def test_control_the_sandbox_refuses_a_connection():
    code = ("import errno, socket\n"
            "try:\n    socket.create_connection(('192.0.2.1', 80), timeout=2)\n"
            "except OSError as e:\n    print(e.errno)\n")
    p = subprocess.run(["sandbox-exec", "-p", "(version 1)(allow default)(deny network*)", sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=60)
    import errno
    assert p.stdout.strip() == str(errno.EPERM), (p.stdout, p.stderr)  # refused by the sandbox, not a timeout
