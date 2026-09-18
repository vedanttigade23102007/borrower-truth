# What lenders can already buy, vs Borrower Truth

Compiled 2026-09-12 from each vendor's **own public pages**. This covers what they say they do, not what they may do privately. "Not described" means their public page doesn't mention it; it does **not** mean they can't do it. Borrower Truth numbers are on synthetic data only.

## Sources

| Vendor | Source | How read |
|---|---|---|
| Setpoint PledgeCheck | [Setpoint release, 29 Oct 2025](https://www.setpoint.io/setpoint-launches-industry-standard-to-stop-double-pledging-after-tricolor-and-first-brands-collapse/) (saved: `sources/setpoint-pledgecheck.txt`) | primary, saved |
| Collateral checkers (Guidehouse, Vervent, CBIZ, Setpoint) | [Bloomberg via Yahoo, 21 Aug 2026](https://finance.yahoo.com/small-business/articles/tricolor-fallout-fuels-boom-business-090000623.html) (saved: `sources/yahoo-collateral-checkers.txt`) | secondary, saved |
| Finley Verification Suite | [PR Newswire, 8 Apr 2024](https://www.prnewswire.com/news-releases/introducing-finleys-verification-suite-a-new-standard-for-accuracy-automation-and-efficiency-in-asset-based-lending-302110145.html) | primary, fetched |
| Cardo AI | [Loan Data Agent page](https://cardoai.com/solutions/by-product/loan-data-agent/) | primary, fetched |
| MonetaGo | [Standard Chartered pilot release](https://www.sc.com/en/press-release/weve-completed-the-industry-first-pilot-of-trade-financing-validation-service-provided-by-monetago-over-swift/), [monetago.com](https://www.monetago.com/) | primary, fetched |
| Quantexa | [Lending fraud page](https://www.quantexa.com/solutions/lending-fraud/) | primary, fetched |
| Ocrolus Detect | [Detect documentation](https://docs.ocrolus.com/docs/detect) | primary, fetched |
| Wolters Kluwer Lien Solutions (iLien) | [Lien Solutions](https://www.wolterskluwer.com/en/solutions/lien-solutions) | page blocked direct fetch (403); taken from search-result text of their pages. **Verify before quoting** |

## Coverage: which of the seven places each one looks at

✓ = the vendor's public page says so · ◐ = partly · – = not described

| Where the fraud hides | Setpoint PledgeCheck | Finley | Cardo AI | MonetaGo | Quantexa | Ocrolus Detect | WK iLien | Field-exam firms | **Borrower Truth** |
|---|---|---|---|---|---|---|---|---|---|
| S1 Collateral pledged twice | ✓ across lenders | – | – | ✓ trade docs, across banks | – | – | – | ◐ sample | ◐ inside WF + reads PledgeCheck |
| S2 Loan file vs source | ◐ vs borrower's own master tape | ✓ tape vs source documents | ◐ vs contracts | – | – | – | – | ◐ sample | ✓ vs servicer system |
| S3 Who actually paid | ◐ collections amount vs reported | – | – | – | – | ◐ bank statements (tampering) | – | ◐ cash reconciliations | ✓ payer identity |
| S4 Fake or altered invoices | – | ◐ invoices vs tape | – | ✓ duplicate invoices across banks | – | – (statements, pay stubs, W-2s) | – | ◐ sample | ✓ + document model |
| S5 Hidden debt (liens, judgments) | – | – | – | – | – | – | ✓ search + monitoring | – | ✓ incl. linked companies |
| S6 Linked companies, shells | – | – | – | – | ✓ entity resolution | – | – | – | ✓ owner/address/GLEIF |
| S7 Financials don't fit | – | ◐ borrowing base | ✓ covenants | – | ◐ "misrepresenting financial strength" | – | – | – | ✓ vs verified cash |
| Joins the places into one verdict + suggested fix + human approval | – | – | – | – | ◐ investigation tooling | ◐ authenticity score | – | people do it | ✓ |

## Where each vendor is stronger than Borrower Truth

- **Setpoint:** sees across *other lenders'* facilities (Borrower Truth can't), has over 250 lenders and originators on its platform (Setpoint release), and is backed by Citi and Wells Fargo.
- **MonetaGo:** a cross-bank registry over SWIFT; the network effect is the product.
- **Quantexa:** entity resolution over "billions of data points"; far more mature than name/address matching.
- **Ocrolus:** deep document forensics (metadata, edits, AI-generated documents), trained on hundreds of millions of documents; Borrower Truth only reads the invoice total.
- **Wolters Kluwer:** 40 years of lien filing, search and monitoring data.
- **Finley and Cardo:** live customers and full credit-administration workflows.
- **All of them:** real customers and real data. Borrower Truth has neither yet.

## Honest positioning

Each vendor covers one or two of the seven places, and does it deeper than this demo. From their public pages, none describes joining all seven places for one non-bank borrower and turning that into a verdict, the evidence and a suggested fix. That joining is where First Brands and Tricolor (as alleged) slipped through: each trick sat in a different place.

So Borrower Truth is **not** a replacement for these tools. It's the layer on top that **uses** them: PledgeCheck results already feed S1, and lien data, entity resolution and document forensics are the natural feeds for S5, S6 and S4 in a real deployment. For Wells Fargo that means **more value from tools it already backs, not another vendor fighting them.**

## Not checked (next steps)

- Vendors' private or enterprise features beyond their public pages.
- Pricing.
- Moody's (Orbis, CreditLens), S&P, dv01, Sayari and other data vendors.
- Whether Wells Fargo uses any of these beyond backing Setpoint.
