"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ScanLine, GitGraph, FileSearch, ShieldCheck, Cpu, Activity } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scan", label: "Live Scan", icon: Activity },
  { href: "/compare", label: "Model Showdown", icon: ScanLine },
  { href: "/mosaic", label: "Mosaic Graph", icon: GitGraph },
  { href: "/dsar", label: "DSAR Copilot", icon: ShieldCheck },
  { href: "/findings", label: "Findings", icon: FileSearch },
  { href: "/agents", label: "Agents", icon: Cpu },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 shrink-0 border-r border-[var(--border)] flex flex-col bg-[var(--bg-elev)]">
      <div className="px-5 pt-6 pb-8 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent-2)] glow-accent" />
        <div className="flex flex-col leading-tight">
          <span className="font-semibold text-[15px] tracking-tight">Forgetter</span>
          <span className="text-[10px] text-[var(--fg-dim)] uppercase tracking-widest">Bosch GDPR</span>
        </div>
      </div>
      <nav className="flex-1 px-3 flex flex-col gap-0.5">
        {NAV.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                active
                  ? "bg-[var(--bg-card)] text-[var(--fg)]"
                  : "text-[var(--fg-dim)] hover:text-[var(--fg)] hover:bg-[var(--bg-card)]/40",
              )}
            >
              <Icon size={16} strokeWidth={1.75} />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-[var(--border)] flex flex-col gap-2">
        <div className="text-[11px] text-[var(--fg-dim)] uppercase tracking-widest">Local-first AI</div>
        <div className="text-[10px] text-[var(--fg-dim)] leading-relaxed">
          Zero cloud, zero egress. GLiNER + LFM2 on-prem. Schrems II safe.
        </div>
      </div>
    </aside>
  );
}
