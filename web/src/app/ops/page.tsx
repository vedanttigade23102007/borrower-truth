"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Card, ErrorState, Skeleton } from "@/components/ui";
import { fetchLatest } from "@/lib/api";
import { SYSTEM, fmtDate } from "@/lib/labels";
import type { RunStatus, SystemMetric } from "@/lib/types";

type Scale = { borrowers: number; scale: number; rows: number; seconds: number; rows_per_second: number };

const GRAFANA = process.env.NEXT_PUBLIC_GRAFANA_URL;

const FALLBACKS = [
  ["A check crashes or times out", "The case still builds and says which check was unavailable; the others keep running."],
  ["A message fails", "Retried with backoff, then parked in a dead-letter queue to replay; nothing is lost."],
  ["The document model is down", "Letters fall back to deterministic templates; every draft records which path wrote it."],
  ["A public data source is down", "The cached copy is used and marked with how stale it is."],
  ["A borrower file is malformed", "It's quarantined; the last good data is kept and an alert is raised."],
  ["The case service is down", "The pipeline parks the run and replays it when the service is back."],
];

export default function OpsPage() {
  const [latest, setLatest] = useState<RunStatus | null>(null);
  const [scale, setScale] = useState<Scale[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLatest(await fetchLatest());
      const r = await fetch("/scale.json", { cache: "no-store" });
      setScale(r.ok ? ((await r.json()) as Scale[]) : []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  // only entries that are checks (they carry a status and a timing); other run metadata is shown separately
  const rows = latest
    ? Object.entries(latest.runMetrics).filter(
        (e): e is [string, SystemMetric] =>
          typeof e[1] === "object" && e[1] !== null && "status" in e[1] && typeof (e[1] as SystemMetric).seconds === "number",
      )
    : [];
  const total = latest?.runMetrics["total_seconds"];
  const dq = latest?.runMetrics["data_quality"] as
    | { checked?: number; quarantined?: Record<string, { issues: string[]; using: string }> }
    | undefined;
  const quarantined = Object.entries(dq?.quarantined ?? {});

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Operations</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Last run {fmtDate(latest?.receivedAt)}
            {typeof total === "number" && <> · all checks and the combiner in {total.toFixed(2)} s</>}
          </p>
        </div>
        {GRAFANA && (
          <a
            href={GRAFANA}
            target="_blank"
            rel="noreferrer"
            className="rounded-md bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            Open live dashboard
          </a>
        )}
      </div>

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">Each check in the last run</h2>
        {!latest ? (
          <div className="p-4">
            <Skeleton className="h-40 w-full" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Check</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 text-right font-medium">Seconds</th>
                <th className="px-4 py-2 text-right font-medium">Output</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {rows.map(([k, m]) => (
                <tr key={k}>
                  <td className="px-4 py-2 text-zinc-900">
                    {k} {SYSTEM[k]}
                  </td>
                  <td className="px-4 py-2">
                    <Badge tone={m.status === "ok" ? "emerald" : "red"}>{m.status}</Badge>
                    {m.error && <span className="ml-2 text-xs text-red-700">{m.error}</span>}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">{m.seconds.toFixed(3)}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {m.signals ?? m.cases ?? 0} {k === "combiner" ? "cases" : "signals"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {dq && (
        <Card className="px-4 py-3 text-sm">
          <span className="font-medium text-zinc-900">Input data quality: </span>
          {quarantined.length === 0 ? (
            <span className="text-zinc-600">all {dq.checked ?? 0} input files passed their checks.</span>
          ) : (
            <span className="text-red-700">
              {quarantined.map(([t, v]) => `${t} quarantined (${v.issues[0]}; using ${v.using})`).join(" · ")}
            </span>
          )}
        </Card>
      )}

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">
          Scale test: all seven checks, one laptop
        </h2>
        {!scale ? (
          <div className="p-4">
            <Skeleton className="h-24 w-full" />
          </div>
        ) : scale.length === 0 ? (
          <p className="px-4 py-6 text-sm text-zinc-500">No scale results published yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-zinc-50 text-left text-xs text-zinc-500">
              <tr>
                <th className="px-4 py-2 font-medium">Borrowers</th>
                <th className="px-4 py-2 text-right font-medium">Rows</th>
                <th className="px-4 py-2 text-right font-medium">Seconds</th>
                <th className="px-4 py-2 text-right font-medium">Rows per second</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 tabular-nums">
              {scale.map((s) => (
                <tr key={s.rows}>
                  <td className="px-4 py-2">{s.borrowers.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">{s.rows.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right">{s.seconds.toFixed(2)}</td>
                  <td className="px-4 py-2 text-right">{s.rows_per_second.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-500">
          Measured on an 8 GB laptop with synthetic data. Each borrower is checked independently, so work splits across
          machines; bank-scale capacity is an extrapolation from this curve, not a claim.
        </p>
      </Card>

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">When something breaks</h2>
        <dl className="divide-y divide-zinc-100 text-sm">
          {FALLBACKS.map(([k, v]) => (
            <div key={k} className="grid gap-1 px-4 py-3 sm:grid-cols-3">
              <dt className="font-medium text-zinc-900">{k}</dt>
              <dd className="text-zinc-600 sm:col-span-2">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>
    </div>
  );
}
