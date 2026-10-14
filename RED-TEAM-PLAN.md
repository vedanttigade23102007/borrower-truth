# Red team plan (step 5): a blind attack on Borrower Truth

**Status: approved by Vedant on 1 Oct 2026, with changes (below). The harness and the briefing are built and frozen with the code (tag `redteam-frozen`). The red team hasn't run yet.** Buyer review gap 4 (the review is kept private).

**Vedant's decisions (1 Oct 2026):**
1. **The red team is option (b), on claude.ai.** Vedant runs it himself, in a new incognito chat. He uploads the sealed briefing as one zip, pastes a fixed first message, and brings the attacks back as a zip.
2. **The leak scan runs on the briefing itself, before upload.** Vedant reads the briefing and the scan result first.
3. **Decisions 2, 3 and 4 as recommended:** the attacker may falsify its own servicer records (results reported with and without that lever); the size floor is 5% of the credit limit; the pass bar is the table in section 6.
4. **The code is tagged before he starts the chat.**
5. **(Added the same day, before anything ran.) A company's history is a partial lever too.** It covers when a company was formed and whether it shows a real business. A real borrower can only partly fake these, for example by buying an old shelf company or dressing up a shell. So, like the servicer lever:
   - it is allowed, and stated in the red team's README
   - the harness detects it: a changed `formed_month` or `has_operations`, or a new company formed before month 0 or one showing a real business
   - results are reported with and without it

   The briefing was rebuilt, re-scanned and re-frozen. The tag moved to the new commit, and both were pushed to `borrower-truth-private` so the freeze has a timestamp before the attack starts.

---

## Why we need it, in one paragraph

Every fraud in the test books so far was invented by the same author who wrote the checks. That's like a teacher marking an exam they also wrote: 248 of 250 caught proves the checks catch the tricks the author thought of, and nothing more. A model-risk reviewer at any bank will say this first. The fix is to let someone else try to beat the system **without seeing how it works**, plant their frauds into fresh books, score them once, and publish every miss.

## The picture

```
                       SEALED BRIEFING (all the red team sees)
                       - what each data table is (no rules, no thresholds)
                       - one honest sample book (no frauds, no labels)
                       - the public DOJ/SEC allegations (First Brands, Tricolor)
                       - the rules of engagement (below)
                                   │
                                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │ RED TEAM: an AI agent that has never seen our code        │
   │ writes up to 8 attacks. Each one = a story + a script     │
   │ that plants the fraud into one honest borrower's data     │
   └───────────────────────────────────────────────────────────┘
                                   │  one submission, no feedback
                                   ▼
   CODE FROZEN (git tag, before the red team starts) ───────────┐
                                   │                            │
   fresh seeds 501-505 (never used)│                            │
        ┌──────────────────────────┴───────────┐                │
        ▼                                      ▼                │
   COPY A: the books as generated     COPY B: same books, each  │
   (our usual planted frauds)         attack planted into 2     │
        │                             honest borrowers per book │
        ▼                                      ▼                │
   SCORED ONCE                        SCORED ONCE  ◄────────────┘
   = the fresh held-out run           = the red-team result
        │                                      │
        └──────────────┬───────────────────────┘
                       ▼
        PUBLISHED AS IS: proof/REDTEAM.md, every miss explained
                       ▼
        Each miss: Vedant decides FIX or KNOWN LIMIT
                       ▼
        If anything was fixed: one more run on NEW fresh seeds 601-605
        (labelled "after fixes": those attacks are no longer blind)
```

---

## 1. Who the red team is, and what "blind" means

- **Who:** a separate AI agent (a fresh Claude session with no memory of this project), started with only the sealed briefing. It works in a folder outside the repository.
- **What it sees:**
  1. A plain description of each data table: what it is and what its columns mean. These are the same descriptions the public data page shows.
  2. One honest sample book, so it knows what normal looks like. It is generated on a seed never used for scoring. The generator always plants at least two frauds, so every borrower with a planted fraud is stripped out, and so are the labels and the generator's notes. Those would reveal our list of fraud types.
  3. The primary DOJ and SEC allegation texts for First Brands and Tricolor, already saved in `research/sources/`.
  4. The rules of engagement (section 2).
