"""Map one borrower file onto one of our tables, check it, and write it with a report a person signs.

Order of work for a new lender (INTEGRATION.md, section 3):
  inspect  -> a person picks the sheet and the header row
  suggest  -> a draft mapping, with a score for every column
  confirm  -> a person checks the draft and puts their name on it; an unconfirmed mapping never runs
  map      -> every month: read, convert, check, write, report
  assemble -> the mapped files of one table become the table the checks read

`map` writes nothing unless every check passes: required columns present, at most 1% of rows rejected (every
rejected row listed), and the amounts adding up to the borrower's own certificate total within $1. A row that
appears twice is kept and flagged, never dropped: it may be the evidence (an invoice resubmitted with a new amount).
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
from collections import defaultdict

import pyarrow as pa
import pyarrow.parquet as pq

from bt.mapper import convert, readfile, suggest
from bt.mapper.targets import AMOUNT_COL, ID_COL, KEY, MONTH_COL, TABLES, out_schema

MAX_REJECTED = 0.01
TIE_OUT = 1.00  # dollars
NOT_NEGATIVE = {"balance", "balance_true", "amount", "orig_amount"}
# industry credit scores (FICO Auto and Bankcard) run 250-900; real SEC loan records also carry 0 and 999 for "no score"
RANGES = {"credit_score": (250, 900), "term": (1, 600), "model_year": (1950, 2100), "due_days": (0, 365)}
FALSE_NAMES = {"", "unknown", "n/a", "none", "test", "admin"}
MAY_BE_EMPTY = {"vin"}  # loans with no vehicle have none


class Stop(Exception):
    """The file was not mapped. The report says why."""


# ---------- mappings ----------
def draft(path: str, table: str, borrower_id: str, header_row: int, first_month: str, sheet: str | None = None,
          constants: dict | None = None) -> dict:
    if table not in TABLES:
        raise ValueError(f"unknown table '{table}' (one of {', '.join(TABLES)})")
    dt.date.fromisoformat(first_month + "-01")
    grid = readfile.rows(path, sheet)
    header = grid[header_row - 1]
    constants = dict(constants or {})
    constants["borrower_id"] = borrower_id
    found, left = suggest.suggest(header, table, fixed=set(constants))
    data = [r for r in grid[header_row:] if not all(convert.is_empty(c) for c in r)]
    return dict(
        version=1, table=table, borrower_id=borrower_id,
        file=dict(kind=readfile.kind_of(path), sheet=sheet, header_row=header_row),
        calendar=dict(first_month=first_month),
        columns={k: dict(source=h, score=s) for k, (h, s) in found.items()},
        constants=constants,
        formats=suggest.guess_formats(table, found, header, data),
        headers_seen=[convert.text(h) for h in header if convert.text(h)],
        not_used=left,
        needs_a_person=missing(table, found, constants),
        confirmed_by=None, confirmed_on=None)


def missing(table: str, columns: dict, constants: dict) -> list[str]:
    return [c.name for c in TABLES[table] if c.required and c.name not in columns and c.name not in constants]


def save(mapping: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(mapping, f, indent=1)


def load(path: str) -> dict:
    return json.load(open(path))


def confirm(mapping: dict, by: str) -> dict:
    if by.strip().lower() in FALSE_NAMES:
        raise Stop("a mapping is confirmed by a named person")
    m = dict(mapping)
    gaps = missing(m["table"], m["columns"], m["constants"])
    if gaps:
        raise Stop(f"required columns have no source and no fixed value: {', '.join(gaps)}")
    m.update(needs_a_person=[], confirmed_by=by.strip(), confirmed_on=dt.date.today().isoformat())
    return m


# ---------- one file ----------
def _value(col, raw, fmt: dict, first_month: str):
    k = col.kind
    if k in ("text",):
        return convert.text(raw)
    if k == "id":
        return convert.ident(raw)
    if k == "money":
        return convert.money(raw)
    if k == "int":
        return convert.integer(raw)
    if k == "terms":
        return convert.terms(raw)
    if k == "rate":
        return convert.rate(raw, fmt.get("rate", "decimal"))
    if k == "dpd":
        return convert.dpd(raw, fmt.get("dpd", "days"))
    if k == "bool":
        return convert.boolean(raw)
    if k == "flag":
        b = convert.boolean(raw)
        return None if b is None else int(b)
    if k in ("month", "date_split"):
        d = convert.date(raw, fmt.get("dates", "MDY"))
        if d is None:
            return None
        m = convert.month_index(d, first_month)
        return m if k == "month" else (m, d.day)
    raise ValueError(k)


def map_file(path: str, mapping: dict, staging: str, control_totals: dict[str, float] | None = None,
             report: str | None = None) -> dict:
    """Returns the result; raises nothing for a bad file: a stopped run comes back with `written: False`."""
    res = dict(file=os.path.basename(path), table=mapping.get("table"), borrower_id=mapping.get("borrower_id"),
               written=False, stops=[], rejected=[], totals_dropped=[], blank=0, notes=[], blanked={})
    try:
        res["sha256"] = hashlib.sha256(open(path, "rb").read()).hexdigest()
        _map(path, mapping, staging, control_totals, res)
    except (Stop, readfile.Refused) as e:
        res["stops"].append(str(e))
    if report:
        write_report(res, mapping, report)
    return res


def _map(path, mapping, staging, control_totals, res):
    if not mapping.get("confirmed_by"):
        raise Stop("this mapping was never confirmed by a person: run `confirm` first")
    table, fmt, first = mapping["table"], mapping["formats"], mapping["calendar"]["first_month"]
    grid = readfile.rows(path, mapping["file"].get("sheet"))
    hr = mapping["file"]["header_row"]
    if len(grid) < hr:
        raise Stop(f"the file has no row {hr} (the header row in the mapping)")
    header = [convert.text(h) for h in grid[hr - 1]]
    where = {h: i for i, h in enumerate(header) if h}
    gone = [s["source"] for s in mapping["columns"].values() if s["source"] not in where]
    if gone:
        raise Stop("the layout changed: no column named " + ", ".join(f"'{g}'" for g in gone)
                   + ". Check the file with the lender, then confirm a new mapping")
    new = [h for h in where if h not in mapping["headers_seen"]]
    if new:
        res["notes"].append("columns not seen when the mapping was confirmed (not read): " + ", ".join(new))
    cols = TABLES[table]
    id_idx = where.get(mapping["columns"].get(ID_COL[table], {}).get("source"))
    out = defaultdict(list)
    n_data = 0
    for r, cells in enumerate(grid[hr:], start=hr + 1):
        if all(convert.is_empty(c) for c in cells):
            res["blank"] += 1
            continue
        if convert.is_total_row(cells, id_idx):
            res["totals_dropped"].append(dict(row=r, text=next(convert.text(c) for c in cells if not convert.is_empty(c))))
            continue
        n_data += 1
        row, errs = {}, []
        for c in cols:
            if c.name in mapping["constants"]:
                v = mapping["constants"][c.name]
            elif c.name in mapping["columns"]:
                src = mapping["columns"][c.name]["source"]
                raw = cells[where[src]] if where[src] < len(cells) else None
                try:
                    v = _value(c, raw, fmt, first)
                except convert.Bad as e:
                    errs.append(dict(row=r, column=src, value=convert.text(raw)[:60], reason=str(e)))
                    continue
                if (v is None or v == "") and c.required and c.name not in MAY_BE_EMPTY:
                    errs.append(dict(row=r, column=src, value="", reason="empty"))
                    continue
                if c.name in NOT_NEGATIVE and v is not None and v < 0:
                    errs.append(dict(row=r, column=src, value=convert.text(raw), reason="negative amount"))
                if c.name in RANGES and v is not None and not RANGES[c.name][0] <= v <= RANGES[c.name][1]:
                    if c.required:
                        errs.append(dict(row=r, column=src, value=convert.text(raw),
                                         reason=f"outside {RANGES[c.name][0]}-{RANGES[c.name][1]}"))
                    else:  # an optional detail (a "no score" code): left empty and counted, the loan still counts
                        res["blanked"].setdefault(src, []).append(convert.text(raw))
                        v = None
                if c.name == MONTH_COL[table] and v is not None and v < 0:
                    errs.append(dict(row=r, column=src, value=convert.text(raw),
                                     reason=f"before the facility's first month ({first})"))
            else:
                v = None
            if c.outputs:
                for o, x in zip(c.outputs, v if v is not None else (None,) * len(c.outputs)):
                    row[o] = x
            else:
                row[c.name] = v
        if errs:
            res["rejected"] += errs
            continue
        for k, x in row.items():
            out[k].append(x)
    res["rows_read"] = n_data
    bad_rows = len({e["row"] for e in res["rejected"]})
    res["rows_rejected"] = bad_rows
    if n_data == 0:
        raise Stop("no data rows under the header row")
    if bad_rows / n_data > MAX_REJECTED:
        raise Stop(f"{bad_rows} of {n_data} rows ({bad_rows / n_data:.1%}) could not be read, over the "
                   f"{MAX_REJECTED:.0%} limit. Every one is listed below; ask the borrower to resend")
    n = len(out[MONTH_COL[table]])
    keys = list(zip(*(out[k] for k in KEY[table])))
    seen, dups = set(), set()
    for k in keys:
        (dups if k in seen else seen).add(k)
    if dups:  # kept, never dropped: a second copy of an invoice or loan is evidence (an altered or double-listed
        # item), and stopping would let the borrower resend the file without it
        res["duplicates"] = sorted(map(str, dups))[:20]
        res["notes"].append(f"{len(dups)} rows appear more than once ({' + '.join(KEY[table])}). Kept, so the checks "
                            f"see them; ask the borrower why")
    sums = defaultdict(float)
    for m, a in zip(out[MONTH_COL[table]], out[AMOUNT_COL[table]]):
        sums[m] += a or 0.0
    res["months"] = {month_label(m, first): round(sums[m], 2) for m in sorted(sums)}
    tie = []
    if control_totals is None:
        if table in ("tape", "invoices"):
            raise Stop("no control total: give the total from the borrower's borrowing-base certificate for each "
                       "month in the file")
        res["notes"].append("not tied out to a control total (none given for this servicer extract)")
    else:
        for m in sorted(sums):
            lab = month_label(m, first)
            if lab not in control_totals:
                raise Stop(f"no control total given for {lab}")
            diff = sums[m] - control_totals[lab]
            tie.append(dict(month=lab, mapped=round(sums[m], 2), certificate=control_totals[lab], difference=round(diff, 2)))
        res["tie_out"] = tie
        off = [t for t in tie if abs(t["difference"]) > TIE_OUT]
        if off:
            raise Stop("the mapped amounts don't add up to the certificate: "
                       + "; ".join(f"{t['month']} off by ${t['difference']:,.2f}" for t in off))
    by_month = defaultdict(set)
    for m, k in zip(out[MONTH_COL[table]], out[ID_COL[table]]):
        by_month[m].add(k)
    ms = sorted(by_month)
    res["continuity"] = [dict(month=month_label(b, first), appeared=len(by_month[b] - by_month[a]),
                              left=len(by_month[a] - by_month[b])) for a, b in zip(ms, ms[1:])]
    if table == "invoices" and all(x is None for x in out["invoice_id"]):  # the lender's file has no record ID
        out["invoice_id"] = [f"{mapping['borrower_id']}:{num}:{pm}" for num, pm in zip(out["invoice_number"], out["pledged_month"])]
    schema = out_schema(table)
    arrays = [pa.array(out.get(f.name, [None] * n), type=f.type) for f in schema]
    os.makedirs(os.path.join(staging, table), exist_ok=True)
    dest = os.path.join(staging, table, f"{mapping['borrower_id']}__{os.path.splitext(os.path.basename(path))[0]}.parquet")
    pq.write_table(pa.Table.from_arrays(arrays, schema=schema), dest)
    res.update(written=True, output=dest, rows_written=n)


def month_label(m: int, first_month: str) -> str:
    y0, m0 = map(int, first_month.split("-"))
    t = y0 * 12 + (m0 - 1) + m
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


# ---------- the table the checks read ----------
SORT = {"tape": ("borrower_id", "month", "asset_id"), "source_truth": ("borrower_id", "month", "asset_id"),
        "invoices": ("invoice_id",)}


def assemble(staging: str, table: str, data_dir: str) -> int:
    files = sorted(glob.glob(os.path.join(staging, table, "*.parquet")))
    if not files:
        raise Stop(f"nothing mapped for {table} in {staging}")
    t = pa.concat_tables([pq.read_table(f) for f in files])
    t = t.sort_by([(k, "ascending") for k in SORT[table]])
    os.makedirs(data_dir, exist_ok=True)
    pq.write_table(t, os.path.join(data_dir, f"{table}.parquet"))
    return t.num_rows


# ---------- the report ----------
def write_report(res: dict, mapping: dict, path: str) -> None:
    L = [f"# Mapping report: {res['file']}", "",
         f"- **Result: {'WRITTEN' if res['written'] else 'STOPPED, nothing written'}**",
         f"- Borrower `{res['borrower_id']}`, table `{res['table']}`, file sha256 `{res.get('sha256', '?')[:16]}…`",
         f"- Mapping confirmed by: {mapping.get('confirmed_by') or 'nobody (not confirmed)'}"
         f"{' on ' + mapping['confirmed_on'] if mapping.get('confirmed_on') else ''}",
         f"- Sheet: {mapping['file'].get('sheet') or '(first)'}; header row {mapping['file']['header_row']}; "
         f"month 0 = {mapping['calendar']['first_month']}", ""]
    for s in res["stops"]:
        L.append(f"**Stopped:** {s}")
    if res["stops"]:
        L.append("")
    L += ["## Columns", "", "| Ours | From the file | Score when suggested |", "|---|---|---|"]
    for k, v in mapping["columns"].items():
        L.append(f"| `{k}` | {v['source']} | {v.get('score', '-')} |")
    for k, v in mapping["constants"].items():
        L.append(f"| `{k}` | fixed: `{v}` | set by a person |")
    L += ["", f"Formats: {json.dumps(mapping['formats'])}", ""]
    L += ["## Rows", "", f"- Data rows read: {res.get('rows_read', 0)}; written: {res.get('rows_written', 0)}",
          f"- Blank rows skipped: {res['blank']}",
          f"- Total rows dropped: {len(res['totals_dropped'])}"
          + "".join(f"\n  - row {t['row']}: '{t['text']}'" for t in res["totals_dropped"][:20]),
          f"- Rows rejected: {res.get('rows_rejected', 0)}"]
    for col, vals in res["blanked"].items():
        L.append(f"- {col}: {len(vals)} values outside the expected range left empty (e.g. {', '.join(sorted(set(vals))[:5])}); "
                 f"those loans still count")
    L.append("")
    if res["rejected"]:
        L += ["| Row | Column | Value | Why |", "|---|---|---|---|"]
        L += [f"| {e['row']} | {e['column']} | {e['value']} | {e['reason']} |" for e in res["rejected"]]
        L.append("")
    if res.get("duplicates"):
        L += ["**Rows that appear more than once, kept (first 20):** " + "; ".join(res["duplicates"]), ""]
    if res.get("tie_out"):
        L += ["## Control total", "", "| Month | Mapped | Certificate | Difference |", "|---|---|---|---|"]
        L += [f"| {t['month']} | ${t['mapped']:,.2f} | ${t['certificate']:,.2f} | ${t['difference']:,.2f} |"
              for t in res["tie_out"]]
        L.append("")
    if res.get("continuity"):
        L += ["## Month to month (for the person, not a check)", "", "| Month | New | Gone since last month |",
              "|---|---|---|"]
        L += [f"| {c['month']} | {c['appeared']} | {c['left']} |" for c in res["continuity"]]
        L.append("")
    for n in res["notes"]:
        L.append(f"- Note: {n}")
    L += ["", "Checked and signed off by: ______________________  Date: __________", ""]
    with open(path, "w") as f:
        f.write("\n".join(L))
