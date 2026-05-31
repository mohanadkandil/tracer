"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, type MosaicGraph, type PersonIdentity } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Search, Network } from "lucide-react";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const LABEL_COLOR: Record<string, string> = {
  PERSON: "#fc6c3f",
  EMPLOYEE_ID: "#2dd28d",
  EMAIL: "#5ea4ff",
  PHONE: "#f6c945",
  ADDRESS: "#ff5277",
  TAX_ID: "#ff3060",
  USERNAME: "#9b6dff",
  SIGNATURE: "#fc6c3f",
};

export default function MosaicPage() {
  const [graph, setGraph] = useState<MosaicGraph | null>(null);
  const [query, setQuery] = useState("");
  const [person, setPerson] = useState<PersonIdentity | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.graph().then(setGraph).catch((e) => setErr(String(e)));
  }, []);

  async function lookup() {
    if (!query.trim()) return;
    setPerson(null);
    setErr(null);
    try {
      const r = await api.person(query.trim());
      setPerson(r);
    } catch (e) {
      setErr(String(e));
    }
  }

  const data = graph
    ? {
        nodes: graph.nodes.map((n) => ({
          id: n.id,
          label: n.label,
          value: n.value,
          docs: n.docs,
          val: Math.min(20, 4 + n.docs * 1.5),
        })),
        links: graph.edges.map((e) => ({ source: e.source, target: e.target })),
      }
    : { nodes: [], links: [] };

  return (
    <div>
      <PageHeader
        title="Privacy Mosaic"
        subtitle="Cross-document entity graph. Surface form ≠ identity. Embedding-linked aliases visible."
      />

      <div className="px-8 mb-6 flex items-center gap-3">
        <div className="flex items-center gap-2 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg px-3 py-2 flex-1 max-w-md focus-within:border-[var(--accent)]">
          <Search size={14} className="text-[var(--fg-dim)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && lookup()}
            placeholder='Search a person ("Hans Müller", "Tobias Wagner"...)'
            className="flex-1 bg-transparent text-sm focus:outline-none"
          />
        </div>
        <button className="btn btn-primary" onClick={lookup}>Look up</button>
      </div>

      <div className="px-8 grid grid-cols-1 lg:grid-cols-3 gap-4 mb-12">
        <div className="card overflow-hidden lg:col-span-2 relative" style={{ height: "70vh" }}>
          <div className="absolute top-3 left-3 z-10 flex items-center gap-2 text-xs text-[var(--fg-dim)]">
            <Network size={12} />
            <span>
              {graph?.nodes.length ?? 0} nodes · {graph?.edges.length ?? 0} edges
            </span>
          </div>
          {graph && graph.nodes.length > 0 ? (
            <ForceGraph2D
              graphData={data}
              backgroundColor="#0a0a0c"
              nodeRelSize={6}
              nodeColor={(n: any) => LABEL_COLOR[n.label] || "#9aa0a8"}
              linkColor={() => "rgba(154, 160, 168, 0.2)"}
              linkWidth={0.7}
              nodeLabel={(n: any) => `${n.label}\n${n.value}\n${n.docs} docs`}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-[var(--fg-dim)] text-sm">
              {graph ? "No data yet — run a scan first" : "Loading..."}
            </div>
          )}
        </div>

        <div className="card p-5">
          <h3 className="text-xs uppercase tracking-widest text-[var(--fg-dim)] mb-3">Identity panel</h3>
          {err && <div className="text-[var(--bad)] text-sm">{err}</div>}
          {!person && !err && <p className="text-[var(--fg-dim)] text-sm">Search above to inspect a person.</p>}
          {person && (
            <div>
              <div className="text-base font-semibold">{person.display_name}</div>
              <div className="text-xs code text-[var(--fg-dim)] mt-1">{person.canonical}</div>

              <div className="mt-4">
                <span className={`pill pill-${person.re_id_risk}`}>Re-ID risk: {person.re_id_risk}</span>
              </div>

              {person.risk_factors.length > 0 && (
                <ul className="mt-3 flex flex-col gap-1.5 text-xs text-[var(--fg-dim)]">
                  {person.risk_factors.map((f, i) => (
                    <li key={i}>• {f}</li>
                  ))}
                </ul>
              )}

              <div className="mt-4">
                <div className="text-xs text-[var(--fg-dim)] mb-1">Files</div>
                <div className="text-sm font-mono">{person.file_count}</div>
              </div>

              <div className="mt-4 flex flex-col gap-2">
                {Object.entries(person.identifiers).map(([label, values]) => (
                  <div key={label}>
                    <div className="text-[10px] uppercase tracking-widest text-[var(--fg-dim)] mb-1">{label}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {values.slice(0, 6).map((v, i) => (
                        <span key={i} className="kbd">{v}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {person.fuzzy_matches.length > 0 && (
                <div className="mt-5">
                  <div className="text-[10px] uppercase tracking-widest text-[var(--fg-dim)] mb-2">
                    Fuzzy aliases (embeddings)
                  </div>
                  <ul className="flex flex-col gap-1.5 text-sm">
                    {person.fuzzy_matches.map((m, i) => (
                      <li key={i} className="flex items-center justify-between">
                        <span>{m.value}</span>
                        <span className="text-xs font-mono text-[var(--fg-dim)]">{(m.similarity * 100).toFixed(0)}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
