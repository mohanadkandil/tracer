"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type DSARRequestRecord } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Send, Mail, MessageSquare, Globe, Inbox as InboxIcon, Webhook } from "lucide-react";
import clsx from "clsx";

const SAMPLE_EMAIL = `From: hans.mueller@bosch.example
To: privacy@bosch.example
Subject: GDPR Article 17 erasure request

Dear Bosch Data Protection Office,

I, Hans Müller, hereby formally request the erasure of all personal
data relating to me from your systems, in accordance with Article 17
of the GDPR. My employee ID is E-43217.

Kindly confirm completion within 30 days.

Hans Müller
hans.mueller@bosch.example
`;

const SOURCE_LABELS: Record<string, { icon: any; label: string }> = {
  email: { icon: Mail, label: "Email" },
  web: { icon: Globe, label: "Web form" },
  api: { icon: Webhook, label: "API" },
  webhook: { icon: Webhook, label: "Webhook" },
  slack: { icon: MessageSquare, label: "MessageSquare" },
};

const STATUS_PILL: Record<string, string> = {
  pending: "pill-medium",
  approved: "pill-citrine",
  declined: "pill-critical",
  executed: "pill-low",
};

export default function DSARInboxPage() {
  const [items, setItems] = useState<DSARRequestRecord[]>([]);
  const [body, setBody] = useState(SAMPLE_EMAIL);
  const [source, setSource] = useState<"email" | "web" | "api">("email");
  const [submitting, setSubmitting] = useState(false);
  const [filter, setFilter] = useState<"all" | "pending" | "executed">("all");
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const status = filter === "all" ? undefined : filter;
      const r = await api.dsarRequests(status);
      setItems(r);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => { load(); }, [filter]);

  async function submit() {
    setSubmitting(true);
    setErr(null);
    try {
      const r = await api.dsarInbox({ body, source });
      await load();
      // Navigate to the new request page
      window.location.href = `/dsar/${r.id}`;
    } catch (e) {
      setErr(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        kicker="DSAR · 05"
        title="Erasure Copilot"
        subtitle="Universal intake — email, MessageSquare, web, API. Every request becomes a reviewable case with linked mosaic and signed certificate."
      />

      <div className="px-10 py-8 grid grid-cols-1 lg:grid-cols-5 gap-6 mb-12">
        {/* Intake form */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="kicker">New request · simulate intake</div>
              <div className="flex items-center bg-[var(--paper-elev)] border border-[var(--rule)] rounded-md overflow-hidden">
                {(["email", "api", "web"] as const).map((s) => {
                  const meta = SOURCE_LABELS[s];
                  const Icon = meta.icon;
                  return (
                    <button
                      key={s}
                      onClick={() => setSource(s)}
                      className={clsx(
                        "px-2 py-1 text-[10px] flex items-center gap-1 font-mono tracking-wide",
                        source === s ? "bg-[var(--paper-card)] text-[var(--ink)]" : "text-[var(--ink-dim)]",
                      )}
                    >
                      <Icon size={10} /> {meta.label.toUpperCase()}
                    </button>
                  );
                })}
              </div>
            </div>

            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={14}
              className="w-full bg-[var(--paper-elev)] border border-[var(--rule)] rounded-md p-3 text-[12.5px] code resize-none focus:outline-none focus:border-[var(--rule-strong)]"
              placeholder="Paste an erasure request email or message..."
            />
            <button
              className="btn btn-primary mt-3 w-full justify-center"
              onClick={submit}
              disabled={submitting || !body.trim()}
            >
              <Send size={13} /> {submitting ? "Submitting…" : "Submit request"}
            </button>
            <p className="text-[10.5px] text-[var(--ink-fade)] mt-2 leading-relaxed">
              Parses identifiers from the message (name, email, employee ID, GDPR article), creates a pending request, and fires a notification.
            </p>
          </div>

          {/* Integration cheat sheet */}
          <div className="card p-5">
            <div className="kicker mb-3">Integration · how to trigger from outside</div>
            <div className="flex flex-col gap-3 text-[11.5px] leading-relaxed">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Webhook size={12} className="text-[var(--ink-dim)]" />
                  <span className="font-medium">API webhook</span>
                </div>
                <div className="code bg-[var(--paper-elev)] border border-[var(--rule)] rounded p-2 text-[10.5px] whitespace-pre-wrap">
{`POST /dsar/inbox
{
  "body": "<email body>",
  "source": "email"
}`}
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <MessageSquare size={12} className="text-[var(--ink-dim)]" />
                  <span className="font-medium">MessageSquare incoming webhook</span>
                </div>
                <p className="text-[var(--ink-dim)]">
                  Set <span className="kbd">SLACK_WEBHOOK_URL</span> in backend env — every notification is also posted to your MessageSquare channel with Block Kit + Review button.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Inbox */}
        <div className="lg:col-span-3">
          <div className="flex items-center gap-2 mb-4">
            <div className="kicker">Inbox</div>
            <div className="flex items-center bg-[var(--paper-card)] border border-[var(--rule)] rounded-md overflow-hidden ml-auto">
              {(["all", "pending", "executed"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={clsx(
                    "px-3 py-1.5 text-[11px] font-mono tracking-wide uppercase",
                    filter === f ? "bg-[var(--paper-elev)] text-[var(--ink)]" : "text-[var(--ink-dim)]",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {err && <div className="card p-4 text-[var(--oxblood)] text-[13px] mb-4">{err}</div>}

          {items.length === 0 ? (
            <div className="card p-10 text-center">
              <InboxIcon size={24} className="mx-auto text-[var(--ink-fade)] mb-2" />
              <p className="text-[13px] text-[var(--ink-dim)]">No requests in this view yet.</p>
              <p className="text-[11px] text-[var(--ink-fade)] mt-1">Submit one on the left to see the flow.</p>
            </div>
          ) : (
            <div className="card overflow-hidden">
              {items.map((r, idx) => {
                const SrcIcon = SOURCE_LABELS[r.source]?.icon || Mail;
                return (
                  <Link
                    key={r.id}
                    href={`/dsar/${r.id}`}
                    className={clsx(
                      "block px-5 py-4 hover:bg-[var(--paper-aged)]/40 transition-colors",
                      idx > 0 && "border-t border-[var(--rule)]",
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-1 text-[var(--ink-dim)]">
                        <SrcIcon size={13} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline gap-2">
                          <span className="font-display text-[18px] text-[var(--ink)] leading-tight">{r.subject}</span>
                          <span className="kicker">Art. {r.article}</span>
                        </div>
                        <div className="text-[11.5px] text-[var(--ink-dim)] mt-1 flex flex-wrap gap-x-3 gap-y-1">
                          {r.requester_email && <span className="code">{r.requester_email}</span>}
                          <span>via {r.source}</span>
                          <span>{new Date(r.created_at).toLocaleString()}</span>
                          {r.status === "executed" && (
                            <span className="text-[var(--sage)]">
                              {r.files_processed} files · {r.findings_erased} findings erased
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="shrink-0">
                        <span className={`pill ${STATUS_PILL[r.status]}`}>{r.status}</span>
                      </div>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
