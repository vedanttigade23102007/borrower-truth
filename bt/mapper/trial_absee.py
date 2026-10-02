"""The mapper on a real lender layout: SEC ABS-EE (Schedule AL), the loan-level file real auto lenders report to
investors every month. Run once; the result is published as it came out (proof/MAPPER_ABSEE_TRIAL.md).

1. A sample of real loans from one public trust is written as a CSV with the lender's own field names (the
   Schedule AL tags) and values written the way ABS-EE writes them (MM-DD-YYYY, MM/YYYY, days late).
2. The mapper suggests a mapping from the headers alone. It is scored against the right answers below, fixed
   before the run: right, wrong, missed, and correctly left for a person.
3. With a person's corrections and the values ABS-EE doesn't carry, the file is mapped and checked against a
   control total: the sum of the same loans' ending balances.

Caveats, stated with the result:
- The column names (bt/mapper/targets.py) were written before this run and not changed after it. Their author
  had seen these tags before, in bt/sec/absee.py.
- ABS-EE is a public investor report, not a borrowing-base spreadsheet sent to a bank.

    uv run python -m bt.mapper.trial_absee
"""
from __future__ import annotations

import csv
import datetime as dt
import glob
import os

import pyarrow.parquet as pq

from bt.mapper import run, suggest
from bt.sec.absee import FIELDS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "proof", "MAPPER_ABSEE_TRIAL.md")
N = 2000

# the right answer for each of our tape columns: the Schedule AL tag that holds it, or None when ABS-EE has nothing
# a person could map it from. Fixed before the run.
TRUTH = {
    "month": "reportingPeriodEndingDate", "asset_id": "assetNumber", "balance": "reportingPeriodActualEndBalanceAmount",
    "dpd_bucket_reported": "currentDelinquencyStatus", "orig_month": "originationDate",
    "orig_amount": "originalLoanAmount", "rate": "originalInterestRatePercentage", "term": "originalLoanTerm",
    "make": "vehicleManufacturerName", "model": "vehicleModelName", "model_year": "vehicleModelYear",
    "obligor_state": "obligorGeographicLocation", "credit_score": "obligorCreditScore",
    "facility_id": None, "vin": None, "obligor_id": None, "deferred_flag": None, "eligible_reported": None,
}


def _raw(col: str, v, t):
    """Write a parsed value back the way ABS-EE writes it."""
    if v is None:
        return ""
    if col == "period_end":  # YYYY-MM -> last day, MM-DD-YYYY
        y, m = map(int, v.split("-"))
        last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
        return f"{m:02d}-{last:02d}-{y}"
    if t == "my":  # YYYY-MM -> MM/YYYY
        y, m = v.split("-")
        return f"{m}/{y}"
    if t is bool:
        return "true" if v else "false"
    return repr(v) if isinstance(v, float) else str(v)


