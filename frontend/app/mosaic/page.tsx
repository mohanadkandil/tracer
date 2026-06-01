"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, type MosaicGraph, type PersonIdentity } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Search, Network, X } from "lucide-react";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

// Editorial palette for nodes — matches DESIGN.md
const LABEL_COLOR: Record<string, string> = {
  PERSON: "#6f6555",
  EMPLOYEE_ID: "#8eaf80",
  EMAIL: "#8aa7c4",
  PHONE: "#d8a648",
  ADDRESS: "#c47a64",
  TAX_ID: "#b04848",
  IBAN: "#b04848",
  USERNAME: "#b59cc8",
  SIGNATURE: "#b08855",
  COMPANY: "#9a8e78",
  DEPARTMENT: "#9a8e78",
};

const LEGEND_ORDER: string[] = ["PERSON", "EMPLOYEE_ID", "EMAIL", "PHONE", "ADDRESS", "TAX_ID", "USERNAME", "SIGNATURE"];

// Focus mode: dim factor for non-cluster nodes/edges
const DIM_OPACITY = 0.08;
const FOCUS_RING_COLOR = "#b9c441"; // citrine

function hexWithAlpha(hex: string, alpha: number): string {
  // Convert #rrggbb → rgba string
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export default function MosaicPage() {
  const [graph, setGraph] = useState<MosaicGraph | null>(null);
  const [query, setQuery] = useState("");
  const [person, setPerson] = useState<PersonIdentity | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<{ name: string; docs: number }[]>([]);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<any>(null);
  const [dims, setDims] = useState({ w: 800, h: 560 });

  useEffect(() => {
    api.graph().then(setGraph).catch((e) => setErr(String(e)));
    api.suggestions(6).then(setSuggestions).catch(() => {});
  }, []);

  async function pick(name: string) {
    setQuery(name);
    setPerson(null);
    setErr(null);
    try {
      const r = await api.person(name);
      setPerson(r);
    } catch (e) {
      setErr(String(e));
    }
  }

  function clearFocus() {
    setPerson(null);
    setQuery("");
    setErr(null);
    // Recenter
    fgRef.current?.zoomToFit?.(400, 60);
  }

  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setDims({ w: Math.max(400, width), h: Math.max(360, height) });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Tune d3 forces once graph data is mounted so nodes spread out
  useEffect(() => {
    if (!graph || !fgRef.current) return;
    const t = setTimeout(() => {
      const fg = fgRef.current;
      if (!fg) return;
      fg.d3Force("charge")?.strength(-90).distanceMax(280);
      fg.d3Force("link")?.distance(45);
      fg.d3ReheatSimulation?.();
    }, 50);
    return () => clearTimeout(t);
  }, [graph]);

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

  // Build the "focused cluster" set: selected canonical + every neighbor (1-hop)
  // plus all edges between members of that set. Anything outside the set is dimmed.
  const focusSet = useMemo(() => {
    if (!person || !graph) return null;
    const focal = person.canonical;
    const neighbors = new Set<string>([focal]);
    const focusEdges = new Set<string>();

    for (const e of graph.edges) {
      const s = typeof e.source === "string" ? e.source : (e.source as any).id;
      const t = typeof e.target === "string" ? e.target : (e.target as any).id;
      if (s === focal || t === focal) {
        neighbors.add(s);
        neighbors.add(t);
        focusEdges.add(`${s}|${t}`);
        focusEdges.add(`${t}|${s}`);
      }
    }
    return { focal, nodes: neighbors, edges: focusEdges };
  }, [person, graph]);

  // When focus changes, center + zoom on the cluster
  useEffect(() => {
    if (!fgRef.current || !graph) return;
    if (!focusSet) {
      const t = setTimeout(() => fgRef.current?.zoomToFit?.(400, 80), 100);
      return () => clearTimeout(t);
    }
    // Wait one frame for d3 to place nodes, then center on focal node
    const t = setTimeout(() => {
      const fg = fgRef.current;
      if (!fg) return;
      const node = (data.nodes as any[]).find((n) => n.id === focusSet.focal);
      if (node && typeof node.x === "number" && typeof node.y === "number") {
        fg.centerAt(node.x, node.y, 800);
        fg.zoom(3.2, 800);
      }
    }, 120);
    return () => clearTimeout(t);
  }, [focusSet, graph]);

  const data = useMemo(() => {
    if (!graph) return { nodes: [], links: [] };
    return {
      nodes: graph.nodes.map((n) => ({
        id: n.id,
        label: n.label,
        value: n.value,
        docs: n.docs,
        val: n.label === "PERSON" ? Math.min(6, 2 + n.docs * 0.25) : Math.min(4, 1.5 + n.docs * 0.2),
      })),
      links: graph.edges.map((e) => ({ source: e.source, target: e.target })),
    };
  }, [graph]);

  return (
    <div>
      <PageHeader
        kicker="Mosaic · 04"
        title="Privacy Mosaic"
        subtitle="Cross-document entity graph. Surface form does not equal identity — fuzzy aliases linked via embedding similarity are visible here."
      />

      <div className="px-10 py-8">
        {/* Search + legend */}
        <div className="flex items-center gap-4 mb-6 flex-wrap">
          <div className="flex items-center gap-2 bg-[var(--paper-card)] border border-[var(--rule)] rounded-md px-3 py-2 flex-1 max-w-md focus-within:border-[var(--rule-strong)] shadow-paper">
            <Search size={14} className="text-[var(--ink-dim)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && lookup()}
              placeholder='Hans Müller, Tobias Wagner, hans@bosch.example'
              className="flex-1 bg-transparent text-[13px] focus:outline-none placeholder:text-[var(--ink-fade)]"
            />
          </div>
          <button className="btn btn-primary" onClick={lookup}>Look up</button>
          {focusSet && (
            <button className="btn btn-ghost" onClick={clearFocus} title="Clear focus">
              <X size={13} /> Clear focus
            </button>
          )}

          {suggestions.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="kicker text-[var(--ink-fade)]">Try:</span>
              {suggestions.slice(0, 5).map((s) => (
                <button
                  key={s.name}
                  onClick={() => pick(s.name)}
                  className="kbd hover:border-[var(--rule-strong)] hover:text-[var(--ink)] transition-colors"
                >
                  {s.name}
                </button>
              ))}
            </div>
          )}

          <div className="ml-auto flex items-center gap-3 flex-wrap">
            {LEGEND_ORDER.map((label) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full" style={{ background: LABEL_COLOR[label] }} />
                <span className="kicker text-[var(--ink-dim)]">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-12">
          <div
            ref={wrapRef}
            className="card lg:col-span-2 relative overflow-hidden bg-[var(--paper-card)]"
            style={{ height: "72vh" }}
          >
            <div className="absolute top-3 left-4 z-10 flex items-center gap-2 text-[11px] font-mono text-[var(--ink-dim)] bg-[var(--paper-card)]/80 px-2 py-1 rounded">
              <Network size={11} />
              <span>
                {graph?.nodes.length ?? 0} nodes · {graph?.edges.length ?? 0} edges
                {focusSet && (
                  <span className="ml-2 text-[var(--ink)]">
                    · focusing {focusSet.nodes.size} of {graph?.nodes.length}
                  </span>
                )}
              </span>
            </div>

            {graph && graph.nodes.length > 0 ? (
              <ForceGraph2D
                ref={fgRef}
                graphData={data}
                width={dims.w}
                height={dims.h}
                backgroundColor="#faf5eb"
                nodeRelSize={3}
                nodeColor={(n: any) => {
                  const base = LABEL_COLOR[n.label] || "#6f6555";
                  if (!focusSet) return base;
                  if (focusSet.nodes.has(n.id)) return base;
                  return hexWithAlpha(base, DIM_OPACITY);
                }}
                linkColor={(l: any) => {
                  const s = typeof l.source === "string" ? l.source : l.source?.id;
                  const t = typeof l.target === "string" ? l.target : l.target?.id;
                  if (!focusSet) return "rgba(42, 38, 32, 0.14)";
                  if (focusSet.edges.has(`${s}|${t}`)) return "rgba(42, 38, 32, 0.45)";
                  return "rgba(42, 38, 32, 0.04)";
                }}
                linkWidth={(l: any) => {
                  if (!focusSet) return 0.5;
                  const s = typeof l.source === "string" ? l.source : l.source?.id;
                  const t = typeof l.target === "string" ? l.target : l.target?.id;
                  return focusSet.edges.has(`${s}|${t}`) ? 1.2 : 0.3;
                }}
                nodeLabel={(n: any) => `${n.label} · ${n.value} · ${n.docs} docs`}
                cooldownTicks={240}
                d3AlphaDecay={0.012}
                d3VelocityDecay={0.45}
                onNodeClick={(n: any) => {
                  if (n.label === "PERSON") pick(n.value);
                }}
                nodeCanvasObjectMode={() => "after"}
                nodeCanvasObject={(node: any, ctx, scale) => {
                  // Focal ring on selected person
                  if (focusSet && node.id === focusSet.focal) {
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, node.val + 5 / scale, 0, 2 * Math.PI);
                    ctx.strokeStyle = FOCUS_RING_COLOR;
                    ctx.lineWidth = 2 / scale;
                    ctx.stroke();
                  }
                  // Labels: always on focused cluster, otherwise only on zoom
                  const inFocus = focusSet?.nodes.has(node.id);
                  const showLabel = inFocus || (scale >= 1.4 && node.val >= 4);
                  if (!showLabel) return;
                  ctx.font = `${10 / scale}px Geist, -apple-system, sans-serif`;
                  ctx.fillStyle = inFocus ? "#2a2620" : "rgba(42, 38, 32, 0.5)";
                  ctx.textAlign = "left";
                  ctx.textBaseline = "middle";
                  const txt = (node.value || "").length > 24 ? node.value.slice(0, 24) + "…" : node.value;
                  ctx.fillText(txt, node.x + node.val + 4 / scale, node.y);
                }}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-[var(--ink-dim)] text-[13px] gap-2">
                {graph ? (
                  <>
                    <Network size={28} className="text-[var(--ink-fade)]" />
                    <p>No mosaic data yet.</p>
                    <p className="text-[11px] text-[var(--ink-fade)]">
                      Run a scan from <span className="kbd">Live Scan</span> to populate the graph.
                    </p>
                  </>
                ) : (
                  <p>Loading...</p>
                )}
              </div>
            )}
          </div>

          {/* Identity panel */}
          <div className="card p-6 self-start">
            <div className="kicker mb-4">Identity Panel</div>
            {err && <div className="text-[var(--oxblood)] text-[13px]">{err}</div>}
            {!person && !err && (
              <p className="text-[var(--ink-dim)] text-[13px] leading-relaxed">
                Search a name or <span className="text-[var(--ink)]">click a PERSON node</span> in the graph. The selected cluster will highlight while everything else dims.
              </p>
            )}
            {person && (
              <div>
                <div className="display-md text-[var(--ink)] leading-none">{person.display_name}</div>
                <div className="code text-[var(--ink-dim)] mt-2 text-[11px]">{person.canonical}</div>

                <div className="mt-5 flex items-center gap-3">
                  <span className={`pill pill-${person.re_id_risk}`}>Re-ID · {person.re_id_risk}</span>
                  <span className="text-[11px] text-[var(--ink-dim)] font-mono">{person.file_count} files</span>
                </div>

                {person.risk_factors.length > 0 && (
                  <div className="mt-4 pl-3 border-l-2 border-[var(--copper)]">
                    {person.risk_factors.map((f, i) => (
                      <p key={i} className="text-[12px] text-[var(--ink-dim)] leading-relaxed mb-1">{f}</p>
                    ))}
                  </div>
                )}

                <div className="mt-6 flex flex-col gap-4">
                  {Object.entries(person.identifiers).map(([label, values]) => (
                    <div key={label}>
                      <div className="kicker mb-1.5">{label}</div>
                      <div className="flex flex-wrap gap-1.5">
                        {values.slice(0, 8).map((v, i) => (
                          <span key={i} className="kbd">{v}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                {person.fuzzy_matches.length > 0 && (
                  <div className="mt-6 pt-4 border-t border-[var(--rule)]">
                    <div className="kicker mb-2">Fuzzy Aliases · Embedding</div>
                    <ul className="flex flex-col">
                      {person.fuzzy_matches.map((m, i) => (
                        <li key={i} className="flex items-center justify-between py-1.5 text-[13px]">
                          <span className="code">{m.value}</span>
                          <span className="font-mono text-[10.5px] text-[var(--ink-dim)]">
                            {(m.similarity * 100).toFixed(0)}%
                          </span>
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
    </div>
  );
}
