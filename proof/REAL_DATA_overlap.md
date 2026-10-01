# Public-pool overlap: the tolerance against real loans

Real SEC ABS-EE data: 787,944 open loans in 28 trusts of 22 lenders; 6 lenders have two or more trusts. Different trusts of one lender hold different loans, so every match below is a false one. The check needs 3 or more matched loans, two months running, before it notes anything.

| Matching rule | Trust pairs with any match | Pairs with enough matches to trip the check | Largest |
|---|---|---|---|
| exact match (before 2 Oct 2026) | 0 | 0 | 0 loans |
| the check's tolerance | 0 | 0 | 0 loans |
| looser, for comparison: amount 3%, score 10, origination month +-1 | 1 | 0 | 2 loans |

The check uses amount within 2% and credit score within 10 points, all other fields exact. Limit: only 6 lenders have two trusts here, so this tests cross-trust near-duplicates, not every way a match could go wrong.
