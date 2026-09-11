"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, ConfidencePill, ErrorState, Skeleton, StatusPill, VerdictBadge } from "@/components/ui";
import { allowed, decide, fetchCase, isDemo } from "@/lib/api";
import { MECHANISM, SOURCE, SYSTEM, fmtDate, signalLabel } from "@/lib/labels";
import type { CaseDetail, Decision, Finding, Signal, Step } from "@/lib/types";

const USER_KEY = "bt-user";

export default function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState("demo.officer");

  const load = useCallback(async () => {
    try {
      setData(await fetchCase(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
    try {
      const saved = window.localStorage.getItem(USER_KEY);
      if (saved) setUser(saved);
    } catch {
      /* ignore */
    }
  }, [load]);

  const byId = useMemo(() => new Map((data?.caseData.signals ?? []).map((s) => [s.signalId, s])), [data]);

  if (error) return <ErrorState message={`Case ${id}: ${error}`} onRetry={() => void load()} />;
  if (!data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const c = data.caseData;
  const actionable = c.findings.filter((f) => f.confidence !== "low");
  const context = c.findings.filter((f) => f.confidence === "low");

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="rounded text-sm text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
          ← Review queue
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="font-mono text-2xl font-semibold tracking-tight text-zinc-900">{c.borrowerId}</h1>
          <VerdictBadge verdict={c.verdict} />
          <span className="text-sm text-zinc-500">priority {Math.round(c.priority * 100)}%</span>
        </div>
        <p className="mt-1 text-zinc-700">{c.headline}</p>
      </div>

      {data.unavailableSystems.length > 0 && (
        <div role="status" className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Reduced coverage: {data.unavailableSystems.map((s) => `${s} ${SYSTEM[s] ?? ""}`).join(", ")} didn&apos;t run
          this time. The findings below are based on the other checks only.
        </div>
      )}

      {(data.liveAlerts?.length ?? 0) > 0 && (
        <Card className="overflow-hidden">
          <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">
            Live payment alerts <span className="text-zinc-500">{data.liveAlerts!.length}</span>
            <span className="ml-2 text-xs font-normal text-zinc-500">from the streaming cash check (S3), newest first</span>
          </h2>
          <ul className="divide-y divide-zinc-100 text-sm">
            {data.liveAlerts!.slice(0, 8).map((a, i) => (
              <li key={`${a.txnId}-${i}`} className="flex flex-wrap gap-x-3 px-4 py-2">
                <Badge tone="red">{signalLabel(a.type)}</Badge>
                <span className="text-zinc-900">{a.payerName ?? "unknown payer"}</span>
                <span className="tabular-nums text-zinc-700">${a.amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                <span className="font-mono text-xs text-zinc-500">{a.txnId}</span>
                <span className="text-zinc-500">{fmtDate(a.detectedAt)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {actionable.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-zinc-500">What we found</h2>
          {actionable.map((f) => (
            <FindingCard key={f.mechanism} f={f} byId={byId} />
          ))}
        </section>
      )}

      {context.length > 0 && (
        <Card className="p-4">
          <h2 className="text-sm font-medium text-zinc-900">Worth a look (not enough on its own)</h2>
          <ul className="mt-2 space-y-1 text-sm text-zinc-600">
            {context.map((f) => (
              <li key={f.mechanism}>
                {MECHANISM[f.mechanism]}: {f.signals.map((sid) => byId.get(sid)?.explanation).filter(Boolean).join("; ")}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {c.explanations.length > 0 && (
        <Card className="p-4">
          <h2 className="text-sm font-medium text-zinc-900">Explained by disclosures</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-600">
            {c.explanations.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Card>
      )}

      <FixSteps id={c.borrowerId} steps={data.steps} user={user} setUser={setUser} onChange={() => void load()} />

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">
          All evidence <span className="text-zinc-500">{c.signals.length}</span>
        </h2>
        {c.signals.length === 0 ? (
          <p className="px-4 py-6 text-sm text-zinc-500">None of the seven checks found anything for this borrower.</p>
        ) : (
          <ul className="divide-y divide-zinc-100">
            {c.signals.map((s) => (
              <li key={s.signalId} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="blue">
                    {s.system} {SYSTEM[s.system]}
                  </Badge>
                  <span className="font-medium text-zinc-900">{signalLabel(s.type)}</span>
                  <span className="text-xs text-zinc-500">month {s.observedMonth + 1}</span>
                </div>
                <p className="mt-1 text-zinc-700">{s.explanation}</p>
                <p className="mt-1 break-all font-mono text-xs text-zinc-500">
                  {s.evidence.join(" · ")} · ref {s.signalId}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="overflow-hidden">
        <h2 className="border-b border-zinc-200 px-4 py-3 text-sm font-medium text-zinc-900">Audit log</h2>
        {data.audit.length === 0 ? (
          <p className="px-4 py-6 text-sm text-zinc-500">No decisions yet.</p>
        ) : (
          <ul className="divide-y divide-zinc-100 text-sm">
            {data.audit.map((a) => (
              <li key={a.id} className="flex flex-wrap gap-x-3 px-4 py-2">
                <span className="text-zinc-500">{fmtDate(a.at)}</span>
                <span className="font-medium text-zinc-900">{a.actor}</span>
                <span className="text-zinc-700">{a.action.replace("STEP_", "").toLowerCase()}</span>
                <span className="text-zinc-600">{a.detail}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function FindingCard({ f, byId }: { f: Finding; byId: Map<string, Signal> }) {
  const own = f.signals.map((id) => byId.get(id)).filter((s): s is Signal => Boolean(s));
  const linked = (f.corroboratedBy ?? []).map((id) => byId.get(id)).filter((s): s is Signal => Boolean(s));
  const MAX_CHAIN = 6;
  const full = [...own, ...linked].sort((a, b) => a.observedMonth - b.observedMonth);
  // keep the strongest clues when the chain is long; the full list is in "All evidence" below
  const chain =
    full.length <= MAX_CHAIN
      ? full
      : [...full]
          .sort((a, b) => b.severity * b.confidence - a.severity * a.confidence)
          .slice(0, MAX_CHAIN)
          .sort((a, b) => a.observedMonth - b.observedMonth);
  const hidden = full.length - chain.length;
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-medium text-zinc-900">{MECHANISM[f.mechanism]}</h3>
        <ConfidencePill level={f.confidence} />
        <span className="text-xs text-zinc-500">
          independent sources: {f.sources.map((s) => SOURCE[s] ?? s).join(", ")}
        </span>
      </div>
      <p className="mt-1 text-sm text-zinc-600">In plain words: {f.plain}.</p>
      <div className="mt-3 flex flex-wrap items-stretch gap-2" aria-label="How the evidence connects">
        {chain.map((s, i) => (
          <div key={s.signalId} className="flex items-center gap-2">
            <div
              className={`max-w-60 rounded-lg border px-3 py-2 text-xs ${
                linked.includes(s) ? "border-dashed border-blue-300 bg-blue-50/50" : "border-zinc-200 bg-zinc-50"
              }`}
              title={s.explanation}
            >
              <div className="font-medium text-zinc-900">
                {s.system} · {signalLabel(s.type)}
              </div>
              <div className="mt-0.5 line-clamp-2 text-zinc-600">{s.explanation}</div>
              {linked.includes(s) && <div className="mt-1 text-blue-700">linked through a shared company</div>}
            </div>
            {i < chain.length - 1 && <span className="text-zinc-400" aria-hidden>→</span>}
          </div>
        ))}
        {hidden > 0 && (
          <span className="self-center text-xs text-zinc-500">+{hidden} more clues (see all evidence)</span>
        )}
        <span className="self-center text-zinc-400" aria-hidden>
          →
        </span>
        <div className="self-center rounded-lg bg-zinc-900 px-3 py-2 text-xs font-medium text-white">
          {MECHANISM[f.mechanism]}
        </div>
      </div>
    </Card>
  );
}

function FixSteps({
  id,
  steps,
  user,
  setUser,
  onChange,
}: {
  id: string;
  steps: Step[];
  user: string;
  setUser: (u: string) => void;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  async function act(step: Step, d: Decision) {
    setBusy(step.code + d);
    setErr(null);
    try {
      await decide(id, step, d, user.trim() || "unknown", notes[step.code] ?? "");
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  if (steps.length === 0) {
    return (
      <Card className="p-4 text-sm text-zinc-600">
        No fix steps: nothing here is strong enough to act on. It stays under monitoring.
      </Card>
    );
  }

  const groups = steps.reduce<Record<string, Step[]>>((acc, s) => {
    (acc[s.mechanism] ??= []).push(s);
    return acc;
  }, {});

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 px-4 py-3">
        <h2 className="text-sm font-medium text-zinc-900">Suggested fix</h2>
        <span className="text-xs text-zinc-500">Nothing is sent or changed until a person approves it.</span>
        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-600">
          Approving as
          <input
            value={user}
            onChange={(e) => {
              setUser(e.target.value);
              try {
                window.localStorage.setItem(USER_KEY, e.target.value);
              } catch {
                /* ignore */
              }
            }}
            className="h-7 w-36 rounded-md border border-zinc-300 px-2 text-sm text-zinc-900 focus-visible:outline-2 focus-visible:outline-blue-600"
          />
        </label>
      </div>
      {isDemo && (
        <p className="border-b border-zinc-100 bg-zinc-50 px-4 py-2 text-xs text-zinc-500">
          Demo mode: decisions are saved in your browser only, using the same rules as the live service.
        </p>
      )}
      {err && (
        <p role="alert" className="border-b border-red-100 bg-red-50 px-4 py-2 text-sm text-red-800">
          {err}
        </p>
      )}
      {Object.entries(groups).map(([mech, list]) => (
        <div key={mech} className="border-b border-zinc-100 last:border-0">
          <h3 className="bg-zinc-50/60 px-4 py-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
            {MECHANISM[mech] ?? mech}
          </h3>
          <ul className="divide-y divide-zinc-100">
            {list.map((s) => (
              <li key={s.code} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-zinc-900">{s.title}</span>
                  <Badge>{s.kind === "LETTER" ? "letter" : "internal action"}</Badge>
                  <StatusPill status={s.status} />
                  <span className="text-xs text-zinc-500">due {s.dueDate ?? "—"}</span>
                  {s.draftSource !== "TEMPLATE" && <Badge tone="blue">{s.draftSource.toLowerCase().replace("_", " ")}</Badge>}
                  <div className="ml-auto flex gap-2">
                    <Button variant="primary" disabled={!allowed(s, "APPROVE") || busy !== null} onClick={() => void act(s, "APPROVE")}>
                      {busy === s.code + "APPROVE" ? "Approving…" : "Approve"}
                    </Button>
                    <Button variant="danger" disabled={!allowed(s, "REJECT") || busy !== null} onClick={() => void act(s, "REJECT")}>
                      Reject
                    </Button>
                    <Button disabled={!allowed(s, "DONE") || busy !== null} onClick={() => void act(s, "DONE")}>
                      Mark done
                    </Button>
                  </div>
                </div>
                {s.decidedBy && (
                  <p className="mt-1 text-xs text-zinc-500">
                    {s.status.toLowerCase()} by {s.decidedBy} · {fmtDate(s.decidedAt)}
                    {s.note ? ` · “${s.note}”` : ""}
                  </p>
                )}
                {s.status === "PROPOSED" && (
                  <input
                    placeholder="Note for the audit log (optional)"
                    value={notes[s.code] ?? ""}
                    onChange={(e) => setNotes({ ...notes, [s.code]: e.target.value })}
                    className="mt-2 h-8 w-full max-w-md rounded-md border border-zinc-300 px-2 text-sm focus-visible:outline-2 focus-visible:outline-blue-600"
                  />
                )}
                <details className="mt-2">
                  <summary className="cursor-pointer rounded text-sm text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
                    {s.kind === "LETTER" ? "Read the drafted letter" : "Read the action memo"}
                  </summary>
                  <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-zinc-200 bg-zinc-50 p-3 font-mono text-xs leading-relaxed text-zinc-800">
                    {s.draft}
                  </pre>
                </details>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </Card>
  );
}
