"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Card, ErrorState, Skeleton, VerdictBadge } from "@/components/ui";
import { MECHANISM, SYSTEM, signalLabel } from "@/lib/labels";
import { cell, money, useStatic, type Doc, type Story, type Tables } from "@/lib/showcase";

const SECTIONS = [
  ["tables", "What it reads"],
  ["story", "One fraud, step by step"],
  ["documents", "Invoice documents"],
] as const;

export default function DataPage() {
  const tables = useStatic<Tables>("/showcase/tables.json");
  const story = useStatic<Story>("/showcase/story.json");
  const docs = useStatic<Doc[]>("/showcase/documents.json");

  return (
    <div className="space-y-10">
      <div className="max-w-4xl">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">The data</h1>
        <p className="mt-2 text-zinc-700">
          Everything here is synthetic: a made-up book of {tables.data?.borrowers ?? 120} finance-company borrowers over
          24 months. Fraud is planted in {tables.data?.frauds ?? "about a third"} of them, using the tricks described in
          the public court filings on First Brands and Tricolor plus two harder ones (a shell registered to a front
          person, and money sent round through a middleman), next to honest borrowers that look suspicious for innocent
          reasons. You see the shape of every input and 10 sample rows from each. The full dataset, the code and the
          model weights are not published.
        </p>
        <nav aria-label="On this page" className="mt-4 flex flex-wrap gap-2 text-sm">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="rounded-md bg-zinc-100 px-3 py-1.5 text-zinc-800 hover:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-blue-600">
              {label}
            </a>
          ))}
          <Link href="/test" className="rounded-md bg-blue-700 px-3 py-1.5 font-medium text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600">
            Test it yourself: the answer key →
          </Link>
        </nav>
      </div>

      <section id="tables" className="scroll-mt-6 space-y-3">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">What it reads</h2>
        {tables.error ? (
          <ErrorState message={tables.error} onRetry={() => void tables.retry()} />
        ) : !tables.data ? (
          <Skeleton className="h-72 w-full" />
        ) : (
          <TableExplorer t={tables.data} />
        )}
      </section>

      <section id="story" className="scroll-mt-6 space-y-3">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">One fraud, step by step</h2>
        {story.error ? (
          <ErrorState message={story.error} onRetry={() => void story.retry()} />
        ) : !story.data ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <StoryView s={story.data} />
        )}
      </section>

      <section id="documents" className="scroll-mt-6 space-y-3">
        <h2 className="text-lg font-semibold tracking-tight text-zinc-900">Invoice documents</h2>
        <p className="max-w-4xl text-sm text-zinc-600">
          Invoice-based borrowers pledge invoices. An optional document module, off by default, reads the total printed
          on each invoice image with a fine-tuned open model (Donut), and S4 compares it with the amount the borrower
          recorded. It helps only a little: on a held-out book it flagged all 24 tampered invoices but also 15 of 516
          clean ones, and on this demo it found no fraud the rules missed. The rules work without it, so a bank pays for
          validating a model only if it turns it on. The model only reads; the rules decide. Six samples, including one
          it got wrong.
        </p>
        {docs.error ? (
          <ErrorState message={docs.error} onRetry={() => void docs.retry()} />
        ) : !docs.data ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {docs.data.map((d) => (
              <DocCard key={d.invoice_id} d={d} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function TableExplorer({ t }: { t: Tables }) {
  const [sel, setSel] = useState(t.tables[0]?.table);
  const cur = t.tables.find((x) => x.table === sel) ?? t.tables[0];
  return (
    <>
      <p className="max-w-4xl text-sm text-zinc-600">
        {t.tables.length} inputs, {t.total_rows.toLocaleString()} rows in total for {t.borrowers} borrowers. Pick one to
        see what each column means and 10 sample rows (the fraud walked through below first, then an honest borrower).
      </p>
      <div role="tablist" aria-label="Inputs" className="flex flex-wrap gap-1.5">
        {t.tables.map((x) => (
          <button
            key={x.table}
            role="tab"
            aria-selected={x.table === cur.table}
            onClick={() => setSel(x.table)}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 ${
              x.table === cur.table ? "bg-zinc-900 text-white" : "bg-white text-zinc-700 ring-1 ring-inset ring-zinc-200 hover:bg-zinc-50"
            }`}
          >
            {x.title}
            <span className={`ml-1.5 tabular-nums ${x.table === cur.table ? "text-zinc-300" : "text-zinc-400"}`}>{x.rows.toLocaleString()}</span>
          </button>
        ))}
      </div>
      <Card className="overflow-hidden" key={cur.table}>
        <div className="border-b border-zinc-200 px-4 py-3">
          <div className="flex flex-wrap items-baseline gap-2">
            <h3 className="font-medium text-zinc-900">{cur.title}</h3>
            <span className="text-sm text-zinc-500">{cur.rows.toLocaleString()} rows</span>
          </div>
          <p className="mt-0.5 text-sm text-zinc-600">{cur.what}</p>
        </div>
        <dl className="grid gap-x-6 gap-y-1 border-b border-zinc-100 px-4 py-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {cur.columns.map((c) => (
            <div key={c.name} className="flex gap-2">
              <dt className="shrink-0 font-mono text-xs leading-5 text-zinc-900">{c.name}</dt>
              <dd className="text-zinc-600">{c.meaning}</dd>
            </div>
          ))}
        </dl>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500">
              <tr>
                {cur.columns.map((c) => (
                  <th key={c.name} scope="col" className="whitespace-nowrap px-4 py-2 font-medium">
                    {c.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {cur.sample.map((r, i) => (
                <tr key={i}>
                  {cur.columns.map((c) => (
                    <td key={c.name} className={`whitespace-nowrap px-4 py-1.5 ${typeof r[c.name] === "number" ? "tabular-nums" : ""} text-zinc-800`}>
                      {cell(r[c.name])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function Step({ n, title, children, note }: { n: number; title: string; children: React.ReactNode; note?: string }) {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-start gap-3 border-b border-zinc-200 px-4 py-3">
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-xs font-semibold text-white">{n}</span>
        <div>
          <h3 className="font-medium text-zinc-900">{title}</h3>
          {note && <p className="mt-0.5 text-sm text-zinc-600">{note}</p>}
        </div>
      </div>
      <div className="overflow-x-auto">{children}</div>
    </Card>
  );
}

function StoryView({ s }: { s: Story }) {
  const shells = s.registry.filter((r) => r.kind !== "borrower");
  const shellNames = new Set(shells.map((r) => r.name));
  const byId = new Map(s.signals.map((x) => [x.signal_id, x]));
  const actionable = s.findings.filter((f) => f.confidence !== "low");
  const found = new Set(actionable.map((f) => f.mechanism));
  const th = "whitespace-nowrap px-4 py-2 font-medium";
  const td = "whitespace-nowrap px-4 py-1.5 text-zinc-800";
  return (
    <div className="space-y-4">
      <p className="max-w-4xl text-sm text-zinc-600">
        <span className="font-medium text-zinc-900">{s.name}</span> ({s.borrower_id}) is a synthetic borrower with a{" "}
        {s.pattern === "first_brands_like" ? "First Brands" : "Tricolor"}-style fraud planted from month{" "}
        {s.fraud_start_month + 1}. These are the rows the checks actually read.
      </p>
      <Step
        n={1}
        title="The company registry: new companies, same officer, no business"
        note={`${shells.length} companies share the borrower's officer. None of them does any business, and the borrower never disclosed them (S6 Relationship mapper).`}
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th scope="col" className={th}>company</th>
              <th scope="col" className={th}>kind</th>
              <th scope="col" className={th}>officer</th>
              <th scope="col" className={th}>formed</th>
              <th scope="col" className={th}>does business?</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {s.registry.map((r) => (
              <tr key={r.entity_id} className={r.kind === "borrower" ? "" : "bg-red-50/40"}>
                <td className={td}>{r.name}</td>
                <td className={td}>{r.kind}</td>
                <td className={`${td} font-mono text-xs`}>{r.officer_person_id}</td>
                <td className={`${td} tabular-nums`}>{r.formed_month < 0 ? "before the timeline" : `month ${r.formed_month + 1}`}</td>
                <td className={td}>{r.has_operations ? "yes" : <span className="font-medium text-red-800">no</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>
      <Step
        n={2}
        title="The bank payments: a linked company paying like a customer"
        note={`Month ${(s.payments[0]?.month ?? 0) + 1}. Real customers pay small instalments. A company owned by the same person sends large 'customer remittances' that make the book look healthier (S3 Cash provenance: judged by who paid, not by the amount).`}
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th scope="col" className={th}>payer</th>
              <th scope="col" className={th}>memo</th>
              <th scope="col" className={`${th} text-right`}>amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {s.payments.map((p, i) => (
              <tr key={i} className={shellNames.has(p.payer_name) ? "bg-red-50/40" : ""}>
                <td className={td}>
                  {p.payer_name}
                  {shellNames.has(p.payer_name) && <span className="ml-2"><Badge tone="red">linked company</Badge></span>}
                </td>
                <td className={td}>{p.memo}</td>
                <td className={`${td} text-right tabular-nums`}>{money(p.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>
      <Step
        n={3}
        title="Public lien filings: who else has a claim"
        note="Lien filings carry names and addresses, not IDs, so S5 matches them by name and address against the borrower and every linked company."
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th scope="col" className={th}>against</th>
              <th scope="col" className={th}>held by</th>
              <th scope="col" className={th}>covers</th>
              <th scope="col" className={th}>filed</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {s.liens.map((l, i) => (
              <tr key={i}>
                <td className={td}>{l.debtor_name}</td>
                <td className={td}>{l.secured_party_name}</td>
                <td className="px-4 py-1.5 text-zinc-800">{l.collateral_desc}</td>
                <td className={`${td} tabular-nums`}>{l.filed_month < 0 ? `${-l.filed_month} months before` : `month ${l.filed_month + 1}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>
      <Step
        n={4}
        title="What it reported: covenants that keep just clearing"
        note="S7 compares reported revenue with cash the bank can verify, and watches for a covenant that clears its line by a hair quarter after quarter."
      >
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-50 text-xs text-zinc-500">
            <tr>
              <th scope="col" className={th}>quarter</th>
              <th scope="col" className={`${th} text-right`}>reported revenue</th>
              <th scope="col" className={`${th} text-right`}>covenant metric</th>
              <th scope="col" className={`${th} text-right`}>minimum</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {s.financials.map((f) => (
              <tr key={f.quarter}>
                <td className={td}>Q{f.quarter + 1}</td>
                <td className={`${td} text-right tabular-nums`}>{money(f.revenue_reported)}</td>
                <td className={`${td} text-right tabular-nums`}>{f.covenant_metric_reported.toFixed(2)}</td>
                <td className={`${td} text-right tabular-nums text-zinc-500`}>{f.covenant_threshold.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Step>
      <Step n={5} title="What the system concluded" note="The combiner joins the clues through the linked companies and counts independent sources before it calls anything likely.">
        <div className="space-y-3 px-4 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <VerdictBadge verdict={s.verdict} />
            <span className="text-zinc-800">{s.headline}</span>
          </div>
          <ul className="space-y-2">
            {actionable.map((f) => (
              <li key={f.mechanism}>
                <span className="font-medium text-zinc-900">{MECHANISM[f.mechanism] ?? f.mechanism}</span>{" "}
                <Badge tone={f.confidence === "high" ? "red" : "amber"}>{f.confidence}</Badge>
                <span className="ml-2 text-zinc-600">
                  {[
                    ...new Set(
                      f.signals
                        .map((id) => byId.get(id))
                        .filter(Boolean)
                        .map((x) => `${x!.system} ${SYSTEM[x!.system] ?? ""}: ${signalLabel(x!.type).toLowerCase()}`),
                    ),
                  ].join(" · ")}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-zinc-700">
            Planted (answer key):{" "}
            {s.planted.map((m) => (
              <span key={m} className="mr-1.5 inline-block">
                <Badge tone={found.has(m) ? "emerald" : "zinc"}>
                  {found.has(m) ? "✓" : "✗"} {MECHANISM[m] ?? m}
                </Badge>
              </span>
            ))}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Link href={`/case/${s.borrower_id}`} className="rounded font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
              Open the full case, with the suggested fix and the decision record →
            </Link>
            {s.decision && <span className="font-mono text-xs text-zinc-500">decision {s.decision.decision_id}</span>}
          </div>
        </div>
      </Step>
    </div>
  );
}

function amount(read: string | null): string {
  if (!read) return "—";
  const n = Number(read.replace(/[$,]/g, ""));
  return Number.isFinite(n) ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : read;
}

function DocCard({ d }: { d: Doc }) {
  const tone = d.outcome.startsWith("tampered") ? "red" : d.flagged ? "amber" : "emerald";
  return (
    <Card className="overflow-hidden">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={d.image} alt={`Synthetic invoice ${d.invoice_id}`} className="aspect-[4/3] w-full border-b border-zinc-200 bg-zinc-50 object-cover object-top" loading="lazy" />
      <div className="space-y-1.5 px-4 py-3 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-zinc-700">{d.invoice_id}</span>
          <Badge tone={tone}>{d.outcome}</Badge>
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5">
          <dt className="text-zinc-500">model read</dt>
          <dd className="tabular-nums text-zinc-900">{amount(d.read_total)}</dd>
          <dt className="text-zinc-500">recorded</dt>
          <dd className="tabular-nums text-zinc-900">${d.record_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</dd>
          {d.second_look && (
            <>
              <dt className="text-zinc-500">first read</dt>
              <dd className="tabular-nums text-zinc-600">{amount(d.first_read)} (second look taken)</dd>
            </>
          )}
        </dl>
      </div>
    </Card>
  );
}
