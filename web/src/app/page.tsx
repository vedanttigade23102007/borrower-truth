"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Card, EmptyState, ErrorState, Skeleton, VerdictBadge } from "@/components/ui";
import { fetchCases, fetchLatest } from "@/lib/api";
import { MECHANISM, SYSTEM, VERDICT } from "@/lib/labels";
import type { CaseSummary, RunStatus, SystemMetric, Verdict } from "@/lib/types";

const ORDER: Verdict[] = ["LIKELY_FRAUD", "NEEDS_MORE_EVIDENCE", "EXPLAINED", "NO_ISSUE"];
const STATUS_LABEL: Record<string, string> = {
  AWAITING_APPROVAL: "Awaiting approval",
  IN_PROGRESS: "In progress",
  RESOLVED: "Resolved",
  NO_ACTION: "—",
};

export default function QueuePage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [latest, setLatest] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Verdict | "ALL">("LIKELY_FRAUD");

  const load = useCallback(async () => {
    try {
      const [c, l] = await Promise.all([fetchCases(), fetchLatest()]);
      setCases(c);
      setLatest(l);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const shown = useMemo(
    () => (cases ?? []).filter((c) => filter === "ALL" || c.verdict === filter),
    [cases, filter],
  );

  const systems = latest
    ? Object.entries(latest.runMetrics).filter(
        (e): e is [string, SystemMetric] => typeof e[1] === "object" && e[1] !== null && e[0].startsWith("S"),
      )
    : [];

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Review queue</h1>
        <p className="mt-1 text-sm text-zinc-600">
          Loans to non-bank lenders, checked by seven connected systems.{" "}
          {latest?.asOf != null && <>Data as of month {latest.asOf + 1} of the synthetic timeline.</>}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {ORDER.map((v) => {
          const n = latest?.verdicts?.[v];
          const active = filter === v;
          return (
            <button
              key={v}
              onClick={() => setFilter(active ? "ALL" : v)}
              aria-pressed={active}
              className={`rounded-xl border bg-white p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
                active ? "border-blue-600 ring-1 ring-blue-600" : "border-zinc-200 hover:border-zinc-300"
              }`}
            >
              <div className="text-xs text-zinc-500">{VERDICT[v].label}</div>
              <div className="mt-1 text-2xl font-semibold tabular-nums text-zinc-900">
                {n == null ? <Skeleton className="h-7 w-10" /> : n}
              </div>
            </button>
          );
        })}
      </div>

      <Card className="flex flex-wrap items-center gap-2 px-4 py-3">
        <span className="mr-1 text-xs font-medium text-zinc-500">Checks in the last run</span>
        {systems.length === 0 && <Skeleton className="h-5 w-72" />}
        {systems.map(([k, m]) => (
          <span key={k} title={m.error ?? `${m.seconds}s, ${m.signals ?? 0} signals`}>
            <Badge tone={m.status === "ok" ? "emerald" : "red"}>
              {k} {SYSTEM[k]} {m.status === "ok" ? "" : "· unavailable"}
            </Badge>
          </span>
        ))}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-3">
          <h2 className="text-sm font-medium text-zinc-900">
            {filter === "ALL" ? "All borrowers" : VERDICT[filter].label}
            {cases && <span className="ml-2 text-zinc-500">{shown.length}</span>}
          </h2>
          {filter !== "ALL" && (
            <button
              onClick={() => setFilter("ALL")}
              className="rounded text-sm text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              Show all
            </button>
          )}
        </div>
        {!cases ? (
          <div className="space-y-3 p-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <EmptyState title="Nothing here" hint="No borrowers have this verdict in the current run." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Priority</th>
                  <th className="px-4 py-2 font-medium">Borrower</th>
                  <th className="px-4 py-2 font-medium">Verdict</th>
                  <th className="px-4 py-2 font-medium">What we found</th>
                  <th className="px-4 py-2 font-medium">Open steps</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100">
                {shown.map((c) => (
                  <tr key={c.borrowerId} className="group hover:bg-zinc-50">
                    <td className="px-4 py-3">
                      <div className="h-1.5 w-20 rounded-full bg-zinc-100" aria-label={`priority ${Math.round(c.priority * 100)}%`}>
                        <div className="h-1.5 rounded-full bg-blue-700" style={{ width: `${Math.round(c.priority * 100)}%` }} />
                      </div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      <Link
                        href={`/case/${c.borrowerId}`}
                        className="rounded font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
                      >
                        {c.borrowerId}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <VerdictBadge verdict={c.verdict} />
                    </td>
                    <td className="max-w-md px-4 py-3">
                      <div className="truncate text-zinc-900" title={c.headline}>
                        {c.headline}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {c.mechanisms.map((m) => (
                          <Badge key={m}>{MECHANISM[m] ?? m}</Badge>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-zinc-700">
                      {c.openSteps || "—"}
                      {(c.liveAlerts ?? 0) > 0 && (
                        <span className="ml-2">
                          <Badge tone="red">{c.liveAlerts} live</Badge>
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-zinc-600">{STATUS_LABEL[c.caseStatus] ?? c.caseStatus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
