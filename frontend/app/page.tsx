"use client";

import { useEffect, useState } from "react";
import { api, type Summary } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { KpiCard } from "@/components/kpi-card";
import { ShieldAlert, FileSearch, Files, Cpu } from "lucide-react";

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.summary().then(setSummary).catch((e) => setErr(String(e)));
  }, []);

  const totalFindings = summary?.total_findings ?? 0;
  const filesScanned = summary?.files_with_findings ?? 0;
  const critical = (summary?.by_severity["critical"] ?? 0) + (summary?.by_severity["high"] ?? 0);
  const labelEntries = Object.entries(summary?.by_label ?? {}).sort((a, b) => b[1] - a[1]);
  const detectorEntries = Object.entries(summary?.by_detector ?? {});
  const topOwners = summary?.top_exposed_owners ?? [];

  return (
    <div>
      <PageHeader
        kicker="Overview · 01"
        title="Compliance Dossier"
        subtitle="Bosch · SharePoint, OneDrive, FileShares. Local-first scan results, tiered detection, mosaic-linked identities."
      />

      <div className="px-10 py-8">
        {err && (
          <div className="mb-8 border-l-4 border-[var(--oxblood)] bg-[var(--paper-card)] p-4 text-[13px]">
            <div className="kicker mb-1 text-[var(--oxblood)]">Backend unreachable</div>
            <div className="text-[var(--ink)] code">{err}</div>
            <div className="text-[var(--ink-dim)] text-[11px] mt-1">
              Is the API running at <span className="kbd">localhost:8000</span>?
            </div>
          </div>
        )}

        {/* KPI strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
          <KpiCard icon={Files} label="Files Scanned" value={filesScanned} />
          <KpiCard icon={FileSearch} label="Total Findings" value={totalFindings} />
          <KpiCard
            icon={ShieldAlert}
            label="High + Critical"
            value={critical}
            accent={critical > 0 ? "bad" : "good"}
            emphasis={critical > 0}
          />
          <KpiCard icon={Cpu} label="Detectors Active" value={detectorEntries.length || 0} />
        </div>

        {/* Editorial 2-col */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-10">
          <section className="lg:col-span-2">
            <SectionHeader kicker="03" title="Detection by Label" caption="distribution across all scanned documents" />
            {labelEntries.length === 0 ? (
              <p className="text-[13px] text-[var(--ink-dim)]">
                No findings yet. Start a scan from the <span className="text-[var(--ink)]">Live Scan</span> tab.
              </p>
            ) : (
              <div className="flex flex-col">
                {labelEntries.map(([label, count], idx) => {
                  const max = labelEntries[0]?.[1] || 1;
                  const pct = (count / max) * 100;
                  return (
                    <div
                      key={label}
                      className={`flex items-center gap-4 py-3 ${idx > 0 ? "border-t border-[var(--rule)]" : ""}`}
                    >
                      <div className="font-mono text-[10.5px] text-[var(--ink-fade)] w-8">
                        {String(idx + 1).padStart(2, "0")}
                      </div>
                      <div className="w-40 text-[12.5px] text-[var(--ink)]">{label}</div>
                      <div className="flex-1 h-[3px] bg-[var(--paper-card)] overflow-hidden">
                        <div className="h-full bg-[var(--citrine)]" style={{ width: `${pct}%` }} />
                      </div>
                      <div className="w-14 text-right font-mono text-[14px] text-[var(--ink)]">{count}</div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>

          <section>
            <SectionHeader kicker="04" title="Severity" caption="risk profile" />
            <div className="flex flex-col">
              {(["critical", "high", "medium", "low"] as const).map((sev, idx) => {
                const c = summary?.by_severity[sev] ?? 0;
                return (
                  <div
                    key={sev}
                    className={`flex items-center justify-between py-3 ${idx > 0 ? "border-t border-[var(--rule)]" : ""}`}
                  >
                    <span className={`pill pill-${sev}`}>{sev}</span>
                    <span className="font-mono text-[15px]">{c}</span>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* Owners + detector mix */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-12">
          <section>
            <SectionHeader kicker="05" title="Top Exposed Owners" caption="who holds the most PII" />
            {topOwners.length === 0 ? (
              <p className="text-[13px] text-[var(--ink-dim)]">No data yet.</p>
            ) : (
              <ul className="flex flex-col">
                {topOwners.slice(0, 8).map((o, idx) => (
                  <li
                    key={o.owner}
                    className={`flex items-center justify-between py-2.5 text-[13px] ${
                      idx > 0 ? "border-t border-[var(--rule)]" : ""
                    }`}
                  >
                    <span className="code text-[var(--ink)]">{o.owner}</span>
                    <span className="font-mono text-[var(--ink-dim)] text-[12px]">
                      {o.count} <span className="text-[10px] tracking-wider uppercase text-[var(--ink-fade)] ml-1">findings</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section>
            <SectionHeader kicker="06" title="Detector Mix" caption="tiered routing — cost-aware escalation" />
            {detectorEntries.length === 0 ? (
              <p className="text-[13px] text-[var(--ink-dim)]">No data yet.</p>
            ) : (
              <div className="flex flex-col gap-4">
                {detectorEntries.map(([d, c]) => {
                  const total = detectorEntries.reduce((s, [, n]) => s + n, 0) || 1;
                  const pct = (c / total) * 100;
                  const tier = d === "presidio" ? "T1" : d === "gliner" ? "T2" : "T3";
                  const color = d === "presidio" ? "var(--sage)" : d === "gliner" ? "var(--citrine)" : "var(--amber)";
                  return (
                    <div key={d}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[13px] flex items-center gap-2.5">
                          <span className="kbd">{tier}</span>
                          <span className="font-mono">{d}</span>
                        </span>
                        <span className="font-mono text-[11px] text-[var(--ink-dim)]">
                          {pct.toFixed(0)}% · {c}
                        </span>
                      </div>
                      <div className="h-[2px] bg-[var(--paper-card)] overflow-hidden">
                        <div className="h-full" style={{ width: `${pct}%`, background: color }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ kicker, title, caption }: { kicker: string; title: string; caption?: string }) {
  return (
    <div className="mb-5">
      <div className="flex items-baseline gap-3 mb-1">
        <span className="font-mono text-[10.5px] tracking-widest text-[var(--ink-fade)]">§{kicker}</span>
        <h3 className="font-display text-[20px] text-[var(--ink)] leading-tight">{title}</h3>
      </div>
      {caption && <div className="text-[11px] text-[var(--ink-fade)] mt-0.5">{caption}</div>}
    </div>
  );
}
