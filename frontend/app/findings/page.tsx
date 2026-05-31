"use client";

import { useEffect, useState } from "react";
import { api, type Finding } from "@/lib/api";
import { PageHeader } from "@/components/page-header";

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[]>([]);
  const [filterLabel, setFilterLabel] = useState<string>("");
  const [filterOwner, setFilterOwner] = useState<string>("");

  useEffect(() => {
    api.findings({ label: filterLabel || undefined, owner: filterOwner || undefined, limit: 200 }).then(setFindings);
  }, [filterLabel, filterOwner]);

  const labels = Array.from(new Set(findings.map((f) => f.label))).sort();

  return (
    <div>
      <PageHeader title="Findings" subtitle="Every PII span persisted across all scans." />

      <div className="px-8 mb-4 flex items-center gap-3">
        <input
          placeholder="Filter owner..."
          value={filterOwner}
          onChange={(e) => setFilterOwner(e.target.value)}
          className="bg-[var(--bg-card)] border border-[var(--border)] rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--accent)]"
        />
        <select
          value={filterLabel}
          onChange={(e) => setFilterLabel(e.target.value)}
          className="bg-[var(--bg-card)] border border-[var(--border)] rounded-md px-3 py-1.5 text-sm focus:outline-none focus:border-[var(--accent)]"
        >
          <option value="">All labels</option>
          {labels.map((l) => (
            <option key={l}>{l}</option>
          ))}
        </select>
        <span className="text-xs text-[var(--fg-dim)] ml-auto">{findings.length} rows</span>
      </div>

      <div className="px-8 pb-12">
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-elev)] text-[var(--fg-dim)] text-[10px] uppercase tracking-widest">
              <tr>
                <th className="text-left px-4 py-2.5">Label</th>
                <th className="text-left px-4 py-2.5">Value</th>
                <th className="text-left px-4 py-2.5">Severity</th>
                <th className="text-left px-4 py-2.5">Owner</th>
                <th className="text-left px-4 py-2.5">Detector</th>
                <th className="text-right px-4 py-2.5">Score</th>
                <th className="text-left px-4 py-2.5">File</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.id} className="border-t border-[var(--border)] hover:bg-[var(--bg-elev)]/40">
                  <td className="px-4 py-2">
                    <span className="kbd">{f.label}</span>
                  </td>
                  <td className="px-4 py-2 code">{f.value}</td>
                  <td className="px-4 py-2"><span className={`pill pill-${f.severity}`}>{f.severity}</span></td>
                  <td className="px-4 py-2 text-[var(--fg-dim)]">{f.owner ?? "—"}</td>
                  <td className="px-4 py-2 text-[var(--fg-dim)]">{f.detector}</td>
                  <td className="px-4 py-2 text-right font-mono">{(f.score * 100).toFixed(0)}%</td>
                  <td className="px-4 py-2 text-[var(--fg-dim)] code truncate max-w-xs" title={f.file_path}>{f.file_path}</td>
                </tr>
              ))}
              {findings.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-[var(--fg-dim)]">No findings. Start a scan.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
