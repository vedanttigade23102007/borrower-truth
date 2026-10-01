# Red team, round 2: plan

**Status: plan only. Nothing for round 2 has been built or run.** Written 2 Oct 2026 for Vedant to read and approve, after the round-1 fixes and the fresh 601–605 run (`proof/REDTEAM_after_fixes.md`).

## Why a second round

- **Round 1 was blind.** Its result is published: 19 of 80 caught, 21 sent to review, 40 missed.
- **The fixes since were tuned on those very attacks.** So the 601–605 run shows whether the fixes hold on fresh books. It can't show how a *new* attacker would do.
- **Only a new, blind attacker can answer that.**

Round 2 also closes a gap Vedant found in round 1: three attacks recorded money as paid by someone other than the real sender.

## What changes from round 1

| | Round 1 | Round 2 |
|---|---|---|
| Attacker | a new incognito claude.ai chat | **a new incognito chat with a different model** if the model picker offers one, so the attacker shares fewer blind spots with round 1 and with the author of the checks |
| What it sees | the briefing, an honest sample book, the DOJ/SEC texts | the same kinds of thing, rebuilt: **a new sample book** on an unused seed, from the corrected generator (credit limits sized to the collateral). **Never** round 1's attacks, results or fixes, because those would anchor it |
| Payments | added payments could name anyone as payer | **a payment shows its real sender.** Money the borrower sends, directly or through a company it controls, must name that company as payer. It may not appear to come from a customer, real or invented |
| Levers | servicer records; company history | the same two partial levers, reported with and without |
| Size and timing | at least 5% of the credit limit; start by month 18 | the same. 5% now means about a tenth of a borrower's collateral, because the limits are realistic |
| Scoring books | fresh seeds 501–505 | **fresh seeds 701–705**, never generated before |
| Freeze | tag `redteam-frozen`, pushed before the chat | a new tag, `redteam-round2-frozen`, pushed before the chat |

## How "a payment shows its real sender" is enforced

The harness, written and frozen before the chat, rejects any planted payment into the collection account whose payer is not one of these:
- the borrower's own company
- a company whose officer is the borrower's owner
- a company the attack itself creates

A plant that breaks the rule is reverted and reported, never repaired, the same as any other rule break. The briefing states the rule plainly, with one sentence of reason: "a bank's record of an incoming payment names the account the money came from".

## The steps, in order

1. **Build first, frozen with the code:**
   - the payer rule in the harness, with a test
   - the round-2 briefing (README with the new rule; the same table guide and DOJ/SEC texts; a new sample book)
   - leak scan of the briefing. Vedant reads the briefing and the scan before upload, as in round 1.
2. **Freeze:** tag `redteam-round2-frozen`, record the rules version and the briefing's fingerprint, and push to `borrower-truth-private`.
3. **Vedant runs the chat:** a new incognito chat, a different model if offered, web search off, code execution on. He pastes the same first message as round 1 and brings back `attacks.zip`.
4. **Leak-scan the attacks and read every script** before running anything.
5. **Plant and score once** on seeds 701–705:
   - **copy A** (the books as generated) is also a fresh held-out run
   - **copy B** has the attacks planted
6. **Publish as it came out** (`proof/REDTEAM_round2.md`). Then each miss is Vedant's call: fix it (by mechanism, never one attack) or record it as a known limit.
   - If anything is fixed, the fresh held-out run the finish line needs (item 5) moves to a new set of seeds again.
   - If nothing is fixed, copy A of 701–705 is that run.

## What stays the same

- **The pass bar for copy A:** at least 95% caught, 0 honest flagged, at most 35 per 100 sent to review, every check ran.
- **The red-team result has no pass bar.** It's published as is.
- **Nothing on the "ask Vedant" list is involved.** No install, no message, no key, and no change to who can see the site.

## Limits we'll state with the result

- **The attacker is still an AI,** and of the same broad kind as the one that helped write the checks.
- **The data is still synthetic,** and the attack can only use what our tables record.
- **Blindness rests on instructions** and a leak scan, plus the chat having no access to this Mac.
- **A later round 3 could be an "informed fraudster"** that reads the public website first. Not part of this plan.

## Decision for Vedant

- **Which model runs the attacker:** if claude.ai offers another model, the plan recommends it. You'll know which model round 1 used.
- Everything else follows the round-1 decisions unless you change it.