- **What it never sees:**
  - our checks (`bt/systems`), the combiner, any threshold
  - the generator code, which holds our list of fraud types
  - the buyer review and the decision log (both kept private) and DATA-CONTRACT.md, which name the checks
  - the proof reports, the website, the deck and the case study
- **It can't test against us.** Our pipeline isn't in its folder, and it is told not to run it. A real fraudster can't run the bank's monitoring either. It may run its own scripts on the honest sample book, to check they work.
- **How blindness is checked.** It's enforced by instruction, not by a locked sandbox, because the agent runs on this same machine. Afterwards, a **leak scan** searches everything it hands in for our internal names, check codes and threshold numbers. A hit is reported as a possible leak, and that attack is marked as not blind.

## 2. The rules of engagement (what the red team must follow)

**What a borrower controls, so the attack may change it:**
- everything it reports to the bank: the loan tape, invoices, financial statements, covenant figures and disclosures
- companies it forms: owners, officers, addresses, phone numbers and registered agents of its choice, including nominees (a friend named as the owner)
- money it moves: who pays into the collection account, and what leaves its operating account
- loans it sells into its own public securitizations, and its own SEC filings
- **its own servicer system.** Many non-bank lenders service their own loans, so a determined fraudster can falsify those records too. (Decision 2 below.)
- **its companies' history:** when a company was formed, and whether it shows a real business. A borrower can only partly fake these (an old shelf company, a dressed-up shell). This lever is detected by the harness and reported apart, like the servicer lever.

**What it doesn't control, so the attack may not change it:**
- other lenders' lien filings
- court records
- the LEI register (it may simply not get an LEI)
- PledgeCheck's results (it may choose not to enrol)
- the bank's own records of what arrived in the collection account

**Size.** An attack counts only if the fraudster gains at least **5% of that borrower's credit limit** over the 24 months. The gain can be collateral overstated, debt hidden, or cash diverted or dressed up. Each attack states its gain in dollars. Smaller attacks are reported, but scored apart as "too small to matter". (Decision 3.)

**Timing.** The fraud must start by month 18 of 24, so there are at least 6 months of data in which it could be seen.

**Variety.** Up to 8 attacks, each a different trick. At least half must follow something alleged in the DOJ/SEC texts. The rest can be new.

**What it hands in, per attack:**
- `README.md`: the story in plain words, the allegation it follows (if any), the levers it pulls, the dollar gain, and why it expects a bank's monitoring to miss it.
- `plant.py`: a function that takes one honest borrower in a book and plants the fraud into that borrower's data, without changing the table layouts.
- It hands in once. No feedback, no second try.

## 3. How it's scored, once

1. **Freeze the code first.** Before the red team starts, the code gets a git tag (`redteam-frozen`). The scoring must run on exactly that commit, and every decision record carries the commit, so anyone can check. Between the red team starting and the scoring, no rule, threshold or check changes.
2. **Fresh books.** Seeds 501–505, never generated or scored before. They use the same settings as the headline run (120 borrowers per book, generator v3).
3. **Two copies of each book:**
   - **Copy A** is the book as generated, with our usual planted frauds. Scoring it is the **fresh held-out run** the finish line needs (item 5).
   - **Copy B** is the same book with each attack planted into 2 honest borrowers of the right type (a car lender or an invoice lender). They are picked at random with a recorded seed, so it can be repeated. Up to 8 attacks × 2 borrowers × 5 books = up to 80 red-team frauds.
4. **Same scoring as the headline.** Each book is run month by month (24 runs). Each red-team fraud ends in one of three places at month 24:
   - **caught** (likely fraud)
   - **sent to review** (worth a look)
   - **missed** (no issue, or explained)

   Also recorded: the month it was first flagged, and which kinds of finding fired. False alarms are counted on the honest borrowers left in copy B.
