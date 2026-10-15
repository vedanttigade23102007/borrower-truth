# Corrections to published reports

Published reports in `proof/` are never edited after they are scored. When one prints something imprecise, the correction goes here, dated, and every place that presents the report links to this page.

## 15 Oct 2026: `REPORT_seeds1301-1305.md` rounds 249/250 up to "(100%)"

- **What the report prints:** "Frauds caught by month 24 | 249/250 (100%)".
- **What is exact:** 249 of 250 is **99.6%**. The report rounds percentages to whole numbers, so 99.6% printed as 100%.
- **What it means:** on this held-out synthetic test set (seeds 1301–1305), 249 of 250 planted fraud cases were flagged by month 24. One was not: B0042 on seed 1304, sent to "worth a look" instead. This is not a measurement of real-world fraud detection accuracy.
- **What else in that report rounds the same way:** the per-mechanism and per-pattern tables ("TAPE_DRESSUP 64/65 (98%)", "paid_to_look_current 19/20 (95%)"). The fractions are exact; the percentages are rounded to whole numbers.
- The report itself stays as it was scored. The JSON beside it (`REPORT_seeds1301-1305.json`) has the unrounded rate: `"catch_rate": 0.996`.
- **`REPORT.md` and `REPORT.json` round the same way.** Since 15 Oct 2026 they are exact copies of `REPORT_seeds1301-1305.md` and `.json` (the current-evaluation convenience copy; the frozen reports keep their seed names and are unchanged), so `REPORT.md` also prints "249/250 (100%)". The exact figure is 99.6%, as above.
