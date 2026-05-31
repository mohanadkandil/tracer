"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { Play, Square, Cloud, HardDrive } from "lucide-react";

type ProgressEvent = {
  scanned: number;
  deduped: number;
  findings: number;
  current: string;
  owner?: string;
  spans?: number;
  elapsed_ms?: number;
  cached?: boolean;
};

export default function LiveScanPage() {
  const [source, setSource] = useState<"filesystem" | "sharepoint">("sharepoint");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [done, setDone] = useState<ProgressEvent | null>(null);
  const [ticker, setTicker] = useState<{ path: string; spans: number; cached: boolean; owner?: string }[]>([]);
  const esRef = useRef<EventSource | null>(null);

  function start() {
    setRunning(true);
    setDone(null);
    setProgress(null);
    setTicker([]);
    const es = api.scanStreamEventSource(source);
    esRef.current = es;
    es.addEventListener("progress", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as ProgressEvent;
      setProgress(data);
      setTicker((t) =>
        [{ path: data.current, spans: data.spans ?? 0, cached: !!data.cached, owner: data.owner }, ...t].slice(0, 25),
      );
    });
    es.addEventListener("done", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as ProgressEvent;
      setDone(data);
      setRunning(false);
      es.close();
    });
    es.onerror = () => {
      setRunning(false);
      es.close();
    };
  }

  function stop() {
    esRef.current?.close();
    setRunning(false);
  }

  useEffect(() => {
    return () => esRef.current?.close();
  }, []);

  const totalScanned = progress?.scanned ?? done?.scanned ?? 0;
  const totalDeduped = progress?.deduped ?? done?.deduped ?? 0;
  const totalFindings = progress?.findings ?? done?.findings ?? 0;
  const elapsed = ((progress?.elapsed_ms ?? done?.elapsed_ms ?? 0) / 1000).toFixed(1);
  const rate = totalScanned > 0 && parseFloat(elapsed) > 0 ? (totalScanned / parseFloat(elapsed)).toFixed(1) : "0";

  return (
    <div>
      <PageHeader
        title="Live Scan"
        subtitle="Discovery → dedup → tiered routing → mosaic linking. Streamed via SSE."
        action={
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-[var(--bg-card)] border border-[var(--border)] rounded-lg overflow-hidden">
              <button
                disabled={running}
                onClick={() => setSource("sharepoint")}
                className={`px-3 py-2 text-xs flex items-center gap-1.5 ${
                  source === "sharepoint" ? "bg-[var(--bg-elev)] text-[var(--fg)]" : "text-[var(--fg-dim)]"
                }`}
              >
                <Cloud size={13} /> SharePoint
              </button>
              <button
                disabled={running}
                onClick={() => setSource("filesystem")}
                className={`px-3 py-2 text-xs flex items-center gap-1.5 ${
                  source === "filesystem" ? "bg-[var(--bg-elev)] text-[var(--fg)]" : "text-[var(--fg-dim)]"
                }`}
              >
                <HardDrive size={13} /> Filesystem
              </button>
            </div>
            {running ? (
              <button className="btn" onClick={stop}>
                <Square size={14} /> Stop
              </button>
            ) : (
              <button className="btn btn-primary" onClick={start}>
                <Play size={14} /> Start scan
              </button>
            )}
          </div>
        }
      />

      <div className="px-8 grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <Stat label="Scanned" value={totalScanned} mono />
        <Stat label="Deduped (cache)" value={totalDeduped} mono accent="good" />
        <Stat label="Findings" value={totalFindings} mono accent="warn" />
        <Stat label="Elapsed" value={`${elapsed}s`} mono />
        <Stat label="Rate" value={`${rate}/s`} mono accent="good" />
      </div>

      <div className="px-8 grid grid-cols-1 lg:grid-cols-2 gap-4 mb-12">
        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            Now scanning
          </h3>
          {!progress && !done && (
            <p className="text-[var(--fg-dim)] text-sm">
              Idle. Click <span className="text-[var(--fg)]">Start scan</span> to walk{" "}
              <span className="kbd">data/files/</span>.
            </p>
          )}
          {progress && (
            <div>
              <div className="text-sm code text-[var(--fg)] break-all">{progress.current}</div>
              {progress.owner && (
                <div className="text-xs text-[var(--fg-dim)] mt-1">owner: {progress.owner}</div>
              )}
              <div className="mt-3 h-1.5 rounded-full bg-[var(--bg-elev)] overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[var(--accent)] to-[var(--accent-2)] transition-all duration-300"
                  style={{ width: `${Math.min(100, totalScanned / 5)}%` }}
                />
              </div>
            </div>
          )}
          {done && (
            <div className="mt-2 text-sm text-[var(--good)]">
              ✓ Done. {done.scanned} files in {(done.elapsed_ms! / 1000).toFixed(1)}s.
            </div>
          )}
        </div>

        <div className="card p-5">
          <h3 className="text-sm font-semibold mb-4 text-[var(--fg-dim)] uppercase tracking-widest">
            Recent files
          </h3>
          <div className="flex flex-col gap-1.5 max-h-80 overflow-y-auto">
            {ticker.length === 0 && <p className="text-[var(--fg-dim)] text-sm">Waiting...</p>}
            {ticker.map((row, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    row.cached ? "bg-[var(--fg-dim)]" : row.spans > 0 ? "bg-[var(--warn)]" : "bg-[var(--good)]"
                  }`}
                />
                <span className="code text-[var(--fg)] flex-1 truncate">{row.path}</span>
                {row.cached ? (
                  <span className="kbd">cache</span>
                ) : (
                  <span className="text-[var(--fg-dim)] font-mono">{row.spans}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, mono, accent }: { label: string; value: string | number; mono?: boolean; accent?: "good" | "warn" }) {
  const color = accent === "good" ? "text-[var(--good)]" : accent === "warn" ? "text-[var(--warn)]" : "text-[var(--fg)]";
  return (
    <div className="card p-4">
      <div className="text-[10px] uppercase tracking-widest text-[var(--fg-dim)] mb-2">{label}</div>
      <div className={`text-xl ${mono ? "font-mono" : "font-semibold"} ${color}`}>{value}</div>
    </div>
  );
}
