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
        "- Ask the borrower: why $2M a month?",                          # ... but its numbers must be in the evidence
    ])
    kept, dropped = validate(memo, SIG, CALLS)
    assert [k["cites"] for k in kept] == [["S3-B1-RELATED_PARTY_INFLOW-aa"], ["T2"], ["S3-B1-RELATED_PARTY_INFLOW-aa"], []]
    assert [d["reason"].split(":")[0] for d in dropped] == [
        "cites no source", "states a number not in its sources", "cites an unknown source",
        "states a number not in its sources", "states a number not in its sources"]


FACTS = dict(borrower="lakeshore lending group", disclosed={"silverline credit fund"},
             borrower_liens=True, borrower_judgments=False,
             names=["lakeshore lending group", "silverline credit fund", "lakeshore receivables", "silverline credit"])


def test_claims_are_checked_against_the_records():
    memo = "\n".join([
        "- The borrower has undisclosed debt to Silverline Credit Fund LLC [T2].",      # it was disclosed
        "- The borrower disclosed Lakeshore Receivables LLC as an affiliate [T2].",      # it was not
        "- Lakeshore Receivables LLC was never disclosed to the bank [T2].",             # true: kept
        "- No public liens or judgments were found against the borrower [T2].",          # there are liens
        "- The borrower disclosed a facility with Silverline Credit Fund LLC [T2].",     # true; 'Silverline Credit' is a
        "- No court judgments were found against the borrower [T2].",                    #   different company. true: kept
        "- Could not confirm whether the lien affects repayment [T2].",                  # not a claim of absence: kept
        "- The disclosures do not mention Lakeshore Receivables LLC [T2].",              # a negative claim, true: kept
    ])
    kept, dropped = validate(memo, SIG, CALLS, FACTS)
    assert [k["text"] for k in kept] == ["Lakeshore Receivables LLC was never disclosed to the bank",
                                         "The borrower disclosed a facility with Silverline Credit Fund LLC",
                                         "No court judgments were found against the borrower",
                                         "Could not confirm whether the lien affects repayment",
                                         "The disclosures do not mention Lakeshore Receivables LLC"]
    assert [d["reason"].split(",")[0] for d in dropped] == [
        "says 'silverline credit fund' was not disclosed", "says 'lakeshore receivables' was disclosed",
        "says there are no liens"]


def test_glued_or_garbled_citations_resolve_to_the_real_signal():
    sig = {"S3-B1-RELATED_PARTY_INFLOW-3a0eb607": SIG["S3-B1-RELATED_PARTY_INFLOW-aa"]}
    memo = "- $229,587 came from X Receivables LLC [T1-S3-B1-RELATED_PARTY_INFLOW-3a0eb607].\n" \
           "- $229,587 came from X Receivables LLC [S5-B1-WRONG_TYPE-3a0eb607].\n" \
           "- Ask the borrower: why did X Receivables LLC send $229,587?"
    kept, dropped = validate(memo, sig, {})
    assert [k["cites"] for k in kept] == [["S3-B1-RELATED_PARTY_INFLOW-3a0eb607"]] * 2 + [[]] and not dropped


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
    _, liens = t.run("lien_search", {"name": b})  # an ID is searched by the borrower's legal name
    assert b not in json.dumps(liens)
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
