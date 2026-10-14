# Red team, round 3: the record, written before it ran

**All data synthetic.** Written 2 Oct 2026, before the attack started. Decisions: the decision log (kept private), "red team round 3".

| | Round 3 |
|---|---|
| Attacker | **OpenAI Codex, run by a friend on their own machine.** Exact model: to be given by Vedant |
| Why this attacker | a different company's model: rounds 1 and 2 used Claude models, the same family as the model that helped write the checks |
| Briefing | the round-2 briefing, unchanged: `proof/redteam/round2/redteam_briefing_round2.zip`, sha256 `e8068ee87807425b37e1b2e6f11354a0456f4f096d90e02cdcb0c74326b98dcc` |
| Rules of engagement | as in round 2: realistic credit limits, the payer rule, the servicer and company-history levers (reported with and without), 5% size floor, start by month 18 |
| Leak scan | the same 3 innocent hits as round 2, against today's 88 forbidden terms (`LEAK-SCAN-briefing.md`) |
| Rules frozen | tag `redteam-round3-frozen`, `FROZEN.json`, pushed before the friend starts |
| Scoring seeds | **1001–1005**, never generated before |
| What it is | **a measurement only.** Published as it comes out. No fixes before outreach: each miss becomes a known limit, or goes on a list for after outreach |

## For the friend

1. **Python 3 with `pyarrow` and `numpy` installed** before starting. The attack scripts may use only those, and Codex will have no internet to install anything.
2. **A new, empty folder** holding only `redteam_briefing_round2.zip`. Start Codex in that folder, so it can't see any other files.
3. **No internet access and no web search** for Codex, set in its own settings.
4. Paste this as the first message:

```text
This is a defensive fraud-detection test on synthetic data. redteam_briefing_round2.zip is in this folder.

1. Unzip it and read redteam_briefing_round2/README.md first, then TABLES.md. Follow README.md exactly: you are the red team it describes.
2. Work only from the files in the zip. You have no internet access and no web search: don't try to use either. Do not look up the bank, either company, or any project or code that checks loans. If anything in the files seems to reveal how the bank checks, don't use it, and tell me.
3. Use your code tool to explore sample_book/ and to test every plant.py on a copy of it.
4. I can't answer questions about how the bank checks. Decide for yourself from the files.
5. When you're finished, save one file in this folder: attacks.zip, in the format README.md describes. Also give me a short list of the attacks: the name, one line each, the gain as a % of the credit limit, and whether it uses the servicer records, faked company history, or a customer as an accomplice.
```

5. Answer any question with only "decide from the files".
6. Send back `attacks.zip`, unedited, together with Codex's short list of attacks. Vedant saves it as `wells fargo/proof/redteam/round3/attacks.zip`.

**The only change from round 2's message:** the zip is in the folder rather than attached to a chat, the result is saved rather than downloaded, and point 2 says plainly that there's no internet and no web search.

## When it's back

1. Leak-scan the attacks.
2. Read every script before running anything.
3. Plant them, with the payer rule on. A plant that breaks the rules is reverted, never repaired.
4. Score once on 1001–1005: copy A (the books as generated) and copy B (attacks planted).
5. Publish both as they come out, with the exact model name.
