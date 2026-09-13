# SEC data plan: sources and facts (checked 14 Sep 2026)

These are the facts behind `deck/sec-plan.html`. Nothing in this file has been downloaded from EDGAR yet: pulling data needs a contact email in the request header, and that email needs Vedant's OK.

| Fact | Source | Tier |
|---|---|---|
| Form ABS-EE holds loan-level data (Schedule AL) for registered ABS: Item 1 residential mortgages, Item 2 commercial mortgages, Item 3 auto loans, Item 4 auto leases | 17 CFR 229.1125, https://www.law.cornell.edu/cfr/text/17/229.1125 | primary (regulation text) |
| Auto-loan fields: origination date, amount, term, rate; vehicle make, model, year, new/used, value; obligor credit score, income verification, payment-to-income ratio, state; each period: scheduled vs actual amount paid, current delinquency status, repossession, charged-off principal, recoveries, modification, zero-balance code | same | primary |
| No VIN field, and no obligor name or identifier | same | primary |
| Filed with each reporting period: monthly when the deal reports monthly; performance is reported even when the payments don't reach investors | SEC ABS-EE interpretations, `research/sources/sec-absee-interps.txt` | primary |
| Example filer: CarMax Auto Funding LLC files Form ABS-EE for CarMax Auto Owner Trusts (filings seen for 2021–2026) | EDGAR filing index, e.g. https://www.sec.gov/Archives/edgar/data/1259380/000125938026000015/abs-ee2026x2smallpool040326.htm | primary (search result; not opened) |
| data.sec.gov APIs: submissions, companyfacts, companyconcept, frames; no API key; updated in real time; companyfacts.zip and submissions.zip rebuilt nightly around 3 a.m. ET | https://www.sec.gov/search-filings/edgar-application-programming-interfaces | primary |
| Automated access must declare a User-Agent such as "Sample Company Name AdminContact@<domain>.com"; maximum 10 requests per second | https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data | primary |
| Tricolor (alleged): double-pledged auto loans to several ABS deals and lenders; made non-paying or defaulted loans look current; more than $945M of ABS principal still outstanding at bankruptcy | `research/sources/sec-tricolor-2026-77.txt` | primary |
| Tricolor's ABS were private placements resold under Rule 144A, not SEC-registered, so they would not file Form ABS-EE | The bank defendants' filings in civil litigation, as reported by Octus: https://octus.com/resources/articles/tricolor-implosion-creates-first-of-its-kind-auto-loan-securitization-litigation-with-industrywide-implications/ | secondary |
| 8-K Item 2.03 (new direct financial obligation) and Item 2.04 (triggering events that accelerate an obligation); 10-K Exhibit 21 (subsidiaries of the registrant) | Form 8-K and Regulation S-K Item 601(b)(21), standard SEC forms | primary (well known; not re-fetched) |

**Not checked:**
- how many public auto ABS trusts file each month;
- how much public pools differ from small subprime lenders.

Both get measured in the build.
