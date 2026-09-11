export type Verdict = "LIKELY_FRAUD" | "NEEDS_MORE_EVIDENCE" | "EXPLAINED" | "NO_ISSUE";
export type Confidence = "high" | "medium" | "low";
export type StepStatus = "PROPOSED" | "APPROVED" | "REJECTED" | "DONE";
export type Decision = "APPROVE" | "REJECT" | "DONE";

export type Signal = {
  signalId: string;
  entityId: string;
  system: string;
  type: string;
  severity: number;
  confidence: number;
  evidence: string[];
  explanation: string;
  observedMonth: number;
  relatedEntities: string[];
};

export type Finding = {
  mechanism: string;
  confidence: Confidence;
  plain: string;
  signals: string[];
  corroboratedBy: string[] | null;
  sources: string[];
  systems: string[];
  firstMonth: number;
};

export type CaseData = {
  borrowerId: string;
  verdict: Verdict;
  headline: string;
  priority: number;
  findings: Finding[];
  signals: Signal[];
  explanations: string[];
  coverage: Record<string, string>;
};

export type Step = {
  mechanism: string;
  code: string;
  title: string;
  kind: "LETTER" | "ACTION";
  status: StepStatus;
  draft: string;
  draftSource: string;
  owner: string;
  dueDate: string | null;
  decidedBy: string | null;
  decidedAt: string | null;
  note: string | null;
};

export type AuditEvent = {
  id: number;
  at: string;
  actor: string;
  borrowerId: string | null;
  action: string;
  detail: string;
};

export type CaseDetail = {
  caseData: CaseData;
  steps: Step[];
  audit: AuditEvent[];
  caseStatus: string;
  unavailableSystems: string[];
};

export type CaseSummary = {
  borrowerId: string;
  verdict: Verdict;
  headline: string;
  priority: number;
  mechanisms: string[];
  openSteps: number;
  caseStatus: string;
};

export type SystemMetric = { status: string; seconds: number; signals?: number; cases?: number; error?: string };

export type RunStatus = {
  asOf: number | null;
  receivedAt: string | null;
  runMetrics: Record<string, SystemMetric | number>;
  verdicts: Record<string, number>;
};
