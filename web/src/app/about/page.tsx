"use client";

import { useEffect, useState } from "react";
import { Card, Skeleton } from "@/components/ui";
import { MECHANISM } from "@/lib/labels";

type Proof = {
  seeds: number[];
  borrowers: number;
  fraud: number;
  honest: number;
  caught: number;
  catch_rate: number;
  false_alarms_per_100_end: number;
  false_alarms_per_100_ever: number;
  honest_needing_review_per_100: number;
  baseline_caught: number;
  baseline_catch_rate: number;
  baseline_false_alarms_per_100: number;
  median_days_earlier_than_audit: number | null;
  beyond_pledgecheck: number;
  per_mechanism: Record<string, [number, number]>;
  seconds_per_monthly_run: number;
};

const SYSTEMS: [string, string, string][] = [
  ["S1", "Collateral integrity", "Is the same collateral pledged twice? Uses PledgeCheck's result (simulated in this demo) plus checks inside the bank, and says when a borrower isn't enrolled, so other lenders can't be checked."],
  ["S2", "Tape vs source", "Does the loan file match the lender's own system? \"Pull this up on your screen,\" automated: it pulls the loans reported current that paid nothing, and catches credit scores rewritten to clear the eligibility line."],
  ["S3", "Cash provenance", "Who actually paid? Lender or affiliate money dressed up as customer payments is caught by the payer, and money sent out to a middleman that comes back as 'customer' cash is caught by the round trip."],
  ["S4", "Invoice authenticity", "Re-submitted invoices with new amounts, invoices the customer never pays, impossible amounts."],
  ["S5", "Hidden-debt finder", "Public lien filings and court records against the borrower and every company linked to it."],
  ["S6", "Relationship mapper", "Who shares the owner, address, phone number or registered agent? Shell-like companies that were never disclosed, even when a front person is on the paperwork."],
  ["S7", "Financial consistency", "Does reported revenue fit verified cash? Are receivables piling up far faster than revenue? Covenants repeatedly just clearing the line?"],
];

export default function AboutPage() {
  const [p, setP] = useState<Proof | null>(null);
  useEffect(() => {
    fetch("/proof.json", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<Proof>) : null))
      .then(setP)
      .catch(() => setP(null));
  }, []);

  return (
    <div className="max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">How it works</h1>
        <p className="mt-2 text-zinc-700">
          Banks have lent $1.32 trillion to non-bank lenders, 10% of all bank loans, and banks over $100 billion in
          assets hold about 86% of it (FDIC, February 2026). The worked example is Wells Fargo, whose largest commercial
          loan category is lending to non-bank financial firms: $208.8B, 20% of all its loans (10-Q, June 2026). Recent
          frauds against lenders in this market used several tricks at once, each hiding in a different place. One
          check reads one place, so Borrower Truth runs seven connected checks, and a combiner turns what they find
          into a solved case: the finding, the proof, a suggested fix and drafted paperwork, for a person to approve.
          It is a second pair of eyes next to covenants and field exams, not a fix for fraud.
        </p>
        <a
          href="/deck.html"
          className="mt-3 inline-block rounded text-sm font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          Read the full plan deck, with every source →
        </a>
        <a
          href="/memo.html"
          className="mt-3 inline-block rounded text-sm font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          Read the one-page proposal memo →
        </a>
      </div>

      <Card className="divide-y divide-zinc-100">
        {SYSTEMS.map(([k, name, what]) => (
          <div key={k} className="grid gap-1 px-4 py-3 sm:grid-cols-4">
            <div className="font-medium text-zinc-900">
              {k} {name}
            </div>
            <div className="text-sm text-zinc-600 sm:col-span-3">{what}</div>
          </div>
        ))}
      </Card>

      <div>
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">The proof, on synthetic data it never saw</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Held-out synthetic evaluation, seeds 1301–1305, scored once on 15 Oct 2026 under today&apos;s rules (rule
          version c147a0a636e6): <b className="font-medium text-zinc-900">249 of 250 planted fraud cases were flagged by
          month 24 (99.6% on this synthetic test set). This is not a measurement of real-world fraud detection
          accuracy.</b> Rules were tuned on six development books; these five books were never used before. The
          report file rounds that rate to a whole number; the exact figure is 99.6% (proof/CORRECTIONS.md).
        </p>
        <p className="mt-2 text-sm text-zinc-600">
          Honest synthetic borrowers: 0 of 350 flagged at month 24; 1 of 350 flagged at least once (B0054, months 21–22,
          also flagged under the previous rules). Across all 14 fresh sets: 2 of 5,121 flagged at month 24 and 7 of
          5,121 at least once. The previous rules&apos; evaluation (seeds 1201–1205): 248 of 250 flagged, 0 of 350 honest.
          Every fresh run, including the ones that failed, and the three blind red-team rounds are in the plan deck.
        </p>
        {!p ? (
          <Skeleton className="mt-3 h-40 w-full" />
        ) : (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Planted fraud cases flagged"
              value={`${p.caught} of ${p.fraud}`}
              sub={`${((100 * p.caught) / p.fraud).toFixed(1)}% by month 24, on synthetic books`}
            />
            <Metric
              label="Quarterly sample audit"
              value={`${p.baseline_caught} of ${p.fraud}`}
              sub={`${((100 * p.baseline_caught) / p.fraud).toFixed(1)}% on the same books`}
            />
            <Metric
              label="Earlier than the audit"
              value={p.median_days_earlier_than_audit != null ? `${p.median_days_earlier_than_audit} days` : "—"}
              sub="median, frauds both flagged"
            />
            <Metric label="Beyond PledgeCheck" value={`${p.beyond_pledgecheck} of ${p.caught}`} sub="flagged frauds its four checks never flagged" />
            <Metric
              label="Honest flagged at month 24"
              value={`${Math.round((p.false_alarms_per_100_end * p.honest) / 100)} of ${p.honest}`}
              sub={`at least once: ${Math.round((p.false_alarms_per_100_ever * p.honest) / 100)} of ${p.honest}`}
            />
            <Metric
              label="Honest borrowers to review"
              value={`${Math.round((p.honest_needing_review_per_100 * p.honest) / 100)} of ${p.honest}`}
              sub={`${p.honest_needing_review_per_100} per 100, 'worth a look': the real workload`}
            />
            <Metric label="One monthly run" value={`${p.seconds_per_monthly_run} s`} sub={`${p.borrowers / p.seeds.length} borrowers`} />
            <Metric label="Held-out books" value={`${p.seeds.length}`} sub={`seeds ${p.seeds[0]}–${p.seeds[p.seeds.length - 1]}, ${p.borrowers} borrowers`} />
          </div>
        )}
        {p && (
          <Card className="mt-3 divide-y divide-zinc-100 text-sm">
            {Object.entries(p.per_mechanism).map(([m, [hit, tot]]) => (
              <div key={m} className="flex items-center gap-3 px-4 py-2">
                <span className="w-56 text-zinc-900">{MECHANISM[m] ?? m}</span>
                <div className="h-1.5 flex-1 rounded-full bg-zinc-100">
                  <div className="h-1.5 rounded-full bg-blue-700" style={{ width: `${(100 * hit) / Math.max(tot, 1)}%` }} />
                </div>
                <span className="w-24 text-right tabular-nums text-zinc-600">
                  {hit}/{tot}
                </span>
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-zinc-900">{value}</div>
      <div className="mt-0.5 text-xs text-zinc-500">{sub}</div>
    </Card>
  );
}
