import type { ButtonHTMLAttributes, ReactNode } from "react";
import { VERDICT, type Tone } from "@/lib/labels";
import type { Confidence, StepStatus, Verdict } from "@/lib/types";

const TONE: Record<Tone, string> = {
  red: "bg-red-50 text-red-800 ring-red-200",
  amber: "bg-amber-50 text-amber-900 ring-amber-200",
  sky: "bg-sky-50 text-sky-900 ring-sky-200",
  emerald: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  zinc: "bg-zinc-100 text-zinc-700 ring-zinc-200",
  blue: "bg-blue-50 text-blue-800 ring-blue-200",
};

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-xl border border-zinc-200 bg-white ${className}`}>{children}</section>;
}

export function Badge({ tone = "zinc", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE[tone]}`}>
      {children}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const v = VERDICT[verdict];
  return <Badge tone={v.tone}>{v.label}</Badge>;
}

export function ConfidencePill({ level }: { level: Confidence }) {
  const tone: Tone = level === "high" ? "red" : level === "medium" ? "amber" : "zinc";
  return <Badge tone={tone}>{level} confidence</Badge>;
}

const STEP_STATUS: Record<StepStatus, { label: string; tone: Tone }> = {
  PROPOSED: { label: "Awaiting approval", tone: "amber" },
  APPROVED: { label: "Approved", tone: "blue" },
  DONE: { label: "Done", tone: "emerald" },
  REJECTED: { label: "Rejected", tone: "zinc" },
  CLEARED: { label: "Cleared", tone: "emerald" },
  ESCALATED: { label: "Escalated", tone: "red" },
  STANDBY: { label: "Waiting", tone: "zinc" },
};

export function StatusPill({ status }: { status: StepStatus }) {
  const s = STEP_STATUS[status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`rounded-md bg-zinc-200/70 motion-safe:animate-pulse ${className}`} />;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <Card className="p-6">
      <p className="font-medium text-zinc-900">Couldn&apos;t load this.</p>
      <p className="mt-1 text-sm text-zinc-600">{message}</p>
      {onRetry && (
        <Button className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Card>
  );
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="font-medium text-zinc-900">{title}</p>
      <p className="mt-1 text-sm text-zinc-500">{hint}</p>
    </div>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost";
const VARIANT: Record<Variant, string> = {
  primary: "bg-blue-700 text-white hover:bg-blue-800 active:bg-blue-900",
  secondary: "bg-white text-zinc-900 ring-1 ring-inset ring-zinc-300 hover:bg-zinc-50 active:bg-zinc-100",
  danger: "bg-white text-red-700 ring-1 ring-inset ring-red-200 hover:bg-red-50 active:bg-red-100",
  ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
};

export function Button({
  variant = "secondary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600
        disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT[variant]} ${className}`}
    />
  );
}