5. **I read every `plant.py` before running it,** because it is code that runs on this Mac. I check that it only edits the book files. If a script crashes, I may fix only the crash. I never change what the attack does, and every such fix is logged.

## 4. A worked example (made up, only to show the flow)

> **Attack "friendly supplier":** the borrower pays a supplier it secretly controls, and the supplier sends the money back as if a customer paid an invoice.
> - Planted into 2 honest invoice lenders in each of the 5 books = 10 frauds.
> - Stated gain: $1.4M per borrower, 9% of the credit limit, so it counts.
> - **Made-up result:** 7 caught, 2 sent to review, 1 missed.
> - In REDTEAM.md the miss is shown in full. The borrower's round trips happened through a second bank account the bank doesn't hold, so no check could see the money leave.
> - Vedant decides: **known limit** ("we only see accounts we hold; ask for statements of every account"), or **fix** (for example, ask for those statements in the data contract).

The numbers above are invented to show the shape of the result. They are not a prediction.

## 5. What happens after the score

- **Everything is published as it came out:** every attack, every miss and the false alarms, in `proof/REDTEAM.md`, labelled synthetic and "attacks designed by an AI red team that had not seen the rules".
- **Every miss gets a decision from Vedant,** logged in the decision log (kept private):
  - **fix it:** a reason, a change and a test, or
  - **known limit:** a reason, written in the docs and the pitch.
- **If anything was fixed,** one more run on new fresh seeds 601–605, copy A and copy B. It is labelled "after fixes": those attacks are no longer blind, because we tuned to them. If nothing was fixed, the 501–505 copy A run is the fresh held-out run.
- **The last fresh run becomes the new headline,** and the document pass updates every quoted number.

## 6. What the fresh run must reach to "pass" (fixed now, before any data exists)

These are set before the run, so the bar can't move after the result is known. (Decision 4.)

| Measure | Pass bar | For comparison: headline (406–410) | Dev books today |
|---|---|---|---|
| Planted frauds caught by month 24 | at least 95% | 248/250 (99%) | 298/300 |
| Honest borrowers flagged at month 24 | 0 | 0 of 350 | 0 of 420 |
| Honest borrowers sent to "worth a look", per 100 | at most 35 | 29.1 | 27.9 |
| Every check ran on every case | yes | yes | yes |

The red-team result has **no pass bar**. It's a measurement, published as is. The rule is that every miss is fixed or written down.

## 7. Limits we'll state with the result

- **Blind to the code, not independent like a human team.** The red team is the same family of AI model that helped write the checks, so their blind spots may overlap. A human red team would be stronger. That's a pilot step for a bank.
- **Synthetic world.** Attacks can only use what our data layout records. A real fraudster has more levers: forged paper, bribed staff, other banks.
- **Blindness by instruction,** checked by the leak scan, not locked by a sandbox.
- **One round.** A later, optional round 2 could let a red team read the public website first: the "informed fraudster" who has seen the product's marketing.

## 8. Decisions I need from Vedant before anything runs

| # | Decision | My recommendation |
|---|---|---|
| 1 | Who runs the red team: (a) an AI agent I start with only the sealed briefing; (b) a separate session **you** start in an empty folder holding only the briefing (stronger blindness, a few minutes of your time); (c) a human | **(a)**, with the leak scan. Choose (b) if you want blindness that doesn't depend on my instructions. |
| 2 | May the attacker falsify its own servicer system? | **Yes.** Many non-bank lenders are their own servicer, and leaving it out would flatter us. Results are reported with and without this lever. |
| 3 | Size floor | **5% of the borrower's credit limit** over the 24 months |
| 4 | Pass bar for the fresh run | **The table in section 6** |

**Time.**
- Me: writing the briefing and the scoring harness first (both frozen with the code), then reading the attacks, scoring and writing up. About half a day of work.
- The red team: about an hour.
- You: these 4 decisions now, then a fix-or-limit call on each miss.

**Nothing on the "ask Vedant" list is involved.** No install, no message, no key, and no change to who can see the site.
