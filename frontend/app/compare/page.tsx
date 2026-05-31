"use client";

import { useState } from "react";
import { api, type CompareResponse } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Beaker } from "lucide-react";

const SAMPLE_DE = `Spesenabrechnung (ausgefüllt)
Mitarbeiter: Hans Müller (E-43217)
Abteilung: Forschung & Entwicklung
Datum: 12 Mär 2026
Vorgesetzter: Anna Becker
E-Mail: hans.mueller@bosch.example
Telefon: +49 711 123456
Steuernummer: DE123456789
Unterschrift: A. Becker`;

const MODEL_META: Record<string, { tier: string; tone: string; pitch: string }> = {
  presidio: { tier: "T1", tone: "var(--good)", pitch: "regex+NER, instant, deterministic" },
  gliner: { tier: "T2", tone: "var(--accent)", pitch: "200M multilingual NER, CPU-fast" },
  reasoner: { tier: "T3", tone: "var(--warn)", pitch: "LFM2 reasoning, ambiguous spans only" },
};

export default function ComparePage() {
  const [text, setText] = useState(SAMPLE_DE);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const r = await api.scanAll(text, ["presidio", "gliner"]);
      setResult(r);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        kicker="Showdown · 03"
        title="Model Showdown"
        subtitle="Run each tier against the same input. Side-by-side detection, latency, and cost projection."
        action={
          <button className="btn btn-primary" onClick={run} disabled={loading}>
            <Beaker size={14} /> {loading ? "Running..." : "Compare"}
          </button>
        }
      />

      <div className="px-8 mb-6">
        <div className="card p-4">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
            className="w-full bg-[var(--bg-elev)] border border-[var(--border)] rounded-lg p-3 text-sm code resize-none focus:outline-none focus:border-[var(--accent)]"
          />
        </div>
      </div>

      {result && (
        <div className="px-8 mb-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(result.results).map(([model, spans]) => {
              const meta = MODEL_META[model] || { tier: "?", tone: "var(--fg-dim)", pitch: "" };
              return (
                <div key={model} className="card overflow-hidden">
                  <div className="p-4 border-b border-[var(--border)]">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="kbd" style={{ color: meta.tone, borderColor: meta.tone }}>
                          {meta.tier}
                        </span>
                        <span className="font-semibold capitalize">{model}</span>
                      </div>
                      <span className="text-xs text-[var(--fg-dim)] font-mono">
                        {result.timing_ms[model]?.toFixed(0)}ms
                      </span>
                    </div>
                    <div className="text-xs text-[var(--fg-dim)]">{meta.pitch}</div>
                  </div>
                  <div className="p-4">
                    <div className="text-xs text-[var(--fg-dim)] mb-2">
                      <span className="font-mono">{spans.length}</span> spans detected
                    </div>
                    <div className="flex flex-col gap-1.5 max-h-72 overflow-y-auto">
                      {spans.length === 0 && (
                        <p className="text-[var(--fg-dim)] text-xs">No spans</p>
                      )}
                      {spans.map((s, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between gap-2 px-2 py-1.5 rounded bg-[var(--bg-elev)]"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span
                              className="text-[10px] uppercase tracking-widest font-medium px-1.5 py-0.5 rounded shrink-0"
                              style={{ color: meta.tone, background: `${meta.tone}1a` }}
                            >
                              {s.label}
                            </span>
                            <span className="text-xs code truncate">{s.value}</span>
                          </div>
                          <span className="text-[10px] font-mono text-[var(--fg-dim)] shrink-0">
                            {(s.score * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6 card p-5">
            <h3 className="text-xs uppercase tracking-widest text-[var(--fg-dim)] mb-3">Production cost projection</h3>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-[var(--fg-dim)] text-xs">Bosch / 1M docs</div>
                <div className="text-lg font-mono text-[var(--good)]">€1,000</div>
                <div className="text-[10px] text-[var(--fg-dim)] mt-0.5">local CPU, tiered</div>
              </div>
              <div>
                <div className="text-[var(--fg-dim)] text-xs">GPT-4o / 1M docs</div>
                <div className="text-lg font-mono text-[var(--bad)]">€50,000</div>
                <div className="text-[10px] text-[var(--fg-dim)] mt-0.5">cloud, full inference</div>
              </div>
              <div>
                <div className="text-[var(--fg-dim)] text-xs">Cost reduction</div>
                <div className="text-lg font-mono text-[var(--accent)]">50×</div>
                <div className="text-[10px] text-[var(--fg-dim)] mt-0.5">+ Schrems II safe</div>
              </div>
              <div>
                <div className="text-[var(--fg-dim)] text-xs">Latency p50</div>
                <div className="text-lg font-mono">~85ms</div>
                <div className="text-[10px] text-[var(--fg-dim)] mt-0.5">vs 2100ms cloud</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
