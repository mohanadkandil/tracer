"use client";

import { useState } from "react";
import { api, type DSARPlan } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Send, ShieldCheck, AlertTriangle, FileText, Trash2 } from "lucide-react";

const SAMPLE_EMAIL = `Subject: GDPR Article 17 Erasure Request

Dear Bosch Data Protection Office,

I, Hans Müller, hereby formally request the erasure of all personal data
relating to me from your systems, in accordance with Article 17 of the
GDPR.

Kindly confirm completion within 30 days.

Hans Müller
hans.mueller@bosch.example
`;

export default function DSARPage() {
  const [email, setEmail] = useState(SAMPLE_EMAIL);
  const [subject, setSubject] = useState("Hans Müller");
  const [plan, setPlan] = useState<DSARPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [executed, setExecuted] = useState<{ files_processed: number; findings_erased: number } | null>(null);

  async function runPlan() {
    setLoading(true);
    setErr(null);
    setPlan(null);
    setExecuted(null);
    try {
      const result = await api.dsarPlan(subject, "17");
      setPlan(result);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function execute() {
    if (!confirm(`Execute erasure for ${subject}? This deletes findings records (demo-mode, files preserved).`)) return;
    setLoading(true);
    try {
      const r = await api.dsarExecute(subject, "17");
      setExecuted({ files_processed: r.files_processed, findings_erased: r.findings_erased });
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="DSAR Copilot"
        subtitle="Article 17 right-to-erasure workflow. Paste the request, the agent finds every file, proposes actions, generates the compliance certificate."
      />

      <div className="px-8 grid grid-cols-1 lg:grid-cols-5 gap-4 mb-12">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="card p-5">
            <h3 className="text-xs uppercase tracking-widest text-[var(--fg-dim)] mb-3">Erasure request</h3>
            <textarea
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              rows={10}
              className="w-full bg-[var(--bg-elev)] border border-[var(--border)] rounded-lg p-3 text-sm code resize-none focus:outline-none focus:border-[var(--accent)]"
              placeholder="Paste the erasure request email..."
            />
            <div className="mt-3 flex items-center gap-2">
              <label className="text-xs text-[var(--fg-dim)]">Subject</label>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="flex-1 bg-[var(--bg-elev)] border border-[var(--border)] rounded-md px-2 py-1.5 text-sm focus:outline-none focus:border-[var(--accent)]"
              />
              <button className="btn btn-primary" onClick={runPlan} disabled={loading}>
                <Send size={14} /> {loading ? "Planning..." : "Run plan"}
              </button>
            </div>
          </div>

          {plan && (
            <div className="card p-5">
              <h3 className="text-xs uppercase tracking-widest text-[var(--fg-dim)] mb-3">Reasoner summary</h3>
              <p className="text-sm text-[var(--fg)] leading-relaxed">{plan.summary}</p>
              {plan.risk_notes.length > 0 && (
                <div className="mt-4 flex flex-col gap-2">
                  {plan.risk_notes.map((n, i) => (
                    <div key={i} className="flex items-start gap-2 text-xs text-[var(--warn)]">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{n}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-3">
          {err && (
            <div className="card p-4 mb-3 text-[var(--bad)] text-sm">{err}</div>
          )}
          {!plan && !err && (
            <div className="card p-8 text-center text-[var(--fg-dim)]">
              <ShieldCheck size={28} className="mx-auto mb-3 text-[var(--fg-dim)]" />
              <p className="text-sm">Run plan to see the Forgetting Plan and proposed actions.</p>
            </div>
          )}
          {plan && (
            <div className="card overflow-hidden">
              <div className="p-5 border-b border-[var(--border)] flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold">Forgetting Plan</h3>
                  <p className="text-xs text-[var(--fg-dim)] mt-0.5">
                    Subject: <span className="text-[var(--fg)]">{plan.subject}</span> · Article {plan.article} ·{" "}
                    {plan.matches.length} files matched
                  </p>
                </div>
                <button className="btn btn-primary" onClick={execute} disabled={loading || plan.matches.length === 0}>
                  <Trash2 size={14} /> Execute erasure
                </button>
              </div>

              {executed && (
                <div className="px-5 py-3 bg-[var(--good)]/10 border-b border-[var(--border)] text-[var(--good)] text-sm flex items-center gap-2">
                  <ShieldCheck size={16} /> Erased {executed.findings_erased} findings across{" "}
                  {executed.files_processed} files. Compliance certificate available.
                </div>
              )}

              <div className="max-h-[60vh] overflow-y-auto">
                {plan.matches.length === 0 && (
                  <div className="p-8 text-center text-[var(--fg-dim)] text-sm">
                    No files matched. Try a different subject or run a scan first.
                  </div>
                )}
                {plan.matches.map((m) => (
                  <div key={m.file_path} className="px-5 py-3 border-b border-[var(--border)] last:border-0">
                    <div className="flex items-start gap-3">
                      <FileText size={14} className="text-[var(--fg-dim)] mt-1 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs code text-[var(--fg)] break-all">{m.file_path}</div>
                        <div className="text-xs text-[var(--fg-dim)] mt-1">{m.reason}</div>
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {m.matched_terms.slice(0, 6).map((t, i) => (
                            <span key={i} className="kbd">{t}</span>
                          ))}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-1.5 shrink-0">
                        <span
                          className={`pill ${
                            m.proposed_action === "delete"
                              ? "pill-high"
                              : m.proposed_action === "anonymize"
                                ? "pill-medium"
                                : "pill-low"
                          }`}
                        >
                          {m.proposed_action}
                        </span>
                        <span className="text-[10px] font-mono text-[var(--fg-dim)]">
                          conf {(m.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
