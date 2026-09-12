"""The investigator agent's guardrails, tested without calling any model."""
import json

import pytest

from bt.agent.investigate import Tools, investigate, validate
from bt.datagen.generate import main as generate
from bt.pipeline.run import main as cli

SIG = {"S3-B1-RELATED_PARTY_INFLOW-aa": {"signal_id": "S3-B1-RELATED_PARTY_INFLOW-aa",
                                         "explanation": "$229,587 (31.7% of inflows) arrived from 'X Receivables LLC'"}}
CALLS = {"T2": {"id": "T2", "result": [{"secured_party_name": "Beacon Credit Fund LLC", "filed_month": -10}]}}


def test_lines_must_cite_real_sources_and_numbers_must_match():
    memo = "\n".join([
        "- $229,587 arrived from X Receivables LLC, 31.7% of inflows [S3-B1-RELATED_PARTY_INFLOW-aa].",
        "- Beacon Credit Fund LLC filed a lien [T2].",
        "- The borrower is clearly hiding money.",                       # no source
        "- A second lender is owed $4,000,000 [T2].",                    # number not in the source
        "- The shells were formed together [T9].",                       # tool call never made
        "- Roughly $231k came from the shell [S3-B1-RELATED_PARTY_INFLOW-aa].",   # 231k means 230,500-231,500: wrong
        "- About $230k came from the shell [S3-B1-RELATED_PARTY_INFLOW-aa].",     # 229,587 rounds to 230k: kept
        "- Ask the borrower: who owns X Receivables LLC?",               # a question may go uncited
        "- Ask the borrower: why $2M a month?",                          # ... unless it states numbers
    ])
    kept, dropped = validate(memo, SIG, CALLS)
    assert [k["cites"] for k in kept] == [["S3-B1-RELATED_PARTY_INFLOW-aa"], ["T2"], ["S3-B1-RELATED_PARTY_INFLOW-aa"], []]
    assert [d["reason"].split(":")[0] for d in dropped] == [
        "cites no source", "states a number not in its sources", "cites an unknown source",
        "states a number not in its sources", "cites no source"]


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    out = tmp_path_factory.mktemp("agent") / "book"
    generate(["--borrowers", "40", "--scale", "0.3", "--seed", "17", "--out", str(out)])
    cli(["--data", str(out), "--out", str(out / "run")])
    return out


def test_tools_read_the_book_and_bad_calls_come_back_as_errors(book):
    cases = json.load(open(book / "run" / "cases.json"))
    t = Tools(str(book), cases, live_gleif=False)
    b = cases[0]["borrower_id"]
    tid, ev = t.run("case_evidence", {"borrower_id": b})
    assert tid == "T1" and ev["verdict_by_rules"] == cases[0]["verdict"]
    _, rel = t.run("related_companies", {"borrower_id": b})
    assert rel[0]["is_borrower"]
    _, err = t.run("delete_everything", {})
    assert "error" in err
    _, err = t.run("payer_summary", {"borrower_id": b})  # missing argument
    assert "error" in err


def test_models_down_means_no_memo_and_the_case_stands(book):
    cases = json.load(open(book / "run" / "cases.json"))
    res = investigate(cases[0]["borrower_id"], Tools(str(book), cases, live_gleif=False), "x",
                      models=["m1", "m2"], router="http://127.0.0.1:9/v1/chat/completions")
    assert res["status"] == "unavailable" and res["memo"] == [] and len(res["errors"]) == 2
    assert res["verdict_by_rules"] == cases[0]["verdict"]
