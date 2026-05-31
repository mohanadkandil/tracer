import type { LucideIcon } from "lucide-react";
import clsx from "clsx";

type Accent = "default" | "good" | "warn" | "bad";

export function KpiCard({
  icon: Icon,
  label,
  value,
  accent = "default",
  hint,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  accent?: Accent;
  hint?: string;
}) {
  const tone: Record<Accent, string> = {
    default: "text-[var(--accent)]",
    good: "text-[var(--good)]",
    warn: "text-[var(--warn)]",
    bad: "text-[var(--bad)]",
  };
  return (
    <div className="card p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-widest text-[var(--fg-dim)] font-medium">{label}</span>
        <Icon size={16} className={tone[accent]} strokeWidth={1.75} />
      </div>
      <div className={clsx("text-3xl font-semibold tracking-tight font-mono")}>{value}</div>
      {hint && <div className="text-xs text-[var(--fg-dim)]">{hint}</div>}
    </div>
  );
}
