import { HIDDEN, type AuditEvent, type CaseDetail, type CaseSummary, type Decision, type RunStatus, type Step, type StepStatus } from "./types";

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
  Record<
    string,
    {
      status: StepStatus;
      decidedBy?: string;
      decidedAt?: string;
      note?: string | null;
      approvedBy?: string;
      mechanism?: string;
      from?: StepStatus;
    }
  >
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

const CLOSED: StepStatus[] = ["DONE", "REJECTED", "CLEARED", "ESCALATED"];
const STARTED: StepStatus[] = ["APPROVED", "DONE", "CLEARED", "ESCALATED"];
const isOpen = (s?: StepStatus) => s === "PROPOSED" || s === "APPROVED";

function caseStatus(all: Step[]): string {
  const steps = all.filter((s) => !HIDDEN.includes(s.status));
  if (steps.length === 0) return "NO_ACTION";
  if (steps.every((s) => CLOSED.includes(s.status))) return "RESOLVED";
  if (steps.some((s) => STARTED.includes(s.status))) return "IN_PROGRESS";
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
    const mine = Object.values(overlay[c.borrowerId] ?? {});
    if (mine.length === 0) return c;
    const openSteps = Math.max(0, c.openSteps + mine.reduce((n, s) => n + Number(isOpen(s.status)) - Number(isOpen(s.from)), 0));
    // same rule as caseStatus(): no open step left means every visible step is closed
    const caseStatus =
      openSteps === 0
        ? "RESOLVED"
        : c.caseStatus === "IN_PROGRESS" || mine.some((s) => STARTED.includes(s.status))
          ? "IN_PROGRESS"
          : "AWAITING_APPROVAL";
    return { ...c, openSteps, caseStatus };
  });
}

export async function fetchCase(id: string): Promise<CaseDetail> {
  const d = await getJSON<CaseDetail>(
    `/api/cases/${encodeURIComponent(id)}`,
    `/snapshot/case/${encodeURIComponent(id)}.json`,
  );
  return applyOverlay(d);
}

// the same rules the case service enforces. `check`: only for (true) or never for (false) a "worth a look" check
const NEXT: Record<Decision, { from: StepStatus[]; to: StepStatus; check?: boolean; reason?: boolean }> = {
  APPROVE: { from: ["PROPOSED"], to: "APPROVED" },
  REJECT: { from: ["PROPOSED"], to: "REJECTED", check: false },
  DONE: { from: ["APPROVED"], to: "DONE", check: false },
  CLEAR: { from: ["PROPOSED", "APPROVED"], to: "CLEARED", check: true, reason: true },
  ESCALATE: { from: ["PROPOSED", "APPROVED"], to: "ESCALATED", check: true, reason: true },
};

export function allowed(step: Step, decision: Decision): boolean {
  const r = NEXT[decision];
  return r.from.includes(step.status) && (r.check === undefined || r.check === step.check);
}

export const needsReason = (decision: Decision) => Boolean(NEXT[decision].reason);

const same = (a?: string | null, b?: string | null) => Boolean(a && b && a.trim().toLowerCase() === b.trim().toLowerCase());

/** Four eyes: whoever approved a letter (anything that leaves the bank) can't also mark it done. */
export function approverOf(step: Step): string | null {
  return step.approvedBy ?? (step.status === "APPROVED" ? step.decidedBy : null);
}
export const needsSecondPerson = (step: Step, user: string) => step.kind === "LETTER" && same(approverOf(step), user);