def main() -> None:
    src = sorted(glob.glob(os.path.join(ROOT, "data", "cache", "sec", "absee", "*.parquet")))[0]
    t = pq.read_table(src)
    period = max(t.column("period_end").to_pylist())
    rows = sorted((r for r in t.to_pylist() if r["period_end"] == period), key=lambda r: r["asset"])[:N]
    trust = rows[0]["trust"]
    tags = [tag for tag, _ in FIELDS.values()]
    work = os.path.join(ROOT, "data", "out", "mapper_trial")
    os.makedirs(work, exist_ok=True)
    path = os.path.join(work, "absee_sample.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(tags)
        for r in rows:
            w.writerow([_raw(col, r[col], ty) for col, (_, ty) in FIELDS.items()])

    got, left = suggest.suggest(tags, "tape", fixed={"borrower_id"})
    table, right, wrong, missed, kept_back = [], 0, 0, 0, 0
    for col, want in TRUTH.items():
        have = got.get(col, (None, None))[0]
        if want is None:
            verdict = "right: left for a person" if have is None else f"wrong: took '{have}'"
            kept_back += have is None
            wrong += have is not None
        elif have == want:
            verdict, right = "right", right + 1
        elif have is None:
            verdict, missed = "missed: a person maps it", missed + 1
        else:
            verdict, wrong = f"wrong: took '{have}'", wrong + 1
        table.append((col, want or "(none in ABS-EE)", have or "-", got.get(col, (None, "-"))[1], verdict))

    first = period  # month 0 = this report's month
    m = run.draft(path, "tape", "TRIAL", 1, first)
    m["columns"] = {k: dict(source=v, score="person") for k, v in TRUTH.items() if v}
    m["columns"]["obligor_id"] = dict(source="assetNumber", score="person")  # one loan per customer: ABS-EE has no ID
    m["constants"].update(facility_id="TRIAL-A", vin="", deferred_flag=0, eligible_reported=True)
    m = run.confirm(m, "Trial (Claude, for Vedant)")
    cert = {run.month_label(0, first): round(sum(r["end_bal"] or 0.0 for r in rows), 2)}
    res = run.map_file(path, m, os.path.join(work, "staging"), cert, os.path.join(work, "report.md"))

    n_map = sum(1 for v in TRUTH.values() if v)
    L = ["# The file mapper on a real lender layout (SEC ABS-EE)", "",
         f"Run once on {dt.date.today().isoformat()} (`bt/mapper/trial_absee.py`). **Real public data:** {len(rows):,} loans "
         f"from {trust}, report for {period}, as filed with the SEC. Not a borrowing-base spreadsheet: ABS-EE is the "
         f"loan-level report auto lenders file for investors, so it shows how real lenders name their fields.", "",
         "## 1. Suggesting from the headers alone", "",
         f"The file has {len(tags)} columns, named as the lender files them. Our loan tape has 18 columns a file could fill. "
         f"ABS-EE carries {n_map} of them; the other {len(TRUTH) - n_map} (VIN, customer ID, eligibility, deferral, "
         f"facility) aren't in ABS-EE at all.", "",
         f"- **Right:** {right} of {n_map}",
         f"- **Wrong:** {wrong} (a column filled from the wrong field)",
         f"- **Missed, for a person to map:** {missed}",
         f"- **Correctly left empty** (no ABS-EE field holds them): {kept_back} of {len(TRUTH) - n_map}", "",
         "| Our column | Right answer | Suggested | Score | Verdict |", "|---|---|---|---|---|"]
    L += [f"| `{a}` | {b} | {c} | {d} | {e} |" for a, b, c, d, e in table]
    L += ["", f"Lender columns left unused: {len(left)} ({', '.join(left)})", "",
          "## 2. Mapping the file, after a person's corrections", "",
          "A person fixes what the suggestion got wrong or missed, maps customer ID to the loan number (ABS-EE has "
          "no customer ID), and sets the values ABS-EE doesn't carry: facility, no VIN, not deferred, eligible.", "",
          f"- Result: **{'written' if res['written'] else 'stopped: ' + '; '.join(res['stops'])}**",
          f"- Rows read {res.get('rows_read', 0):,}, written {res.get('rows_written', 0):,}, rejected {res.get('rows_rejected', 0)}",
          f"- Control total (the same loans' ending balances): "
          + (f"off by ${res['tie_out'][0]['difference']:,.2f}" if res.get("tie_out") else "not reached"),
          f"- Formats guessed from the values: {m['formats']}"]
    for col, vals in res.get("blanked", {}).items():
        L.append(f"- {col}: {len(vals)} values outside the expected range left empty (e.g. {', '.join(sorted(set(vals))[:5])})")
    for e in res["rejected"][:10]:
        L.append(f"- Rejected row {e['row']}: {e['column']} = '{e['value']}' ({e['reason']})")
    L += ["", "## Caveats", "",
          "- The mapper's column names (`bt/mapper/targets.py`) were written before this run and not changed after it. "
          "Their author had seen these field names before, in `bt/sec/absee.py`, so this is not a fully blind test.",
          "- One trust, one month. Other lenders name fields differently; a borrowing-base spreadsheet sent to a bank "
          "may look nothing like this.", ""]
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
