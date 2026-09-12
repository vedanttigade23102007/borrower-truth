"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Badge, Card, ErrorState, Skeleton, VerdictBadge } from "@/components/ui";
import { MECHANISM, type Tone } from "@/lib/labels";
import { useStatic, type AnswerKey } from "@/lib/showcase";

const STATUS: Record<string, { tone: Tone; help: string }> = {
  caught: { tone: "red", help: "fraud planted, called likely fraud" },
  "sent to review": { tone: "amber", help: "fraud planted, sent to a person as 'worth a look'" },
  missed: { tone: "zinc", help: "fraud planted, not flagged" },
  "false alarm": { tone: "zinc", help: "honest, called likely fraud" },
  "worth a look (honest)": { tone: "sky", help: "honest, sent to a person: the review workload" },
  cleared: { tone: "emerald", help: "honest, no action" },
};
const ORDER = ["caught", "sent to review", "missed", "false alarm", "worth a look (honest)", "cleared"];

export default function TestPage() {
  const k = useStatic<AnswerKey>("/showcase/answer_key.json");
  const [filter, setFilter] = useState<string>("fraud");

  const rows = useMemo(() => {
    const all = k.data?.borrowers ?? [];
    if (filter === "fraud") return all.filter((b) => b.planted.length > 0);
    if (filter === "all") return all;
    return all.filter((b) => b.status === filter);
  }, [k.data, filter]);

  if (k.error) return <ErrorState message={k.error} onRetry={() => void k.retry()} />;
  if (!k.data) return <Skeleton className="h-96 w-full" />;
  const c = k.data.counts;
  const h = k.data.heldout;
  const tot = h.reduce(
    (a, s) => ({
      fraud: a.fraud + s.fraud,
      caught: a.caught + s.caught,
      review: a.review + s.sent_to_review,
      missed: a.missed + s.missed,
      fa: a.fa + s.false_alarms,
      look: a.look + s.honest_worth_a_look,
      honest: a.honest + (s.borrowers - s.fraud),
    }),
    { fraud: 0, caught: 0, review: 0, missed: 0, fa: 0, look: 0, honest: 0 },
  );
  const mech: Record<string, [number, number]> = {};
  h.forEach((s) =>
    Object.entries(s.per_mechanism).forEach(([m, [hit, n]]) => {
      const cur = mech[m] ?? [0, 0];
      mech[m] = [cur[0] + hit, cur[1] + n];
    }),
  );
  const weakest = Object.entries(mech).sort((a, b) => a[1][0] / a[1][1] - b[1][0] / b[1][1])[0];
  const nAll = k.data.borrowers.length;
  const nFraud = k.data.borrowers.filter((b) => b.planted.length > 0).length;

  return (
    <div className="space-y-10">
      <div className="max-w-4xl">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Test it yourself</h1>
        <p className="mt-2 text-zinc-700">
          Fraud was planted in {nFraud} of the {nAll} demo borrowers. Here is the answer key next to what the system
          said, misses and review workload included. Open any borrower to see the evidence and judge the call yourself.
        </p>
      </div>

      <section className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              aria-pressed={filter === s}
              className={`rounded-xl border bg-white p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                filter === s ? "border-zinc-900 ring-1 ring-zinc-900" : "border-zinc-200 hover:bg-zinc-50"
              }`}
            >
              <div className="text-2xl font-semibold tabular-nums text-zinc-900">{c[s] ?? 0}</div>
              <div className="text-sm font-medium text-zinc-900">{s}</div>
              <div className="text-xs text-zinc-500">{STATUS[s].help}</div>
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-zinc-500">Show</span>
          {[
            ["fraud", `all ${nFraud} frauds`],
            ["all", `all ${nAll} borrowers`],
          ].map(([v, l]) => (
            <button
              key={v}
              onClick={() => setFilter(v)}
              aria-pressed={filter === v}
              className={`rounded-md px-3 py-1 focus-visible:outline-2 focus-visible:outline-blue-600 ${filter === v ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200"}`}
            >
              {l}
            </button>
          ))}
          <span className="text-zinc-500">· {rows.length} shown</span>
        </div>
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">borrower</th>
                <th scope="col" className="px-4 py-2 font-medium">planted (answer key)</th>
                <th scope="col" className="px-4 py-2 font-medium">innocent look-alikes</th>
                <th scope="col" className="px-4 py-2 font-medium">system said</th>
                <th scope="col" className="px-4 py-2 font-medium">result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map((b) => (
                <tr key={b.borrower_id} className="align-top">
                  <td className="px-4 py-2">
                    <Link href={`/case/${b.borrower_id}`} className="rounded font-mono text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
                      {b.borrower_id}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    {b.planted.length === 0 ? (
                      <span className="text-zinc-400">honest</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {b.planted.map((m) => (
                          <Badge key={m} tone={b.right_mechanisms.includes(m) ? "emerald" : "zinc"}>
                            {b.right_mechanisms.includes(m) ? "✓" : "✗"} {MECHANISM[m] ?? m}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-zinc-600">{b.lookalikes.map((x) => x.toLowerCase().replace(/_/g, " ")).join(", ") || "—"}</td>
                  <td className="px-4 py-2">
                    <VerdictBadge verdict={b.verdict} />
                  </td>
                  <td className="px-4 py-2">
                    <Badge tone={STATUS[b.status]?.tone ?? "zinc"}>{b.status}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <p className="text-xs text-zinc-500">
          ✓ = the system named that exact trick, ✗ = it did not. This demo book is the one the rules were built on, so it
          flatters them. The honest test is below.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">The honest test: {h.length} books it never saw</h2>
        <p className="max-w-4xl text-sm text-zinc-600">
          {h.length} fresh books generated after the rules were frozen: {tot.fraud + tot.honest} borrowers and{" "}
          {tot.fraud} planted frauds, including the two harder variants (a front-person shell and a round trip through a
          middleman).
        </p>
        <Card className="overflow-x-auto">
          <table className="w-full text-right text-sm tabular-nums">
            <thead className="bg-zinc-50 text-xs text-zinc-500">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-medium">book</th>
                <th scope="col" className="px-4 py-2 font-medium">frauds</th>
                <th scope="col" className="px-4 py-2 font-medium">caught</th>
                <th scope="col" className="px-4 py-2 font-medium">sent to review</th>
                <th scope="col" className="px-4 py-2 font-medium">missed</th>
                <th scope="col" className="px-4 py-2 font-medium">false alarms</th>
                <th scope="col" className="px-4 py-2 font-medium">honest worth a look</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {h.map((s) => (
                <tr key={s.seed}>
                  <td className="px-4 py-1.5 text-left font-mono text-xs">seed {s.seed}</td>
                  <td className="px-4 py-1.5">{s.fraud}</td>
                  <td className="px-4 py-1.5">{s.caught}</td>
                  <td className="px-4 py-1.5">{s.sent_to_review}</td>
                  <td className="px-4 py-1.5">{s.missed}</td>
                  <td className="px-4 py-1.5">{s.false_alarms}</td>
                  <td className="px-4 py-1.5">
                    {s.honest_worth_a_look} of {s.borrowers - s.fraud}
                  </td>
                </tr>
              ))}
              <tr className="bg-zinc-50 font-medium text-zinc-900">
                <td className="px-4 py-2 text-left">total</td>
                <td className="px-4 py-2">{tot.fraud}</td>
                <td className="px-4 py-2">
                  {tot.caught} ({Math.round((100 * tot.caught) / tot.fraud)}%)
                </td>
                <td className="px-4 py-2">{tot.review}</td>
                <td className="px-4 py-2">{tot.missed}</td>
                <td className="px-4 py-2">{tot.fa}</td>
                <td className="px-4 py-2">
                  {tot.look} of {tot.honest}
                </td>
              </tr>
            </tbody>
          </table>
        </Card>
        <Card className="divide-y divide-zinc-100 text-sm">
          {Object.entries(mech).map(([m, [hit, n]]) => (
            <div key={m} className="flex items-center gap-3 px-4 py-2">
              <span className="w-56 text-zinc-900">{MECHANISM[m] ?? m}</span>
              <div className="h-1.5 flex-1 rounded-full bg-zinc-100">
                <div className={`h-1.5 rounded-full ${hit < n ? "bg-amber-500" : "bg-blue-700"}`} style={{ width: `${(100 * hit) / Math.max(n, 1)}%` }} />
              </div>
              <span className="w-20 text-right tabular-nums text-zinc-600">
                {hit}/{n}
              </span>
            </div>
          ))}
        </Card>
        {weakest && (
          <p className="max-w-4xl text-sm text-zinc-700">
            <span className="font-medium">Where it is weakest:</span> {MECHANISM[weakest[0]] ?? weakest[0]}, {weakest[1][0]} of{" "}
            {weakest[1][1]} named correctly. The borrower is usually still flagged through other checks, but this trick is
            the one to strengthen next. The honest workload is the other cost: {tot.look} of {tot.honest} honest borrowers
            were sent to a person as &ldquo;worth a look&rdquo;.
          </p>
        )}
      </section>
    </div>
  );
}