/** `all`: every step of the case, so a demo-mode escalation can bring the waiting fix steps forward. */
export async function decide(
  id: string,
  step: Step,
  decision: Decision,
  user: string,
  note: string,
  all: Step[] = [],
): Promise<void> {
  const r = NEXT[decision];
  const who = user.trim();
  if (!who || who.toLowerCase() === "unknown") {
    throw new Error("Type your name in 'Approving as' first: a decision needs the officer's own name");
  }
  if (r.check !== undefined && r.check !== step.check) {
    throw new Error(
      step.check
        ? `${step.code} is a check: it ends in CLEAR or ESCALATE, not ${decision}`
        : `${decision} applies to a 'worth a look' check, not to fix step ${step.code}`,
    );
  }
  if (!r.from.includes(step.status)) {
    throw new Error(`${step.code} is ${step.status}; ${r.to} needs ${r.from.join(" or ")}`);
  }
  if (r.reason && !note.trim()) throw new Error(`${decision} needs a reason in the note`);
  if (decision === "DONE" && needsSecondPerson(step, who)) {
    throw new Error(`Four eyes: ${approverOf(step)} approved this letter, so someone else must mark it done`);
  }
  if (!isDemo) {
    const res = await fetch(`${API}/api/cases/${encodeURIComponent(id)}/steps/${step.code}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, user: who, note: note || null }),
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
      status: r.to,
      decidedBy: who,
      decidedAt: now,
      note: note || null,
      approvedBy: decision === "APPROVE" ? who : (approverOf(step) ?? undefined),
      mechanism: step.mechanism,
      from: prev?.from ?? step.status, // the status in the snapshot, for the feedback counts
    },
  };
  const audit = read<AuditEvent[]>(AUDIT_KEY, []);
  audit.unshift({ id: Date.now(), at: now, actor: who, borrowerId: id, action: `STEP_${r.to}`, detail: step.code + (note ? ` — ${note}` : "") });
  if (decision === "ESCALATE") proposeFix(overlay, audit, id, step.mechanism, all, who, now);
  write(OVERLAY_KEY, overlay);
  write(AUDIT_KEY, audit.slice(0, 500));
  if (decision === "CLEAR") pickForSecondCheck(id, step, who, note, now); // after the clear, never before
}

/** Demo mode: an escalated finding's waiting fix steps become PROPOSED. */
function proposeFix(overlay: Overlay, audit: AuditEvent[], id: string, mechanism: string, all: Step[], who: string, now: string) {
  const waiting = all.filter((s) => s.mechanism === mechanism && s.status === "STANDBY");
  overlay[id] ??= {};
  for (const s of waiting) overlay[id][s.code] = { status: "PROPOSED", mechanism: s.mechanism, from: "STANDBY" };
  audit.unshift({ id: Date.now() + 1, at: now, actor: who, borrowerId: id, action: "FIX_PROPOSED", detail: `${mechanism}: ${waiting.length} fix step(s) proposed after escalation` });
}

// ---------- second checks on clears ----------
/** Same as the case service's bt.second-check.large-amount and bt.second-check.rate: demo defaults, a bank sets its own. */
export const LARGE_AMOUNT = 500_000;
export const SECOND_CHECK_RATE = 0.1;
const SECOND_KEY = "bt-demo-second-checks";

export type SecondCheck = {
  borrowerId: string;
  mechanism: string;
  code: string;
  title: string;
  reason: "LARGE_AMOUNT" | "RANDOM";
  amount: number | null;
  clearedBy: string;
  clearNote: string | null;
  pickedAt: string;
  status: "WAITING" | "AGREED" | "DISAGREED";
  reviewer: string | null;
  reviewedAt: string | null;
  note: string | null;
};

/** The largest dollar amount a text names ("$774,996 (1.7% of inflows) came from …"), or 0. */
export function largestAmount(text: string): number {
  return Math.max(0, ...[...text.matchAll(/\$([0-9][0-9,]*)/g)].map((m) => Number(m[1].replace(/,/g, ""))));
}

/** Demo mode: the same draw as the service, made after the clear. The letter lists the clues it asked about. */
function pickForSecondCheck(id: string, step: Step, who: string, note: string, now: string) {
  const amount = largestAmount(step.draft ?? "");
  const draw = crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32;
  const reason = amount >= LARGE_AMOUNT ? "LARGE_AMOUNT" : draw < SECOND_CHECK_RATE ? "RANDOM" : null;
  if (!reason) return;
  const list = read<SecondCheck[]>(SECOND_KEY, []);
  list.unshift({ borrowerId: id, mechanism: step.mechanism, code: step.code, title: step.title, reason, amount: amount || null,
    clearedBy: who, clearNote: note || null, pickedAt: now, status: "WAITING", reviewer: null, reviewedAt: null, note: null });
  write(SECOND_KEY, list);
}

/** Clears picked for a second person, newest first. In a bank only reviewers would see this list. */
export async function fetchSecondChecks(): Promise<SecondCheck[]> {
  const rows = await getJSON<SecondCheck[]>("/api/second-checks", "/snapshot/second-checks.json").catch(() => []);
  return isDemo ? [...read<SecondCheck[]>(SECOND_KEY, []), ...rows] : rows;
}

export async function reviewSecondCheck(sc: SecondCheck, decision: "AGREE" | "DISAGREE", user: string, note: string) {
  const who = user.trim();
  if (!who || who.toLowerCase() === "unknown") throw new Error("Type your name first: a second check needs the reviewer's own name");
  if (same(sc.clearedBy, who)) throw new Error(`${sc.clearedBy} cleared this, so someone else must be its second check`);
  if (sc.status !== "WAITING") throw new Error(`This second check is already ${sc.status.toLowerCase()}`);
  if (decision === "DISAGREE" && !note.trim()) throw new Error("DISAGREE needs a reason in the note");
  if (!isDemo) {
    const res = await fetch(`${API}/api/second-checks/${encodeURIComponent(sc.borrowerId)}/${sc.code}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision, user: who, note: note || null }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      throw new Error(body.error ?? `${res.status} ${res.statusText}`);
    }
    return;
  }
  const now = new Date().toISOString();
  const status = decision === "AGREE" ? "AGREED" : "DISAGREED";
  write(SECOND_KEY, read<SecondCheck[]>(SECOND_KEY, []).map((x) =>
    x.borrowerId === sc.borrowerId && x.code === sc.code ? { ...x, status, reviewer: who, reviewedAt: now, note: note || null } : x));
  const audit = read<AuditEvent[]>(AUDIT_KEY, []);
  audit.unshift({ id: Date.now(), at: now, actor: who, borrowerId: sc.borrowerId, action: `SECOND_CHECK_${status}`, detail: sc.code + (note ? ` — ${note}` : "") });
  if (status === "DISAGREED") {
    const d = await fetchCase(sc.borrowerId);
    const overlay = read<Overlay>(OVERLAY_KEY, {});
    const prev = overlay[sc.borrowerId]?.[sc.code];
    overlay[sc.borrowerId] = {
      ...(overlay[sc.borrowerId] ?? {}),
      [sc.code]: { ...prev, status: "ESCALATED", decidedBy: who, decidedAt: now, note: `second check disagreed: ${note}`, mechanism: sc.mechanism, from: prev?.from ?? "PROPOSED" },
    };
    proposeFix(overlay, audit, sc.borrowerId, sc.mechanism, d.steps, who, now);
    write(OVERLAY_KEY, overlay);
  }
  write(AUDIT_KEY, audit.slice(0, 500));
}

