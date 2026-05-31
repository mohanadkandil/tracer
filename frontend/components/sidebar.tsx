"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ScanLine, GitGraph, FileSearch, ShieldCheck, Cpu, Activity } from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/", label: "Dashboard", num: "01", icon: LayoutDashboard },
  { href: "/scan", label: "Live Scan", num: "02", icon: Activity },
  { href: "/compare", label: "Showdown", num: "03", icon: ScanLine },
  { href: "/mosaic", label: "Mosaic", num: "04", icon: GitGraph },
  { href: "/dsar", label: "DSAR", num: "05", icon: ShieldCheck },
  { href: "/findings", label: "Findings", num: "06", icon: FileSearch },
  { href: "/agents", label: "Agents", num: "07", icon: Cpu },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-[232px] shrink-0 border-r border-[var(--rule)] flex flex-col bg-[var(--paper-elev)]">
      <div className="px-6 pt-7 pb-6">
        <div className="display-md leading-none text-[var(--ink)]">Forgetter</div>
        <div className="kicker mt-2 text-[var(--ink-fade)]">Bosch · GDPR Discovery</div>
      </div>

      <div className="rule mx-6 mb-4" />

      <nav className="flex-1 px-3 flex flex-col gap-px">
        {NAV.map((item) => {
          const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "group flex items-center gap-3 pl-3 pr-3 py-2 text-[13px] rounded-md transition-all duration-100",
                active
                  ? "bg-[var(--paper-card)] text-[var(--ink)] shadow-paper"
                  : "text-[var(--ink-dim)] hover:text-[var(--ink)] hover:bg-[var(--paper-card)]/60",
              )}
            >
              <span className="font-mono text-[10px] tracking-widest text-[var(--ink-fade)] w-5">{item.num}</span>
              <Icon size={14} strokeWidth={1.6} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-6 py-5 border-t border-[var(--rule)] flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--citrine)] pulse-dot" />
          <span className="kicker text-[var(--ink)]">Local-First</span>
        </div>
        <p className="text-[10.5px] leading-relaxed text-[var(--ink-fade)]">
          Zero cloud, zero egress.<br />
          Schrems II safe.
        </p>
      </div>
    </aside>
  );
}
