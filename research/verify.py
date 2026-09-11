#!/usr/bin/env python3
"""Check every claim the deck will use against the locally held source text.

A claim is VERIFIED only if its pattern matches the source file in this run.
Output: VERIFY.md (claim · source · tier · matched · context).
Referent (does the sentence really apply to this claim?) is judged by reading
the printed context, and recorded in the `referent` column by hand-checked rules
below — never assumed from a match alone.
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sources")

# (id, claim as it will appear in the deck, source key, regex, referent note)
CLAIMS = [
    ("W1", "Loans to non-bank financial firms ('financials except banks') are $208.8B, 20% of WF loans, $318.9B committed (30 Jun 2026)",
     "wf-10q-2026q2", r"Total financials except banks 228 208,838 20 318,916", "Table 12, June 30 2026 column"),
    ("W2", "Same category was $191.1B at 31 Dec 2025 (+9% in six months)",
     "wf-10q-2026q2", r"245 191,067 19 306,201", "Table 12, Dec 31 2025 column (revised presentation)"),
    ("W3", "It is WF's largest industry category of commercial loans",
     "wf-10q-2026q2", r"largest industry category, financials except banks", "C&I risk management text"),
    ("W4", "WF's stated protections rely on collateral eligibility rules and re-margining",
     "wf-10q-2026q2", r"collateral eligibility requirements, contractual re-margining of collateral", "describes the financials-except-banks loans"),
    ("W5", "Q1 2026: higher net charge-offs 'driven by a single fraud-related loss'",
     "wf-10q-2026q1", r"higher net charge-offs driven by a single fraud-related loss", "segment discussion (commercial); borrower not named"),
    ("W6", "Headcount 197,466 at 30 Jun 2026 vs 212,804 a year earlier (-7%)",
     "wf-10q-2026q2", r"Headcount \(#\) \(period-end\) 197,466 200,999 212,804 \(2\) \(7\)", "company-wide financial summary"),
    ("W7", "Total assets $2.28T, +15% year on year",
     "wf-10q-2026q2", r"Assets 2,282,201 2,205,752 1,981,269 3 15", "period-end balance sheet summary"),
    ("W8", "Efficiency ratio 60% in Q2 2026 vs 67% in Q1 2026",
     "wf-10q-2026q2", r"Efficiency ratio \(7\) 60 67", "company-wide ratios"),
    ("W9", "Up to ~$1.5B of reasonably possible legal losses above accruals",
     "wf-10q-2026q2", r"approximately \$ 1\.5 billion as of June 30, 2026", "Note 9 Legal Actions outlook"),
    ("W10", "OCC anti-money-laundering formal agreement still cited in Q2 2026 filing",
     "wf-10q-2026q2", r"entered into a formal agreement with the Office of the Comptroller of the Currency", "Note 9 Legal Actions"),
    ("W11", "Government 'fair access to banking' investigations incl. Executive Order 14331",
     "wf-10q-2026q2", r"FAIR ACCESS TO BANKING INVESTIGATIONS.{0,200}Executive Order 14331", "Note 9 Legal Actions"),
    ("W12", "Wealth & Investment Management efficiency ratio 81% in Q2 2026",
     "wf-10q-2026q2", r"Efficiency ratio 81 83", "Table 6g WIM"),
    ("W13", "Investment banking fees +35% year on year in Q2 2026",
     "wf-10q-2026q2", r"Investment banking fees 948 700 248 35", "Table 6e CIB"),
    ("W14", "Fed removed the asset cap on 3 June 2025",
     "wf-10k-2025", r"On June 3, 2025, the Company confirmed that the FRB had removed", "10-K regulatory section"),
    ("W15", "Fed terminated the 2018 consent order (announced 5 Mar 2026)",
     "wf-newsroom-fed-order-terminated", r"03/05/2026.{0,300}terminated the 2018 consent order", "WF newsroom release"),
    ("W16", "WF has a Head of Artificial Intelligence since November 2025",
     "wf-10k-2025", r"Head of Artificial Intelligence since November 2025", "executive officers list"),
    ("W17", "OCC agreement Article XII restricts expansion into new products/markets pending AML assessment",
     "occ-formal-agreement-2024-72", r"RESTRICTION ON NEW PRODUCTS, SERVICES, AND MARKETS", "Article XII heading"),
    ("T1", "Tricolor: double pledging hundreds of millions of subprime auto loans to multiple ABS and lenders",
     "sec-tricolor-2026-77", r"double pledging hundreds of millions of dollars of subprime auto loans", "SEC release, allegation"),
    ("T2", "Tricolor: loans represented as free of other liens while double pledged",
     "sec-tricolor-2026-77", r"free and clear of any other liens", "SEC release, allegation"),
    ("T3", "Tricolor: made non-paying/defaulted loans appear current and eligible",
     "sec-tricolor-2026-77", r"appear current", "SEC release, allegation"),
    ("T4", "Tricolor raised $1.9B through ABS offerings",
     "sec-tricolor-2026-77", r"1\.9 billion", "SEC release"),
    ("T5", "Tricolor pledged ~$2.2B of collateral but had only ~$1.4B real (~$800M bogus), Aug 2025",
     "doj-tricolor", r"approximately \$2\.2 billion of collateral.{0,120}approximately \$1\.4 billion of real collateral.{0,80}approximately \$800 million in bogus collateral", "DOJ release, allegation"),
    ("T6", "Tricolor manipulated collateral characteristics so ineligible assets appeared to meet lender requirements",
     "doj-tricolor", r"manipulate the characteristics of collateral to make ineligible, near-worthless assets appear to meet lender requirements", "DOJ release, allegation"),
    ("T7", "Recorded CEO: the problem would be 'if they sent an auditor and they said, pull this up on your screen'",
     "doj-tricolor", r"pull this up on your screen", "DOJ release, recorded call"),
    ("T8", "Tricolor's largest lenders were owed more than $900M at bankruptcy (10 Sep 2025)",
     "doj-tricolor", r"owed more than \$900 million", "DOJ release"),
    ("F1", "First Brands: fake and inflated invoices; double- and triple-pledged collateral; falsified statements; concealed liabilities",
     "doj-first-brands", r"fake and falsely inflate invoices for accounts receivable and payable; double- and triple-pledge loan collateral; falsify corporate financial statements; and conceal substantial liabilities", "DOJ release, allegation"),
    ("F2", "First Brands: ~$5B sales but $12M cash and >$9B liabilities at bankruptcy",
     "doj-first-brands", r"\$5 billion in net annual sales.{0,80}\$12 million in cash.{0,80}over \$9 billion in liabilities", "DOJ release"),
    ("F3", "First Brands: related 'James Entities' with no independent operations carried off-balance-sheet debt",
     "doj-first-brands", r"no independent business operations", "DOJ release, allegation"),
    ("F4", "First Brands: loan proceeds routed to look like ordinary customer receipts",
     "doj-first-brands", r"appeared to be ordinary customer receipts", "DOJ release, allegation"),
    ("F5", "First Brands: internal 'bridge' files juxtaposed real and manipulated financials",
     "doj-first-brands", r"\"bridge\" files that juxtaposed accurate corporate financials with the manipulated versions", "DOJ release, allegation"),
    ("S1", "Setpoint PledgeCheck is 'backed by' Citi and Wells Fargo",
     "setpoint-pledgecheck", r"Citi and Wells Fargo", "Setpoint's own release"),
    ("S2", "PledgeCheck works from data tapes the borrower uploads",
     "setpoint-pledgecheck", r"[Bb]orrowers upload", "Setpoint's own release"),
    ("S3", "PledgeCheck also checks data integrity (VIN/address consistency) and completeness (actual collections vs reported)",
     "setpoint-pledgecheck", r"Data Integrity : Key fields like address, VIN.{0,200}Completeness : Actual collections on assets are matched to what is reported", "Setpoint's own release: corrects our earlier 'cannot see if tapes lie' claim"),
    ("C4", "After the Q1 loss WF sent teams to clients to 'follow the money trail and trace back all the flows'",
     "fool-wf-2026q1-call", r"follow the money trail and trace back all the flows", "earnings call, CFO answer on the Q1 fraud loss"),
    ("C5", "WF's Q1 fraud loss was in the 'real estate finance category' of financials except banks",
     "fool-wf-2026q1-call", r"single fraud-related loss in the real estate finance category in the financials except banks portfolio", "earnings call prepared remarks; borrower not named"),
    ("M1", "WF named among lenders exposed to UK lender MFS",
     "cnbc-mfs", r"Wells Fargo", "CNBC; exposure amount checked separately"),
    ("M2", "WF exposure to MFS about £143M",
     "cnbc-mfs", r"143", "CNBC"),
    ("Y1", "Guidehouse saw ~80% more demand for collateral verification after Tricolor",
     "yahoo-collateral-checkers", r"80%", "Bloomberg via Yahoo"),
    ("Y2", "Lenders now ask for full asset lists and cash reconciliations",
     "yahoo-collateral-checkers", r"cash reconciliation", "Bloomberg via Yahoo"),
    ("C1", "Q1 2026 call: new credit card account openings up nearly 60%",
     "fool-wf-2026q1-call", r"(nearly|almost) 60%", "earnings call transcript"),
    ("C2", "Q1 2026 call: management called the fraud 'an isolated incident'",
     "fool-wf-2026q1-call", r"isolated", "earnings call transcript"),
    ("C3", "Q1 2026 call: 23 consecutive quarters of headcount reductions",
     "fool-wf-2026q1-call", r"23 consecutive quarters", "earnings call transcript"),
    ("D1", "GLEIF 'who owns whom' (Level 2) data is openly available",
     "gleif-level2", r"[Ww]ho [Oo]wns [Ww]hom", "GLEIF page"),
    ("D2", "CourtListener offers a REST API",
     "courtlistener-api", r"REST API", "CourtListener docs"),
    ("J1", "Tech intern eligibility: graduating Mar–Aug 2028, Bengaluru/Hyderabad",
     "wf-job-tech-intern-2027", r"March 2028", "WF job posting"),
    ("W18", "The intern posting asks for programming in Java, C#, SQL and Python",
     "wf-job-tech-intern-2027", r"Java.{0,20}C#.{0,20}SQL.{0,20}Python", "WF intern posting"),
    ("W19", "WF India engineering job ads list Kafka (and Spark, Spring Boot)",
     "wf-jobs-search-snippets", r"Python, Apache Spark, and Kafka", "search snippets of wellsfargojobs.com; pages no longer load"),
    ("W20", "A WF 'Data Engineer-AI' ad lists Cloud Composer (Apache Airflow), Kafka and Google Pub/Sub",
     "wf-jobs-search-snippets", r"Cloud Composer \(Apache Airflow\), Kafka, and Google Pub/Sub", "search snippet of wellsfargojobs.com"),
    ("A1", "WF's Fargo: a small in-house model detects personal data before Google's Flash 2.0 is called",
     "venturebeat-fargo", r"small language model \(SLM\) for personally identifiable information \(PII\) detection\. Only then is a call made to Google.s Flash 2\.0", "VentureBeat interview with WF CIO"),
    ("A1b", "WF is 'poly-model': Llama used internally, OpenAI models as needed",
     "venturebeat-fargo", r"smaller models like Llama are used elsewhere internally, and OpenAI models can be tapped as needed", "VentureBeat"),
    ("A3", "WF used a network of interacting agents to re-underwrite 15 years of archived loan documents",
     "venturebeat-fargo", r"re-underwrite 15 years of archived loan documents", "VentureBeat"),
    ("A2", "WF's Google Agentspace tools help employees navigate policies and sort through documentation",
     "ciodive-wf-agentspace", r"help employees navigate policies and procedures, sort through scores of documentation", "CIO Dive, Aug 2025"),
    ("O1", "The OCC agreement with WF cites the model-risk guidance OCC Bulletin 2011-12",
     "occ-formal-agreement-2024-72", r"OCC Bulletin 2011-12", "OCC agreement Art. VIII/XI references"),
    ("G1", "Kaggle gives free GPU access with a weekly quota of 30 hours or more",
     "kaggle-gpu-docs-browser", r"30 hours or sometimes higher", "Kaggle docs"),
    ("G2", "Hugging Face ZeroGPU offers free GPU access for Spaces demos",
     "hf-zerogpu-docs", r"Free GPU Access", "Hugging Face docs"),
    ("D3", "CORD receipt dataset is licensed CC-BY-4.0",
     "hf-cord-v2", r"License: cc-by-4\.0", "Hugging Face dataset card"),
    ("D4", "FUNSD has 199 fully annotated forms (licence still to confirm)",
     "funsd", r"199 fully annotated forms", "FUNSD site; licence not shown on page"),
]


def load(key):
    p = os.path.join(SRC, key + ".txt")
    return open(p).read() if os.path.exists(p) else None


def main():
    rows, n_ok = [], 0
    for cid, claim, key, pat, ref in CLAIMS:
        t = load(key)
        if t is None:
            rows.append((cid, claim, key, "?", "NO SOURCE FILE", "", ref)); continue
        tier = re.search(r"TIER: (\w+)", t).group(1)
        m = re.search(pat, t, re.S)
        if m:
            n_ok += 1
            a, b = max(0, m.start() - 120), min(len(t), m.end() + 120)
            ctx = " ".join(t[a:b].split()).replace("|", "/")
            rows.append((cid, claim, key, tier, "MATCHED", ctx, ref))
        else:
            rows.append((cid, claim, key, tier, "NOT FOUND", "", ref))
    out = ["# VERIFY — claim-by-claim check against locally held sources",
           "", f"Run by `research/verify.py`. {n_ok}/{len(CLAIMS)} matched. Anything NOT FOUND is cut from the deck or labelled.", "",
           "| ID | Claim | Source | Tier | Result | Referent | Context |", "|---|---|---|---|---|---|---|"]
    for cid, claim, key, tier, res, ctx, ref in rows:
        out.append(f"| {cid} | {claim} | `{key}` | {tier} | **{res}** | {ref} | {ctx[:260]} |")
    open(os.path.join(HERE, "VERIFY.md"), "w").write("\n".join(out) + "\n")
    for cid, claim, key, tier, res, ctx, ref in rows:
        print(f"{res:10} {cid:4} {tier:9} {claim[:80]}")
    print(f"\n{n_ok}/{len(CLAIMS)} matched")


if __name__ == "__main__":
    main()
