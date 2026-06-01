"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, type DSARPlan, type DSARRequestRecord, type PersonIdentity } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ArrowLeft, Check, X, FileText, ShieldCheck, AlertTriangle, Download } from "lucide-react";

type Detail = DSARRequestRecord & { plan: DSARPlan; identity: PersonIdentity | null };

export default function DSARDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [req, setReq] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<"" | "decide" | "execute">("");
  const [note, setNote] = useState("");

  async function load() {
    try {
      const r = await api.dsarRequest(id);
      setReq(r);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => { load(); }, [id]);

  async function decide(d: "approve" | "decline") {
    setPending("decide");
    try {
      await api.dsarDecide(id, d, note || undefined, "DPO (demo)");
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setPending("");
    }
  }

  async function execute() {
    if (!confirm(`Execute erasure for ${req?.subject}? This permanently removes findings.`)) return;
    setPending("execute");
    try {
      await api.dsarExecuteRequest(id);
      await load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setPending("");
    }
  }

  if (err) return <div className="p-10 text-[var(--oxblood)]">{err}</div>;
  if (!req) return <div className="p-10 text-[var(--ink-dim)]">Loading…</div>;

  const isPending = req.status === "pending";
  const isApproved = req.status === "approved";
  const isExecuted = req.status === "executed";
  const isDeclined = req.status === "declined";

  const toDelete = req.plan.matches.filter((m) => m.proposed_action === "delete");

  return (
    <div>
      <PageHeader
        kicker={`Request · ${req.id}`}
        title={req.subject}
        subtitle={`Article ${req.article} GDPR · source: ${req.source}${req.requester_email ? ` · ${req.requester_email}` : ""}`}
        action={
          <button onClick={() => router.push("/dsar")} className="btn btn-ghost">
            <ArrowLeft size={13} /> Back to inbox
          </button>
        }
      />

      <div className="px-10 py-8">
        {/* Status banner */}
        <div className="mb-8">
          {isPending && (
            <div className="card p-5 border-l-4 border-[var(--copper)]">
              <div className="kicker mb-2 text-[var(--copper)]">Awaiting decision</div>
              <p className="text-[13px] text-[var(--ink)] mb-4 leading-relaxed">
                Review the forgetting plan below. Approve to allow execution, decline to reject.
                Add an optional note for audit trail.
              </p>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Decision note (optional)"
                className="w-full bg-[var(--paper-elev)] border border-[var(--rule)] rounded-md px-3 py-2 text-[13px] mb-3 focus:outline-none focus:border-[var(--rule-strong)]"
              />
              <div className="flex gap-2">
                <button className="btn btn-citrine" onClick={() => decide("approve")} disabled={!!pending}>
                  <Check size={13} /> {pending === "decide" ? "Saving…" : "Approve"}
                </button>
                <button className="btn" onClick={() => decide("decline")} disabled={!!pending}>
                  <X size={13} /> Decline
                </button>
              </div>
            </div>
          )}

          {isApproved && (
            <div className="card p-5 border-l-4 border-[var(--citrine)]">
              <div className="kicker mb-2" style={{ color: "#7a8523" }}>Approved · ready to execute</div>
              <p className="text-[13px] text-[var(--ink)] mb-4 leading-relaxed">
                Approved by <span className="code">{req.decided_by || "—"}</span>
                {req.decision_note && <> · note: <span className="text-[var(--ink-dim)]">{req.decision_note}</span></>}
              </p>
              <button className="btn btn-primary" onClick={execute} disabled={!!pending}>
                <ShieldCheck size={13} /> {pending === "execute" ? "Executing…" : `Execute erasure (${toDelete.length} files)`}
              </button>
            </div>
          )}

          {isExecuted && (
            <div className="card p-5 border-l-4 border-[var(--sage)]">
              <div className="kicker mb-2" style={{ color: "var(--sage)" }}>Executed</div>
              <p className="text-[13px] text-[var(--ink)] mb-4 leading-relaxed">
                {req.files_processed} files processed · {req.findings_erased} findings erased.
              </p>
              <a href={api.dsarCertUrl(req.id)} target="_blank" rel="noopener" className="btn btn-gold">
                <Download size={13} /> Download certificate
              </a>
            </div>
          )}

          {isDeclined && (
            <div className="card p-5 border-l-4 border-[var(--oxblood)]">
              <div className="kicker mb-2 text-[var(--oxblood)]">Declined</div>
              <p className="text-[13px] text-[var(--ink-dim)] leading-relaxed">
                Declined by <span className="code text-[var(--ink)]">{req.decided_by || "—"}</span>
                {req.decision_note && <> · {req.decision_note}</>}
              </p>
            </div>
          )}
        </div>

        {/* Plan + identity grid */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-12">
          <div className="lg:col-span-3 card overflow-hidden">
            <div className="px-5 py-3 border-b border-[var(--rule)] flex items-center justify-between">
              <div>
                <div className="kicker">Forgetting plan</div>
                <h3 className="font-display text-[18px] mt-1">{req.plan.matches.length} files matched</h3>
              </div>
              <div className="text-[11px] font-mono text-[var(--ink-dim)]">
                {toDelete.length} delete · {req.plan.matches.length - toDelete.length} anonymize
              </div>
            </div>

            {req.plan.summary && (
              <div className="px-5 py-3 border-b border-[var(--rule)] text-[12.5px] text-[var(--ink)] leading-relaxed">
                {req.plan.summary}
              </div>
            )}

            {req.plan.risk_notes.length > 0 && (
              <div className="px-5 py-3 border-b border-[var(--rule)] flex flex-col gap-2">
                {req.plan.risk_notes.map((n, i) => (
                  <div key={i} className="flex items-start gap-2 text-[12px] text-[var(--copper)]">
                    <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                    <span>{n}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="max-h-[60vh] overflow-y-auto">
              {req.plan.matches.length === 0 && (
                <div className="p-8 text-center text-[var(--ink-dim)] text-[13px]">
                  No files matched. Subject identifiers may be inactive or not yet indexed.
                </div>
              )}
              {req.plan.matches.map((m) => (
                <div key={m.file_path} className="px-5 py-3 border-b border-[var(--rule)] last:border-0">
                  <div className="flex items-start gap-3">
                    <FileText size={13} className="text-[var(--ink-dim)] mt-1 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="code text-[12px] text-[var(--ink)] break-all">{m.file_path}</div>
                      <div className="text-[11.5px] text-[var(--ink-dim)] mt-1 leading-relaxed">{m.reason}</div>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {m.matched_terms.slice(0, 5).map((t, i) => (
                          <span key={i} className="kbd">{t}</span>
                        ))}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      <span className={`pill ${
                        m.proposed_action === "delete" ? "pill-high" :
                        m.proposed_action === "anonymize" ? "pill-medium" : "pill-low"
                      }`}>{m.proposed_action}</span>
                      <span className="text-[10px] font-mono text-[var(--ink-dim)]">
                        {(m.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Identity panel — mosaic of subject */}
          <div className="lg:col-span-2 card p-6 self-start">
            <div className="kicker mb-3">Subject identity · mosaic</div>
            {!req.identity ? (
              <p className="text-[13px] text-[var(--ink-dim)] leading-relaxed">
                No mosaic data for this subject. Run a scan first or verify the name spelling.
              </p>
            ) : (
              <div>
                <div className="display-md text-[var(--ink)] leading-none">{req.identity.display_name}</div>
                <div className="code text-[var(--ink-dim)] mt-1 text-[10.5px]">{req.identity.canonical}</div>

                <div className="mt-4 flex items-center gap-3">
                  <span className={`pill pill-${req.identity.re_id_risk}`}>Re-ID · {req.identity.re_id_risk}</span>
                  <span className="text-[11px] text-[var(--ink-dim)] font-mono">{req.identity.file_count} files</span>
                </div>

                {req.identity.risk_factors.length > 0 && (
                  <div className="mt-3 pl-3 border-l-2 border-[var(--copper)]">
                    {req.identity.risk_factors.map((f, i) => (
                      <p key={i} className="text-[11px] text-[var(--ink-dim)] leading-relaxed mb-1">{f}</p>
                    ))}
                  </div>
                )}

                <div className="mt-5 flex flex-col gap-3">
                  {Object.entries(req.identity.identifiers).map(([label, values]) => (
                    <div key={label}>
                      <div className="kicker mb-1">{label}</div>
                      <div className="flex flex-wrap gap-1">
                        {values.slice(0, 6).map((v, i) => (
                          <span key={i} className="kbd">{v}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-5 pt-4 border-t border-[var(--rule)]">
                  <Link href="/mosaic" className="text-[12px] text-[var(--ink-dim)] hover:text-[var(--ink)]">
                    View in Mosaic graph →
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
