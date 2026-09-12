"""S7 Financial consistency: do the reported numbers fit the evidence?

Mechanism: First Brands kept "bridge" files juxtaposing real and manipulated
financials (VERIFY F5); Tricolor portrayed itself as "financially sound" (T4).

Uses other systems' outputs (this is where the chaining pays off):
  S3 verified collections  -> CASH_REVENUE_GAP (revenue grows, verified cash doesn't)
  S5 undisclosed liens     -> DEBT_GAP
  S4 invoice findings      -> RECEIVABLES_QUALITY
and its own                -> COVENANT_EDGE_PATTERN (repeatedly just clearing the line)
                           -> RECEIVABLES_OUTPACE_REVENUE (invoice-based borrowers: reported
                              receivables pile up far faster than revenue, the footprint of
                              invoices that will never be paid). Not applied to loan books:
                              on those the ratio drifts as much for honest borrowers.
"""
import statistics

from bt.systems.base import Ctx, sig


def run(ctx: Ctx, upstream: dict):
    out = []
    known_q = ctx.shared.get("known_q", {})
    fin = {}
    for r in ctx.rows("SELECT * FROM financials ORDER BY borrower_id, quarter"):
        fin.setdefault(r["borrower_id"], []).append(r)
    for b, qs in fin.items():
        ratios = [(q["quarter"], q["revenue_reported"] / known_q[(b, q["quarter"])])
                  for q in qs if known_q.get((b, q["quarter"]), 0) > 0]
        if len(ratios) >= 4:
            base = statistics.median(r for _, r in ratios[:2])
            last2 = ratios[-2:]
            if base > 0 and all(r > base * 1.12 for _, r in last2):
                jump = last2[-1][1] / base - 1
                out.append(sig("S7", b, "CASH_REVENUE_GAP", min(1.0, 0.4 + jump), 0.75,
                               [f"financials:{b}:Q{q}" for q, _ in last2] + [f"s3:verified_collections:{b}"],
                               f"Reported revenue is running {jump:.0%} above what verified customer cash supports "
                               f"(2 quarters in a row)", last2[0][0] * 3 + 2))
        edge = [q for q in qs[-2:] if q["covenant_threshold"] <= q["covenant_metric_reported"] < q["covenant_threshold"] * 1.05]
        if len(qs) >= 2 and len(edge) == 2:
            out.append(sig("S7", b, "COVENANT_EDGE_PATTERN", 0.5, 0.6,
                           [f"financials:{b}:Q{q['quarter']}:covenant={q['covenant_metric_reported']}" for q in edge],
                           "Covenant metric landed within 5% above the threshold two quarters running",
                           edge[0]["quarter"] * 3 + 2))
    invoice_based = {r["borrower_id"] for r in ctx.rows("SELECT borrower_id FROM borrowers WHERE btype = 'receivables_finance'")}
    for b, qs in fin.items():
        dso = [(q["quarter"], q["receivables_reported"] / q["revenue_reported"]) for q in qs if q["revenue_reported"] > 0]
        if b not in invoice_based or len(dso) < 6:
            continue
        base = statistics.median(r for _, r in dso[:4])
        last2 = dso[-2:]
        if base > 0 and all(r > base * 2.0 for _, r in last2):
            mult = last2[-1][1] / base
            out.append(sig("S7", b, "RECEIVABLES_OUTPACE_REVENUE", min(1.0, 0.3 + mult / 10), 0.7,
                           [f"financials:{b}:Q{q}:receivables/revenue={r:.2f}" for q, r in last2]
                           + [f"financials:{b}:baseline={base:.2f}"],
                           f"Reported receivables are {mult:.1f}x their usual size relative to revenue "
                           f"(2 quarters in a row): money is booked that isn't being collected", last2[0][0] * 3 + 2))
    for b, ids in upstream.get("s5_undisclosed", {}).items():
        out.append(sig("S7", b, "DEBT_GAP", 0.7, 0.8, [f"signal:{i}" for i in ids[:3]] + [f"financials:{b}:debt_reported"],
                       f"Debt reported to Wells Fargo omits {len(ids)} secured lender(s) found in public lien filings",
                       ctx.as_of))
    for b, ids in upstream.get("s4_flags", {}).items():
        out.append(sig("S7", b, "RECEIVABLES_QUALITY", 0.5, 0.7, [f"signal:{i}" for i in ids[:3]],
                       "Reported receivables include invoices that S4 found altered, unpaid or implausible",
                       ctx.as_of))
    return out
