import type { AuditEvent, CaseDetail, CaseSummary, Decision, RunStatus, Step, StepStatus } from "./types";

/**
 * Live mode: NEXT_PUBLIC_API_URL points at the Java case service.
 * Demo mode (no URL): read the static snapshot in /public/snapshot; decisions are
 * kept in this browser only, following the same rules the server enforces.
 */
const API = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
export const isDemo = !API;

async function getJSON<T>(apiPath: string, snapshotPath: string): Promise<T> {
  const res = await fetch(API ? `${API}${apiPath}` : snapshotPath, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ---------- demo overlay (browser only) ----------
type Overlay = Record<
  string,
  Record<string, { status: StepStatus; decidedBy: string; decidedAt: string; note: string | null; mechanism?: string; from?: StepStatus }>
>;
const OVERLAY_KEY = "bt-demo-decisions";
const AUDIT_KEY = "bt-demo-audit";

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: decisions last for this page view only */
  }
}

function caseStatus(steps: Step[]): string {
  if (steps.length === 0) return "NO_ACTION";
  if (steps.every((s) => s.status === "DONE" || s.status === "REJECTED")) return "RESOLVED";
  if (steps.some((s) => s.status === "APPROVED" || s.status === "DONE")) return "IN_PROGRESS";
  return "AWAITING_APPROVAL";
}

function applyOverlay(d: CaseDetail): CaseDetail {
  if (!isDemo) return d;
  const mine = read<Overlay>(OVERLAY_KEY, {})[d.caseData.borrowerId] ?? {};
  const steps = d.steps.map((s) => (mine[s.code] ? { ...s, ...mine[s.code] } : s));
  const audit = [
    ...read<AuditEvent[]>(AUDIT_KEY, []).filter((a) => a.borrowerId === d.caseData.borrowerId),
    ...d.audit,
  ];
  return { ...d, steps, audit, caseStatus: caseStatus(steps) };
}

// ---------- public API ----------
export const fetchLatest = () => getJSON<RunStatus>("/api/runs/latest", "/snapshot/latest.json");

export async function fetchCases(): Promise<CaseSummary[]> {
  const cases = await getJSON<CaseSummary[]>("/api/cases", "/snapshot/cases.json");
  if (!isDemo) return cases;
  const overlay = read<Overlay>(OVERLAY_KEY, {});
  return cases.map((c) => {
    const closed = Object.values(overlay[c.borrowerId] ?? {}).filter(
      (s) => s.status === "DONE" || s.status === "REJECTED",
    ).length;
    return { ...c, openSteps: Math.max(0, c.openSteps - closed) };
  });
}

export async function fetchCase(id: string): Promise<CaseDetail> {
  const d = await getJSON<CaseDetail>(
    `/api/cases/${encodeURIComponent(id)}`,
    `/snapshot/case/${encodeURIComponent(id)}.json`,
  );
  return applyOverlay(d);
}

const NEXT: Record<Decision, { from: StepStatus; to: StepStatus }> = {
  APPROVE: { from: "PROPOSED", to: "APPROVED" },
  REJECT: { from: "PROPOSED", to: "REJECTED" },
  DONE: { from: "APPROVED", to: "DONE" },
};

export function allowed(step: Step, decision: Decision): boolean {
  return step.status === NEXT[decision].from;
}

export async function decide(id: string, step: Step, decision: Decision, user: string, note: string): Promise<void> {
  if (!allowed(step, decision)) {
    throw new Error(`${step.code} is ${step.status}; ${NEXT[decision].to} needs ${NEXT[decision].from}`);
  }
  if (!isDemo) {
    const res = await fetch(`${API}/api/cases/${encodeURIComponent(id)}/steps/${step.code}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, user, note: note || null }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      throw new Error(body.error ?? `${res.status} ${res.statusText}`);
    }
    return;
  }
  const now = new Date().toISOString();
  const overlay = read<Overlay>(OVERLAY_KEY, {});
  const prev = overlay[id]?.[step.code];
  overlay[id] = {
    ...(overlay[id] ?? {}),
    [step.code]: {
      status: NEXT[decision].to,
      decidedBy: user,
      decidedAt: now,
      note: note || null,
      mechanism: step.mechanism,
      from: prev?.from ?? step.status, // the status in the snapshot, for the feedback counts
    },
  };
  write(OVERLAY_KEY, overlay);
  const audit = read<AuditEvent[]>(AUDIT_KEY, []);
  audit.unshift({ id: Date.now(), at: now, actor: user, borrowerId: id, action: `STEP_${NEXT[decision].to}`, detail: step.code + (note ? ` — ${note}` : "") });
  write(AUDIT_KEY, audit.slice(0, 500));
}

export type FeedbackRow = { mechanism: string; proposed: number; approved: number; rejected: number; done: number };

/** Officers' decisions per finding type. Demo mode adds this browser's own decisions to the snapshot counts. */
export async function fetchFeedback(): Promise<FeedbackRow[]> {
  const rows = await getJSON<FeedbackRow[]>("/api/feedback", "/snapshot/feedback.json");
  if (!isDemo) return rows;
  const byM = new Map(rows.map((r) => [r.mechanism, { ...r }]));
  const key: Record<StepStatus, "proposed" | "approved" | "rejected" | "done"> = {
    PROPOSED: "proposed",
    APPROVED: "approved",
    REJECTED: "rejected",
    DONE: "done",
  };
  for (const steps of Object.values(read<Overlay>(OVERLAY_KEY, {}))) {
    for (const s of Object.values(steps)) {
      const r = s.mechanism && s.from ? byM.get(s.mechanism) : undefined;
      if (!r || !s.from) continue;
      r[key[s.from]] = Math.max(0, r[key[s.from]] - 1);
      r[key[s.status]] += 1;
    }
  }
  return [...byM.values()];
}

export function resetDemo() {
  write(OVERLAY_KEY, {});
  write(AUDIT_KEY, []);
}
