export type Verdict = "LIKELY_FRAUD" | "NEEDS_MORE_EVIDENCE" | "EXPLAINED" | "NO_ISSUE";
export type Confidence = "high" | "medium" | "low";
// STANDBY: a fix step waiting, unseen, until its "worth a look" check is escalated (or the evidence grows)
export type StepStatus = "PROPOSED" | "APPROVED" | "REJECTED" | "DONE" | "CLEARED" | "ESCALATED" | "STANDBY";
export type Decision = "APPROVE" | "REJECT" | "DONE" | "CLEAR" | "ESCALATE";

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
  decision?: {
    decisionId: string;
    resultDigest: string;
    inputsDigest: string;
    ruleVersion: string;
    codeVersion: string;
    asOf: number;
  } | null;
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
  /** the one step that can clear a "worth a look" finding: it ends in CLEARED or ESCALATED */
  check: boolean;
  /** who approved it; decidedBy is whoever made the latest decision */
  approvedBy?: string | null;
};

export type AuditEvent = {
  id: number;
  at: string;
  actor: string;
  borrowerId: string | null;
  action: string;
  detail: string;
};

export type LiveAlert = {
  type: string;
  txnId: string | null;
  payerName: string | null;
  amount: number;
  detectedAt: string;
};

export type CaseDetail = {
  liveAlerts?: LiveAlert[];
  caseData: CaseData;
  steps: Step[];
  audit: AuditEvent[];
  caseStatus: string;
  unavailableSystems: string[];
};

export type CaseSummary = {
  liveAlerts?: number;
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
