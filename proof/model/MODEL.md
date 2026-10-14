# Invoice reader: fine-tuned document model (Kaggle, 11 Sep 2026)

**Status (1 Oct 2026): an optional module, off by default** (`BT_DOCUMENT_MODEL=on` turns it on; buyer review gap 7, kept private). The rules work without it, so a bank pays for validating a model only if it turns it on. It helps a little, at best:
- On the held-out book below, it flagged all 24 tampered invoices, and also 15 of 516 clean ones.
- On the demo book it found no fraud the rules missed. Turning it on added 6 "worth a look" cases, all on honest borrowers.

**What:** Donut (`naver-clova-ix/donut-base`, OCR-free, ~200M params), fine-tuned to read five fields from invoice images: invoice number, PO number, bill-to, date, total. S4 then compares the document with the borrower's data record. A mismatch is a tampering flag, sent to a human to confirm.

**Training:**
- Hardware: Kaggle T4 GPU, free tier.
- Schedule: 5 passes over the training set (epochs); training loss fell from 1.05 to 0.04.
- Data: 806 synthetic invoices for training, 352 for validation, 342 for test.
- Split: by borrower, so the test layouts come from borrowers the model never saw.
- Script: `model/kaggle/train_invoice_reader.py`. Raw numbers: `proof/model/metrics.json`.

## Results on the 342 held-out test invoices

| Field | Fine-tuned | Base model, not fine-tuned |
|---|---|---|
| Invoice number | 95.0% | 0% |
| PO number | 97.1% | 0% |
| Bill-to | 100% | 0% |
| Invoice date | 95.6% | 0% |
| Total | 96.5% | 0% |
| **All five fields correct** | **84.8%** | 0% |

**Tamper check** (document total vs. data record, >1% difference):
- The test set holds 11 tampered invoices. **All 11 were flagged** (recall 100%).
- It raised 22 flags in total. **11 were false flags on the 331 clean invoices (3.3%)**, so precision is 50%.
- Every flag goes to a person to confirm, so a false flag costs review time, not a wrong decision.

**Speed:** 120 invoices per minute on one T4.

## Wired into S4: document vs data on a book it never saw

The batch job (`model/kaggle_score/score_invoices.py`, Kaggle T4) read the documents on file for two books. S4 compares each read total with the borrower's data record (`DOC_DATA_MISMATCH`). If the first read disagrees, the document is read a second time with beam search before it is flagged.

| Book | Documents | Tampered caught | False flags, first read | False flags after second look | Speed |
|---|---|---|---|---|---|
| Held-out book (seed 201, never used in training) | 540 | **24 / 24** | 17 / 516 (3.3%) | **15 / 516 (2.9%)** | 150 docs/min |
| Demo book (seed 7; partly the training borrowers) | 495 | 27 / 27 | 14 / 468 (3.0%) | 14 / 468 (3.0%) | 152 docs/min |

**The second look helps only a little:** 17 → 15 false flags on the held-out book, and no change on the demo book. It is kept because it is cheap: only the 41 disagreeing documents were read again. The real fix for digit slips, cross-checking the total against the line items, needs the model retrained to read line items. That is not done.

Raw numbers: `proof/model/score_metrics.json`.

## Honest caveats
- **The baseline is weak.** The base checkpoint cannot produce this output format without fine-tuning, so 0% shows fine-tuning is necessary. It does *not* show we beat a strong general-purpose vision-language model; that comparison has not been run.
- **Errors are digit slips.** Examples: `B0013-12121` read as `B0013-121`; `69331.83` read as `69311.83`. The false tamper flags come from these misread totals.
- **All synthetic.** Three layouts from one generator. Real invoices vary far more, so accuracy on real documents is unknown until re-validated on them.

## Next improvements (not done yet)
1. Cross-check the read total against the sum of the line items, and re-read before flagging. This should cut the false flags caused by digit slips.
2. Compare against a zero-shot general vision-language model on the same test set.
3. Add harder layouts and scan noise.
