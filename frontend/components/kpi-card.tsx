import type { LucideIcon } from "lucide-react";
import clsx from "clsx";

type Accent = "default" | "good" | "warn" | "bad" | "citrine";

export function KpiCard({
  icon: Icon,
  label,
  value,
  accent = "default",
  hint,
  emphasis = false,
}: {
  icon: LucideIcon;
  label: string;
  value: string | number;
  accent?: Accent;
  hint?: string;
  emphasis?: boolean;
}) {
  const tone: Record<Accent, string> = {
    default: "text-[var(--ink-dim)]",
    good: "text-[var(--sage)]",
    warn: "text-[var(--amber)]",
    bad: "text-[var(--copper)]",
    citrine: "text-[var(--citrine)]",
  };
  return (
    <div
      className={clsx(
        "card-aged p-5 flex flex-col gap-4 relative overflow-hidden",
        emphasis && "accent-bar-left",
      )}
    >
      <div className="flex items-start justify-between">
        <span className="meta">{label}</span>
        <Icon size={14} className={tone[accent]} strokeWidth={1.5} />
      </div>
      <div className="font-mono text-[40px] leading-none tracking-tight text-[var(--ink)]">
        {value}
      </div>
      {hint && <div className="text-[11px] text-[var(--ink-dim)] leading-relaxed">{hint}</div>}
    </div>
  );
}
