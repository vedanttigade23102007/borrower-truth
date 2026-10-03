"""The file mapper (INTEGRATION.md, section 3): untrusted files read safely, columns suggested, values converted,
every check, and a round trip: a synthetic book with realistic loan, credit-line and borrower IDs, written out as messy
lender spreadsheets and mapped back, gives exactly the same cases."""
import csv
import datetime as dt
import json
import math
import shutil
import zipfile

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bt.datagen.generate import main as generate
from bt.mapper import convert, readfile, run, suggest
from bt.pipeline.run import run as pipeline

FIRST = "2024-01"


# ---------- reading untrusted files ----------
def _xlsx(path, rows, title=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title or "Sheet1"
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_macro_workbooks_are_refused_by_name_and_by_content(tmp_path):
    with pytest.raises(readfile.Refused):
        readfile.rows(str(tmp_path / "tape.xlsm"))
    p = _xlsx(tmp_path / "tape.xlsx", [["a"], [1]])
    with zipfile.ZipFile(p, "a") as z:  # an .xlsm renamed to .xlsx still carries its macro project
        z.writestr("xl/vbaProject.bin", b"macro")
    with pytest.raises(readfile.Refused, match="macro"):
        readfile.rows(str(p))


def test_oversized_files_and_zip_bombs_are_refused(tmp_path):
    p = _xlsx(tmp_path / "t.xlsx", [["a"]] + [["x" * 200] for _ in range(200)])
    with pytest.raises(readfile.Refused, match="limit"):
        readfile.rows(str(p), max_bytes=1000)
    with pytest.raises(readfile.Refused, match="unpacks"):
        readfile.rows(str(p), max_unpacked=1000)


def test_formulas_are_never_read_as_text_or_run(tmp_path):
    p = _xlsx(tmp_path / "t.xlsx", [["Loan Number", "Balance"], ["L1", "=1+1"]])
    rows = readfile.rows(str(p))
    assert rows[1][1] is None  # no saved value: empty, and the checks reject the row; never "=1+1", never 2


# ---------- suggesting ----------
def test_lender_headers_are_suggested_onto_our_columns():
    headers = ["Loan Number", "Reporting Date", "Beginning Balance", "Cur. Bal", "Days Past Due", "Eligible (Y/N)",
               "Orig Bal", "Interest Rate", "VIN", "Customer No.", "Zero Balance Code", "Branch"]
    got, left = suggest.suggest(headers, "tape", fixed={"borrower_id"})
    want = {"asset_id": "Loan Number", "month": "Reporting Date", "balance": "Cur. Bal",
            "dpd_bucket_reported": "Days Past Due", "eligible_reported": "Eligible (Y/N)", "orig_amount": "Orig Bal",
            "rate": "Interest Rate", "vin": "VIN", "obligor_id": "Customer No."}
    assert {k: v[0] for k, v in got.items() if k in want} == want
    assert "Beginning Balance" in left and "Zero Balance Code" in left and "Branch" in left


# ---------- converting ----------
def test_values_convert_the_way_a_lender_writes_them():
    assert convert.money("$1,234.56") == 1234.56 and convert.money("(10.00)") == -10.0
    assert convert.terms("Net 30") == 30 and convert.terms(45) == 45
    assert [convert.dpd(d, "days") for d in (0, 29, 30, 59, 60, 89, 90, 400)] == [0, 0, 1, 1, 2, 2, 3, 3]
    assert convert.dpd("30-59", "text") == 1
    assert math.isclose(convert.rate("5.25%", "decimal"), 0.0525) and convert.rate(0.07, "decimal") == 0.07
    assert convert.boolean("Y") is True and convert.boolean("Ineligible") is False
    assert convert.text(12345.0) == "12345" and convert.ident("00123") == "00123"
    assert convert.date("03/31/2024") == dt.date(2024, 3, 31) and convert.date("2024-03") == dt.date(2024, 3, 1)
    assert convert.month_index(dt.date(2024, 3, 31), FIRST) == 2
    with pytest.raises(convert.Bad):
        convert.money("see note")


def test_total_rows_are_dropped_but_a_customer_called_total_is_kept():
    assert convert.is_total_row(["Total", "", 1000.0], 0)
    assert convert.is_total_row(["", "Grand Total", 5000.0], 0)
    assert not convert.is_total_row(["INV-1", "Total Logistics Inc", 100.0], 0)


# ---------- every check ----------
HEAD = ["Loan Number", "Reporting Date", "Facility", "VIN", "Customer No.", "Current Principal Balance",
        "Days Past Due", "Deferred", "Eligible (Y/N)"]


def _tape_csv(path, rows, head=HEAD):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    return str(path)


def _rows(n, month="03/31/2024"):
    return [[f"L{i:04d}", month, "F1A", f"VIN{i}", f"C{i}", "$1,000.00", "0", "No", "Y"] for i in range(n)]


def _mapping(path, **kw):
    m = run.draft(path, "tape", "B0001", 1, FIRST)
    return run.confirm(m, "Test Officer") if kw.get("confirm", True) else m


def test_an_unconfirmed_mapping_never_runs(tmp_path):
    p = _tape_csv(tmp_path / "t.csv", _rows(10))
    res = run.map_file(p, _mapping(p, confirm=False), str(tmp_path / "s"), {"2024-03": 10000.0})
    assert not res["written"] and "confirmed" in res["stops"][0]
    with pytest.raises(run.Stop):
        run.confirm(run.draft(p, "tape", "B0001", 1, FIRST), "unknown")


@pytest.mark.parametrize("total,written", [(10000.0, True), (10000.99, True), (10002.0, False), (None, False)])
def test_the_amounts_must_add_up_to_the_certificate(tmp_path, total, written):
    p = _tape_csv(tmp_path / "t.csv", _rows(10))
    res = run.map_file(p, _mapping(p), str(tmp_path / "s"), None if total is None else {"2024-03": total},
                       str(tmp_path / "r.md"))
    assert res["written"] is written
    if not written:
        assert (tmp_path / "r.md").read_text().count("STOPPED") == 1


@pytest.mark.parametrize("bad,written", [(1, True), (2, False)])
def test_over_one_percent_unreadable_stops_and_every_row_is_listed(tmp_path, bad, written):
    rows = _rows(100)
    for i in range(bad):
        rows[10 + i][5] = "see note"
    p = _tape_csv(tmp_path / "t.csv", rows)
    good = 1000.0 * (100 - bad)
    res = run.map_file(p, _mapping(p), str(tmp_path / "s"), {"2024-03": good}, str(tmp_path / "r.md"))
    assert res["written"] is written
    assert [e["row"] for e in res["rejected"]] == [12 + i for i in range(bad)]
    assert "see note" in (tmp_path / "r.md").read_text()


def test_a_renamed_column_stops_with_a_clear_message(tmp_path):
    p = _tape_csv(tmp_path / "t.csv", _rows(10))
    m = _mapping(p)
    q = _tape_csv(tmp_path / "next.csv", _rows(10), [h if h != "Days Past Due" else "DPD Days" for h in HEAD])
    res = run.map_file(q, m, str(tmp_path / "s"), {"2024-03": 10000.0})
    assert not res["written"] and "layout changed" in res["stops"][0] and "Days Past Due" in res["stops"][0]


def test_a_row_listed_twice_is_kept_and_flagged_not_dropped(tmp_path):
    rows = _rows(10)
    rows.append(list(rows[3]))
    p = _tape_csv(tmp_path / "t.csv", rows)
    res = run.map_file(p, _mapping(p), str(tmp_path / "s"), {"2024-03": 11000.0})
    assert res["written"] and res["rows_written"] == 11 and res["duplicates"]


# ---------- the round trip ----------
DAYS = {0: 0, 1: 45, 2: 75, 3: 120}
TAPE_HEAD = ["Loan Number", "Reporting Date", "Facility", "VIN", "Customer No.", "Current Principal Balance",
             "Days Past Due", "Deferred", "Eligible (Y/N)", "Origination Date", "Original Loan Amount",
             "Interest Rate", "Term (Months)", "Make", "Model", "Model Year", "State", "FICO", "Branch", "Notes"]
TRUTH_HEAD = ["Account Number", "Period End", "Days Delinquent", "Principal Balance"]
INV_HEAD = ["Record ID", "Facility", "Report Date", "Invoice #", "PO Number", "Customer ID", "Customer Name",
            "Invoice Date", "Terms", "Invoice Amount", "Description"]


def _month_end(m):
    t = 2024 * 12 + m
    y, mo = divmod(t, 12)
    nxt = dt.date(y + (mo == 11), (mo + 1) % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


def _day(m, d):
    y, mo = divmod(2024 * 12 + m, 12)
    return dt.date(y, mo + 1, d)


def _cents(book):
    """Amounts in cents, as a lender's file holds them: the baseline every mapped value must equal."""
    for t, cols in (("tape", ("balance", "orig_amount")), ("source_truth", ("balance_true",)), ("invoices", ("amount",))):
        tbl = pq.read_table(book / f"{t}.parquet")
        for c in cols:
            i = tbl.schema.get_field_index(c)
            tbl = tbl.set_column(i, c, pa.array([round(float(x), 2) for x in tbl[c].to_pylist()],
                                                type=tbl.schema.field(c).type))
        pq.write_table(tbl, book / f"{t}.parquet")


def _write(path, head, rows, xlsx, title=None, subtotal_col=None, month_col=None):
    """A lender-style file: xlsx with a title row, a blank row and month subtotals, or a plain CSV with $ text."""
    if not xlsx:
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(head)
            w.writerows(rows)
        return 1
    out = [[title], [], head]
    if subtotal_col is not None:
        cur, s = None, 0.0
        for r in rows + [None]:
            m = None if r is None else r[month_col]
            if cur is not None and m != cur:
                out.append(["Total"] + [""] * (subtotal_col - 1) + [round(s, 2)])
                s = 0.0
            if r is None:
                break
            out.append(r)
            cur, s = m, s + (r[subtotal_col] if isinstance(r[subtotal_col], (int, float)) else 0.0)
        out.append(["Grand Total"])
    else:
        out += rows
    _xlsx(path, out)
    return 3


@pytest.fixture(scope="module")
def roundtrip(tmp_path_factory):
    from rename_ids import rename
    root = tmp_path_factory.mktemp("rt")
    gen = root / "generated"
    generate(["--borrowers", "30", "--scale", "0.2", "--seed", "13", "--out", str(gen)])
    _cents(gen)
    base = root / "base"  # realistic, random loan, credit-line and borrower IDs, as a lender's files would carry
    rename(str(gen), str(base))
    tape, truth, inv = (pq.read_table(base / f"{t}.parquet").to_pylist() for t in ("tape", "source_truth", "invoices"))
    files, junk = [], []
    staging = root / "staging"
    by_b = lambda rows: sorted({r["borrower_id"] for r in rows})  # noqa: E731
    for n, b in enumerate(by_b(tape)):
        xlsx = n % 2 == 0
        mine = sorted((r for r in tape if r["borrower_id"] == b), key=lambda r: (r["month"], r["asset_id"]))
        rows = [[r["asset_id"], _month_end(r["month"]) if xlsx else _month_end(r["month"]).strftime("%m/%d/%Y"),
                 r["facility_id"], r["vin"], r["obligor_id"],
                 r["balance"] if xlsx else f"${r['balance']:,.2f}", DAYS[r["dpd_bucket_reported"]],
                 "Yes" if r["deferred_flag"] else "No", "Y" if r["eligible_reported"] else "N",
                 _month_end(r["orig_month"]) if xlsx else _month_end(r["orig_month"]).strftime("%m/%d/%Y"),
                 r["orig_amount"] if xlsx else f"{r['orig_amount']:.2f}",
                 None if r["rate"] is None or math.isnan(r["rate"]) else (r["rate"] if xlsx else repr(r["rate"])),
                 r["term"] or None, r["make"], r["model"], r["model_year"] or None, r["obligor_state"], r["credit_score"],
                 "Main", ""] for r in mine]
        if n < 5:  # one unreadable line in five files: not a loan, not in the certificate, must be listed
            bad = list(rows[0])
            bad[0], bad[5] = f"JUNK-{b}", "see note"
            rows.insert(len(rows) // 2, bad)
            junk.append(f"JUNK-{b}")
        ext = "xlsx" if xlsx else "csv"
        p = root / f"{b}_tape.{ext}"
        hr = _write(p, TAPE_HEAD, rows, xlsx, f"{b} monthly loan tape (synthetic)", 5, 1)
        totals = {}
        for r in mine:
            k = run.month_label(r["month"], FIRST)
            totals[k] = totals.get(k, 0.0) + r["balance"]
        files.append((p, "tape", b, hr, totals))
        mt = sorted((r for r in truth if r["borrower_id"] == b), key=lambda r: (r["month"], r["asset_id"]))
        p = root / f"{b}_servicer.csv"
        _write(p, TRUTH_HEAD, [[r["asset_id"], _month_end(r["month"]).isoformat(), r["dpd_bucket_true"],
                                f"{r['balance_true']:.2f}"] for r in mt], False)
        files.append((p, "source_truth", b, 1, None))
    for n, b in enumerate(by_b(inv)):
        xlsx = n % 2 == 1
        mine = [r for r in inv if r["borrower_id"] == b]
        rows = [[r["invoice_id"], r["facility_id"],
                 _month_end(r["pledged_month"]) if xlsx else _month_end(r["pledged_month"]).strftime("%m/%d/%Y"),
                 r["invoice_number"], r["po_number"], r["debtor_id"], r["debtor_name"],
                 _day(r["issue_month"], r["issue_day"]) if xlsx else _day(r["issue_month"], r["issue_day"]).strftime("%m/%d/%Y"),
                 f"Net {r['due_days']}", r["amount"] if xlsx else f"${r['amount']:,.2f}", r["description"]]
                for r in mine]
        ext = "xlsx" if xlsx else "csv"
        p = root / f"{b}_invoices.{ext}"
        hr = _write(p, INV_HEAD, rows, xlsx, f"{b} schedule of receivables (synthetic)")
        totals = {}
        for r in mine:
            k = run.month_label(r["pledged_month"], FIRST)
            totals[k] = totals.get(k, 0.0) + r["amount"]
        files.append((p, "invoices", b, hr, totals))
    results = []
    for p, table, b, hr, totals in files:
        m = run.confirm(run.draft(str(p), table, b, hr, FIRST), "Test Officer")
        results.append((table, b, m, run.map_file(str(p), m, str(staging), totals, str(root / f"{p.name}.md"))))
    mapped = root / "mapped"
    shutil.copytree(base, mapped)
    for t in ("tape", "source_truth", "invoices"):
        run.assemble(str(staging), t, str(mapped))
    return dict(base=base, mapped=mapped, results=results, junk=junk, root=root)


def test_the_round_trip_suggests_every_column_right(roundtrip):
    want = {"tape": dict(zip(["asset_id", "month", "facility_id", "vin", "obligor_id", "balance",
                              "dpd_bucket_reported", "deferred_flag", "eligible_reported", "orig_month", "orig_amount",
                              "rate", "term", "make", "model", "model_year", "obligor_state", "credit_score"], TAPE_HEAD)),
            "source_truth": dict(zip(["asset_id", "month", "dpd_bucket_true", "balance_true"], TRUTH_HEAD)),
            "invoices": dict(zip(["invoice_id", "facility_id", "pledged_month", "invoice_number", "po_number",
                                  "debtor_id", "debtor_name", "issue_date", "due_days", "amount", "description"], INV_HEAD))}
    for table, b, m, _ in roundtrip["results"]:
        assert {k: v["source"] for k, v in m["columns"].items()} == want[table], (table, b)


def test_the_round_trip_writes_every_file_and_lists_every_junk_line(roundtrip):
    for table, b, _, res in roundtrip["results"]:
        assert res["written"], (table, b, res["stops"])
    rejected = [e for *_, res in roundtrip["results"] for e in res["rejected"]]
    assert len({e["row"] for e in rejected}) == len(roundtrip["junk"]) == 5
    reports = "".join(p.read_text() for p in roundtrip["root"].glob("*_tape.*.md"))
    assert reports.count("'see note' is not an amount") == 5


def test_the_round_trip_gives_the_same_tables_and_the_same_cases(roundtrip):
    for t in ("tape", "source_truth", "invoices"):
        a = pq.read_table(roundtrip["base"] / f"{t}.parquet")
        b = pq.read_table(roundtrip["mapped"] / f"{t}.parquet")
        assert a.schema == b.schema, t
        key = [("borrower_id", "ascending"), ("month", "ascending"), ("asset_id", "ascending")] if t != "invoices" \
            else [("invoice_id", "ascending")]
        ra, rb = a.sort_by(key).to_pylist(), b.sort_by(key).to_pylist()
        if t == "tape":  # the generator marks "not applicable" with NaN or 0; a lender leaves the cell empty (null)
            ra = [dict(r, rate=None if r["rate"] is not None and math.isnan(r["rate"]) else r["rate"],
                       term=r["term"] or None, model_year=r["model_year"] or None) for r in ra]
        assert ra == rb, t
    _, ca, _ = pipeline(str(roundtrip["base"]), 23)
    _, cb, _ = pipeline(str(roundtrip["mapped"]), 23)
    # the input files are different bytes, so their fingerprint differs; every clue, finding, verdict and result
    # digest must not
    assert {c["decision"]["inputs_digest"] for c in ca} != {c["decision"]["inputs_digest"] for c in cb}
    strip = lambda cs: json.dumps([dict(c, decision={k: v for k, v in c["decision"].items() if k != "inputs_digest"})  # noqa: E731
                                   for c in cs], sort_keys=True, default=str)
    assert strip(ca) == strip(cb)


@pytest.mark.parametrize("calendar,flagged", [(None, False), ({"months": 24}, True), ({"months": 36}, False)])
def test_the_data_check_uses_the_books_own_calendar(tmp_path, calendar, flagged):
    from bt.pipeline import dq
    t = pa.table({"month": pa.array([0, 30], pa.int16()), "borrower_id": ["B1", "B1"], "asset_id": ["A1", "A1"],
                  "dpd_bucket_true": pa.array([0, 0], pa.int8()), "balance_true": pa.array([1.0, 1.0], pa.float32())})
    pq.write_table(t, tmp_path / "source_truth.parquet")
    if calendar:
        (tmp_path / "calendar.json").write_text(json.dumps(calendar))
    issues = dq.check(str(tmp_path / "source_truth.parquet"), "source_truth", dq.last_month(str(tmp_path)))
    assert bool(issues) is flagged