export type FeedbackRow = {
  mechanism: string;
  proposed: number;
  approved: number;
  rejected: number;
  done: number;
  cleared: number;
  escalated: number;
};

/** Officers' decisions per finding type. Demo mode adds this browser's own decisions to the snapshot counts. */
export async function fetchFeedback(): Promise<FeedbackRow[]> {
  const rows = await getJSON<FeedbackRow[]>("/api/feedback", "/snapshot/feedback.json");
  if (!isDemo) return rows;
  const byM = new Map(rows.map((r) => [r.mechanism, { ...r }]));
  type Column = Exclude<keyof FeedbackRow, "mechanism">;
  const key: Record<StepStatus, Column | null> = {
    PROPOSED: "proposed",
    APPROVED: "approved",
    REJECTED: "rejected",
    DONE: "done",
    CLEARED: "cleared",
    ESCALATED: "escalated",
    STANDBY: null, // waiting and withdrawn steps are not counted
    WITHDRAWN: null,
  };
  for (const steps of Object.values(read<Overlay>(OVERLAY_KEY, {}))) {
    for (const s of Object.values(steps)) {
      if (!s.mechanism || !s.from) continue;
      if (!byM.has(s.mechanism)) {
        byM.set(s.mechanism, { mechanism: s.mechanism, proposed: 0, approved: 0, rejected: 0, done: 0, cleared: 0, escalated: 0 });
      }
      const r = byM.get(s.mechanism)!;
      const was = key[s.from];
      const now = key[s.status];
      if (was) r[was] = Math.max(0, r[was] - 1);
      if (now) r[now] += 1;
    }
  }
  return [...byM.values()];
}

export function resetDemo() {
  write(OVERLAY_KEY, {});
  write(AUDIT_KEY, []);
  write(SECOND_KEY, []);
}
