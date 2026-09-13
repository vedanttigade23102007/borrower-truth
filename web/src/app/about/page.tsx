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
  ["S1", "Collateral integrity", "Is the same collateral pledged twice? Uses PledgeCheck's result plus checks inside the bank, and says when a borrower isn't enrolled, so other lenders can't be checked."],
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
          Wells Fargo&apos;s largest commercial loan category is lending to non-bank financial firms: $208.8B, 20% of all
          loans (10-Q, June 2026). Recent frauds against lenders in this market used several tricks at once, each
          hiding in a different place. One check reads one place, so Borrower Truth runs seven connected checks, and a
          combiner turns what they find into a solved case: the finding, the proof, a suggested fix and drafted
          paperwork, for a person to approve.
        </p>
        <a
          href="/deck.html"
          className="mt-3 inline-block rounded text-sm font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          Read the full plan deck, with every source →
        </a>
      </div>

      <div>
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">Two short videos</h2>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          {[
            ["overview", "Overview", "The problem, who it's for, what it does, what other tools miss, and the proof."],
            ["training", "Training walkthrough", "How a credit officer uses it: queue, case, evidence, agent memo, fix, approval."],
          ].map(([file, title, what]) => (
            <Card key={file} className="overflow-hidden">
              <video
                controls
                preload="none"
                poster={`/videos/${file}.jpg`}
                className="aspect-video w-full bg-zinc-100"
                aria-label={`${title} video`}
              >
                <source src={`/videos/${file}.mp4`} type="video/mp4" />
              </video>
              <div className="px-4 py-3">
                <div className="font-medium text-zinc-900">{title}</div>
                <p className="text-sm text-zinc-600">{what}</p>
              </div>
            </Card>
          ))}
        </div>
        <p className="mt-2 text-xs text-zinc-500">Narrated with a synthetic voice, with captions. All data shown is synthetic.</p>
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
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">The proof, on data it never saw</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Rules were tuned on one synthetic book; these numbers come from five fresh ones. All synthetic: they prove
          coverage of the documented fraud mechanisms, not real-world catch rates.
        </p>
        {!p ? (
          <Skeleton className="mt-3 h-40 w-full" />
        ) : (
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Frauds caught" value={`${Math.round(p.catch_rate * 100)}%`} sub={`${p.caught} of ${p.fraud}`} />
            <Metric
              label="Quarterly sample audit"
              value={`${Math.round(p.baseline_catch_rate * 100)}%`}
              sub={`${p.baseline_caught} of ${p.fraud}`}
            />
            <Metric
              label="Earlier than the audit"
              value={p.median_days_earlier_than_audit != null ? `${p.median_days_earlier_than_audit} days` : "—"}
              sub="median, frauds both caught"
            />
            <Metric label="Beyond PledgeCheck" value={`${p.beyond_pledgecheck}`} sub="frauds its four checks never flagged" />
            <Metric
              label="Honest borrowers flagged"
              value={`${p.false_alarms_per_100_end} / 100`}
              sub={`audit: ${p.baseline_false_alarms_per_100} / 100`}
            />
            <Metric
              label="Honest borrowers to review"
              value={`${p.honest_needing_review_per_100} / 100`}
              sub="'worth a look': the real workload"
            />
            <Metric label="One monthly run" value={`${p.seconds_per_monthly_run} s`} sub={`${p.borrowers / p.seeds.length} borrowers`} />
            <Metric label="Held-out books" value={`${p.seeds.length}`} sub={`${p.borrowers} borrowers in total`} />
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
