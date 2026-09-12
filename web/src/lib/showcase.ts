"use client";

import { useCallback, useEffect, useState } from "react";
import type { Verdict } from "./types";

/** Static files exported by bt.showcase.export and bt.agent.investigate (synthetic data, samples only). */

export type Column = { name: string; meaning: string };
export type TableInfo = { table: string; title: string; what: string; rows: number; columns: Column[]; sample: Record<string, unknown>[] };
export type Tables = { book: string; borrowers: number; frauds?: number; total_rows: number; tables: TableInfo[] };

type RawFinding = { mechanism: string; confidence: string; plain: string; signals: string[]; first_month: number };
type RawSignal = { signal_id: string; system: string; type: string; explanation: string; observed_month: number };
export type DecisionRecord = {
  decision_id: string;
  result_digest: string;
  inputs_digest: string;
  rule_version: string;
  code_version: string;
  as_of: number;
};
export type Story = {
  borrower_id: string;
  name: string;
  planted: string[];
  pattern: string;
  fraud_start_month: number;
  registry: { entity_id: string; name: string; kind: string; officer_person_id: string; has_operations: boolean; formed_month: number; address: string }[];
  payments: { month: number; payer_name: string; amount: number; memo: string }[];
  liens: { debtor_name: string; secured_party_name: string; collateral_desc: string; filed_month: number }[];
  financials: { quarter: number; revenue_reported: number; covenant_metric_reported: number; covenant_threshold: number }[];
  verdict: Verdict;
  headline: string;
  findings: RawFinding[];
  signals: RawSignal[];
  decision: DecisionRecord | null;
};
export type Doc = {
  invoice_id: string;
  borrower_id: string;
  image: string;
  read_total: string | null;
  first_read: string | null;
  second_look: boolean;
  record_amount: number;
  flagged: boolean;
  truly_tampered: boolean;
  outcome: string;
};
export type KeyRow = {
  borrower_id: string;
  planted: string[];
  lookalikes: string[];
  verdict: Verdict;
  found: string[];
  right_mechanisms: string[];
  status: string;
  priority: number;
};
export type HeldOut = {
  seed: number;
  borrowers: number;
  fraud: number;
  caught: number;
  sent_to_review: number;
  missed: number;
  false_alarms: number;
  honest_worth_a_look: number;
  per_mechanism: Record<string, [number, number]>;
};
export type AnswerKey = { counts: Record<string, number>; borrowers: KeyRow[]; heldout: HeldOut[] };
export type Replay = {
  replayed: number;
  identical: number;
  different: number;
  inputs_changed: string[];
  rules_changed: boolean;
  inputs: Record<string, string>;
  inputs_digest: string;
  rule_version: string;
  code_version: string;
};
export type AgentRun = {
  borrower_id: string;
  verdict_by_rules: Verdict;
  status: "ok" | "unavailable";
  model: string | null;
  steps: { id: string; tool: string; args: Record<string, string>; result: string }[];
  memo: { text: string; cites: string[] }[];
  dropped: { text: string; reason: string }[];
  errors: string[];
  generated_at: string;
  tokens?: number;
  seconds?: number;
};

/** Fetch one static JSON file. `null` data with no error means the file doesn't exist (e.g. no agent memo for a case). */
export function useStatic<T>(path: string | null, optional = false) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!path) return;
    let live = true;
    fetch(path, { cache: "no-store" })
      .then(async (r) => {
        if (r.ok) return (await r.json()) as T;
        if (optional && r.status === 404) return null;
        throw new Error(`${r.status} ${r.statusText}`);
      })
      .then((d) => {
        if (!live) return;
        setData(d);
        setError(null);
      })
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [path, optional, attempt]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, retry };
}

export function cell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

export const money = (n: number) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
