import type { Verdict } from "./types";

export const MECHANISM: Record<string, string> = {
  DOUBLE_PLEDGE: "Collateral pledged twice",
  TAPE_DRESSUP: "Bad loans reported as good",
  DISGUISED_RECEIPTS: "Disguised receipts",
  FAKE_INVOICES: "Fake or altered invoices",
  HIDDEN_DEBT: "Hidden debt",
  RELATED_SHELLS: "Linked shell companies",
  FIN_MANIPULATION: "Financials don't fit",
};

export const SYSTEM: Record<string, string> = {
  S1: "Collateral integrity",
  S2: "Tape vs source",
  S3: "Cash provenance",
  S4: "Invoice authenticity",
  S5: "Hidden-debt finder",
  S6: "Relationship mapper",
  S7: "Financial consistency",
  combiner: "Combiner",
};

export const SOURCE: Record<string, string> = {
  wf_facilities: "WF facilities",
  pledgecheck: "PledgeCheck",
  payments: "bank payments",
  tape_flags: "tape flags",
  tape_history: "tape history",
  servicer_system: "servicer system",
  invoices: "invoices",
  documents: "invoice documents (model)",
  ucc: "lien filings",
  courts: "court records",
  registry: "company registry",
  financials_vs_cash: "financials vs cash",
  financial_statements: "financial statements",
  operating_account: "operating account",
  covenant_certificate: "covenant certificate",
  public_abs: "public securitization (SEC ABS-EE)",
  sec_filings: "SEC filings",
};

export const VERDICT: Record<Verdict, { label: string; tone: Tone }> = {
  LIKELY_FRAUD: { label: "Likely fraud", tone: "red" },
  NEEDS_MORE_EVIDENCE: { label: "Worth a look", tone: "amber" },
  EXPLAINED: { label: "Explained", tone: "sky" },
  NO_ISSUE: { label: "No issue", tone: "emerald" },
};

export type Tone = "red" | "amber" | "sky" | "emerald" | "zinc" | "blue";

export function signalLabel(type: string): string {
  return type
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
