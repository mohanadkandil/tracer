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
        title="Compliance Dashboard"
        subtitle="Bosch • SharePoint / OneDrive / FileShares • Local-first scan results"
      />

      {err && (
        <div className="mx-8 mb-4 card p-4 text-[var(--bad)] text-sm">
          {err}
          <div className="text-[var(--fg-dim)] text-xs mt-1">Is the API running at http://localhost:8000?</div>
        </div>
      )}

      <div className="px-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard icon={Files} label="Files with findings" value={filesScanned} accent="default" />
        <KpiCard icon={FileSearch} label="Total findings" value={totalFindings} accent="default" />
        <KpiCard icon={ShieldAlert} label="High+critical" value={critical} accent={critical > 0 ? "bad" : "good"} />
        <KpiCard icon={Cpu} label="Detectors active" value={detectorEntries.length || 0} accent="default" />
      </div>

      <div className="px-8 grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <div className="card p-5 lg:col-span-2">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            By Label
          </h3>
          {labelEntries.length === 0 && (
            <p className="text-[var(--fg-dim)] text-sm">
              No findings yet. Start a scan from the <span className="text-[var(--fg)]">Live Scan</span> tab.
            </p>
          )}
          <div className="flex flex-col gap-3">
            {labelEntries.map(([label, count]) => {
              const max = labelEntries[0]?.[1] || 1;
              const pct = (count / max) * 100;
              return (
                <div key={label} className="flex items-center gap-3">
                  <div className="w-32 text-xs text-[var(--fg-dim)] font-medium">{label}</div>
                  <div className="flex-1 h-2 rounded-full bg-[var(--bg-elev)] overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--accent-2)]"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="w-12 text-right text-sm font-mono">{count}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            Severity
          </h3>
          {(["critical", "high", "medium", "low"] as const).map((sev) => {
            const c = summary?.by_severity[sev] ?? 0;
            return (
              <div key={sev} className="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0">
                <span className={`pill pill-${sev}`}>{sev}</span>
                <span className="font-mono">{c}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="px-8 grid grid-cols-1 lg:grid-cols-2 gap-4 mb-12">
        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            Top Exposed Owners
          </h3>
          {topOwners.length === 0 && <p className="text-[var(--fg-dim)] text-sm">No data yet</p>}
          <ul className="flex flex-col gap-2">
            {topOwners.slice(0, 8).map((o) => (
              <li key={o.owner} className="flex items-center justify-between text-sm">
                <span className="text-[var(--fg)]">{o.owner}</span>
                <span className="font-mono text-[var(--fg-dim)]">{o.count} findings</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            Detector Mix (Tiered Routing)
          </h3>
          {detectorEntries.length === 0 && <p className="text-[var(--fg-dim)] text-sm">No data yet</p>}
          <div className="flex flex-col gap-3">
            {detectorEntries.map(([d, c]) => {
              const total = detectorEntries.reduce((s, [, n]) => s + n, 0) || 1;
              const pct = (c / total) * 100;
              const tier = d === "presidio" ? "T1" : d === "gliner" ? "T2" : "T3";
              return (
                <div key={d}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">
                      <span className="kbd mr-2">{tier}</span>
                      {d}
                    </span>
                    <span className="text-xs text-[var(--fg-dim)] font-mono">
                      {pct.toFixed(0)}% • {c} spans
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--bg-elev)] overflow-hidden">
                    <div
                      className="h-full"
                      style={{
                        width: `${pct}%`,
                        background: d === "presidio" ? "var(--good)" : d === "gliner" ? "var(--accent)" : "var(--warn)",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
