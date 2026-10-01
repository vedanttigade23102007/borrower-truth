"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, ErrorState, Skeleton } from "@/components/ui";
import {
  LARGE_AMOUNT,
  fetchFeedback,
  fetchLatest,
  fetchSecondChecks,
  reviewSecondCheck,
  type FeedbackRow,
  type SecondCheck,
} from "@/lib/api";
import { MECHANISM, SYSTEM, fmtDate } from "@/lib/labels";
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
  const [feedback, setFeedback] = useState<FeedbackRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    Promise.all([
      fetchLatest(),
      fetch("/scale.json", { cache: "no-store" }).then((r) => (r.ok ? (r.json() as Promise<Scale[]>) : [])),
      fetchFeedback().catch(() => [] as FeedbackRow[]),
    ])
      .then(([l, s, f]) => {
        if (!live) return;
        setLatest(l);
        setScale(s);
        setFeedback(f);
        setError(null);
      })
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [attempt]);

  if (error) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />;

  // only entries that are checks (they carry a status and a timing); other run metadata is shown separately
  const rows = latest
    ? Object.entries(latest.runMetrics).filter(
        (e): e is [string, SystemMetric] =>
          typeof e[1] === "object" && e[1] !== null && "status" in e[1] && typeof (e[1] as SystemMetric).seconds === "number",
      )
    : [];
  const total = latest?.runMetrics["total_seconds"];
  const dq = latest?.runMetrics["data_quality"] as
    | { checked?: number; quarantined?: Record<string, { issues: string[]; using: string }>; not_delivered?: string[] }
    | undefined;
  const quarantined = Object.entries(dq?.quarantined ?? {});
  const notDelivered = dq?.not_delivered ?? [];

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
            rel="noopener noreferrer"
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
                    <Badge tone={m.status === "ok" ? "emerald" : m.status === "partial" ? "amber" : "red"}>{m.status}</Badge>
                    {m.error && <span className="ml-2 text-xs text-red-700">{m.error}</span>}
                    {m.note && <span className="ml-2 text-xs text-zinc-600">{m.note}</span>}
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
          {quarantined.length === 0 && notDelivered.length === 0 ? (
            <span className="text-zinc-600">all {dq.checked ?? 0} input files passed their checks, and every input was delivered.</span>
          ) : (
            <span className="text-red-700">
              {[
                ...quarantined.map(([t, v]) => `${t} quarantined (${v.issues[0]}; using ${v.using})`),
                ...notDelivered.map((n) => `${n} not delivered`),
              ].join(" · ")}
            </span>
          )}
        </Card>
      )}

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">
          What officers decided about each finding type
        </h2>
        {!feedback ? (
          <div className="p-4">
            <Skeleton className="h-24 w-full" />
          </div>
        ) : feedback.length === 0 ? (
          <p className="px-4 py-6 text-sm text-zinc-500">No suggested fixes yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Finding type</th>
                  <th className="px-4 py-2 text-right font-medium">Waiting</th>
                  <th className="px-4 py-2 text-right font-medium">Approved</th>
                  <th className="px-4 py-2 text-right font-medium">Done</th>
                  <th className="px-4 py-2 text-right font-medium">Rejected</th>
                  <th className="px-4 py-2 text-right font-medium">Rejected share of decided</th>
                  <th className="px-4 py-2 text-right font-medium">Cleared</th>
                  <th className="px-4 py-2 text-right font-medium">Escalated</th>
                  <th className="px-4 py-2 text-right font-medium">Cleared share of checks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 tabular-nums">
                {feedback.map((f) => {
                  const decided = f.approved + f.done + f.rejected;
                  const rate = decided ? f.rejected / decided : null;
                  const checked = f.cleared + f.escalated;
                  const clearRate = checked ? f.cleared / checked : null;
                  return (
                    <tr key={f.mechanism}>
                      <td className="px-4 py-2 text-zinc-900">{MECHANISM[f.mechanism] ?? f.mechanism}</td>
                      <td className="px-4 py-2 text-right">{f.proposed}</td>
                      <td className="px-4 py-2 text-right">{f.approved}</td>
                      <td className="px-4 py-2 text-right">{f.done}</td>
                      <td className="px-4 py-2 text-right">{f.rejected}</td>
                      <td className="px-4 py-2 text-right">
                        {rate === null ? "—" : <Badge tone={rate >= 0.3 && decided >= 5 ? "amber" : "zinc"}>{Math.round(rate * 100)}%</Badge>}
                      </td>
                      <td className="px-4 py-2 text-right">{f.cleared}</td>
                      <td className="px-4 py-2 text-right">{f.escalated}</td>
                      <td className="px-4 py-2 text-right">
                        {clearRate === null ? (
                          "—"
                        ) : (
                          <Badge tone={clearRate >= 0.8 && checked >= 5 ? "amber" : "zinc"}>{Math.round(clearRate * 100)}%</Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-500">
          This is the learning loop, kept human. A finding type whose fixes officers keep rejecting (amber: 30% or more
          of at least 5 decisions) goes to the person who owns the rules. So does a &ldquo;worth a look&rdquo; type that
          officers clear almost every time (amber: 80% or more of at least 5 checks): the rules owner reads the reasons
          and decides whether it is noise or a cheap check worth keeping. The rules never change themselves: that would
          be an unvalidated model change.
        </p>
      </Card>

      <SecondChecks />

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

const USER_KEY = "bt-user";

/** Clears picked for a second person. The officer's case screens never show which clears were picked. */
function SecondChecks() {
  const [list, setList] = useState<SecondCheck[] | null>(null);
  const [user, setUser] = useState("");
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    fetchSecondChecks()
      .then(setList)
      .catch(() => setList([]));
  }, []);

  useEffect(() => {
    load();
    try {
      // restoring a browser-only preference after hydration; there is no server value to render instead
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUser(window.localStorage.getItem(USER_KEY) ?? "");
    } catch {
      /* storage unavailable */
    }
  }, [load]);

  async function act(sc: SecondCheck, d: "AGREE" | "DISAGREE") {
    const key = sc.borrowerId + sc.code;
    setBusy(key + d);
    setErr(null);
    try {
      await reviewSecondCheck(sc, d, user, notes[key] ?? "");
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-medium text-zinc-900">Second checks on cleared findings</h2>
        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-600">
          Reviewing as
          <input
            value={user}
            onChange={(e) => setUser(e.target.value)}
            className="h-7 w-36 rounded-md border border-zinc-300 px-2 text-sm text-zinc-900 focus-visible:outline-2 focus-visible:outline-blue-600"
          />
        </label>
      </div>
      <p className="border-b border-zinc-100 bg-zinc-50 px-4 py-2 text-xs text-zinc-600">
        A second person checks every cleared &ldquo;worth a look&rdquo; finding whose clues name $
        {LARGE_AMOUNT.toLocaleString("en-US")} or more, and a random 1 in 10 of the rest. The pick is made after the clear, and
        the officer&apos;s case screens don&apos;t show it. The officer who cleared it can&apos;t be its second check, and a
        disagreement escalates the finding to its full fix. In a bank only reviewers would see this list; that needs the
        bank&apos;s sign-in, which isn&apos;t built.
      </p>
      {err && (
        <p role="alert" className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-800">
          {err}
        </p>
      )}
      {!list ? (
        <div className="p-4">
          <Skeleton className="h-16 w-full" />
        </div>
      ) : list.length === 0 ? (
        <p className="px-4 py-6 text-sm text-zinc-500">No cleared findings have been picked yet.</p>
      ) : (
        <ul className="divide-y divide-zinc-100 text-sm">
          {list.map((sc) => {
            const key = sc.borrowerId + sc.code;
            return (
              <li key={key} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/case/${sc.borrowerId}`}
                    className="rounded font-mono text-xs font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600"
                  >
                    {sc.borrowerId}
                  </Link>
                  <span className="font-medium text-zinc-900">{sc.title}</span>
                  <Badge>{MECHANISM[sc.mechanism] ?? sc.mechanism}</Badge>
                  <Badge tone={sc.reason === "LARGE_AMOUNT" ? "amber" : "zinc"}>
                    {sc.reason === "LARGE_AMOUNT" ? `large amount: $${(sc.amount ?? 0).toLocaleString("en-US")}` : "random 1 in 10"}
                  </Badge>
                  <Badge tone={sc.status === "WAITING" ? "amber" : sc.status === "AGREED" ? "emerald" : "red"}>
                    {sc.status === "WAITING" ? "Waiting" : sc.status === "AGREED" ? "Agreed" : "Disagreed: escalated"}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-zinc-500">
                  cleared by {sc.clearedBy} · {fmtDate(sc.pickedAt)}
                  {sc.clearNote ? ` · “${sc.clearNote}”` : ""}
                  {sc.reviewer ? ` · ${sc.status.toLowerCase()} by ${sc.reviewer}${sc.note ? `: “${sc.note}”` : ""}` : ""}
                </p>
                {sc.status === "WAITING" && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <input
                      aria-label={`Note for the second check of ${sc.borrowerId}`}
                      placeholder="Note (needed to disagree)"
                      value={notes[key] ?? ""}
                      onChange={(e) => setNotes({ ...notes, [key]: e.target.value })}
                      className="h-8 w-full max-w-md rounded-md border border-zinc-300 px-2 text-sm focus-visible:outline-2 focus-visible:outline-blue-600"
                    />
                    <Button variant="primary" disabled={busy !== null} onClick={() => void act(sc, "AGREE")}>
                      Agree
                    </Button>
                    <Button
                      variant="danger"
                      disabled={busy !== null || !(notes[key] ?? "").trim()}
                      onClick={() => void act(sc, "DISAGREE")}
                    >
                      Disagree
                    </Button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
