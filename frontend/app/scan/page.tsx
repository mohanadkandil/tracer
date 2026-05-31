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
        [{ path: data.current, spans: data.spans ?? 0, cached: !!data.cached, owner: data.owner }, ...t].slice(0, 30),
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

  useEffect(() => () => esRef.current?.close(), []);

  const totalScanned = progress?.scanned ?? done?.scanned ?? 0;
  const totalDeduped = progress?.deduped ?? done?.deduped ?? 0;
  const totalFindings = progress?.findings ?? done?.findings ?? 0;
  const elapsed = ((progress?.elapsed_ms ?? done?.elapsed_ms ?? 0) / 1000).toFixed(1);
  const rate = totalScanned > 0 && parseFloat(elapsed) > 0 ? (totalScanned / parseFloat(elapsed)).toFixed(1) : "0";

  return (
    <div>
      <PageHeader
        kicker="Live Scan · 02"
        title="Discovery Stream"
        subtitle="Discovery → dedup → tiered routing → mosaic linking. Streamed via Server-Sent Events."
        action={
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-[var(--paper-card)] border border-[var(--rule)] rounded-md overflow-hidden">
              <button
                disabled={running}
                onClick={() => setSource("sharepoint")}
                className={`px-3 py-2 text-[11px] flex items-center gap-1.5 font-mono tracking-wide ${
                  source === "sharepoint" ? "bg-[var(--paper-elev)] text-[var(--ink)]" : "text-[var(--ink-dim)]"
                }`}
              >
                <Cloud size={11} /> SHAREPOINT
              </button>
              <button
                disabled={running}
                onClick={() => setSource("filesystem")}
                className={`px-3 py-2 text-[11px] flex items-center gap-1.5 font-mono tracking-wide ${
                  source === "filesystem" ? "bg-[var(--paper-elev)] text-[var(--ink)]" : "text-[var(--ink-dim)]"
                }`}
              >
                <HardDrive size={11} /> FILESYSTEM
              </button>
            </div>
            {running ? (
              <button className="btn" onClick={stop}>
                <Square size={13} /> Stop
              </button>
            ) : (
              <button className="btn btn-primary" onClick={start}>
                <Play size={13} /> Start scan
              </button>
            )}
          </div>
        }
      />

      <div className="px-10 py-8">
        {/* Stat strip */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-6 mb-10 border-y border-[var(--rule)] py-6">
          <Stat label="Scanned" value={totalScanned} />
          <Stat label="Deduped" value={totalDeduped} tone="sage" hint="cache hits" />
          <Stat label="Findings" value={totalFindings} tone="amber" />
          <Stat label="Elapsed" value={`${elapsed}s`} />
          <Stat label="Rate" value={`${rate}/s`} tone="citrine" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 mb-12">
          <section className="lg:col-span-2">
            <div className="kicker mb-3">Currently</div>
            {!progress && !done && (
              <p className="text-[13px] text-[var(--ink-dim)]">
                Idle. Press <span className="kbd">Start scan</span> to walk <span className="code">data/files/</span>.
              </p>
            )}
            {progress && (
              <div className="flex flex-col gap-3">
                <div className="font-display text-[22px] text-[var(--ink)] break-all leading-snug">
                  {progress.current.split("/").slice(-2).join("/")}
                </div>
                {progress.owner && (
                  <div className="kicker text-[var(--ink-dim)]">
                    owner · <span className="code text-[var(--ink)] normal-case tracking-normal">{progress.owner}</span>
                  </div>
                )}
                <div className="mt-2 h-[2px] bg-[var(--paper-card)] overflow-hidden">
                  <div
                    className="h-full bg-[var(--citrine)] transition-all duration-300"
                    style={{ width: `${Math.min(100, totalScanned / 5)}%` }}
                  />
                </div>
                <div className="kicker text-[var(--ink-fade)] mt-1">
                  step {totalScanned.toString().padStart(4, "0")}
                </div>
              </div>
            )}
            {done && !progress?.scanned && (
              <div className="mt-2 text-[13px] text-[var(--sage)] flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[var(--sage)]" />
                Done. {done.scanned} files · {(done.elapsed_ms! / 1000).toFixed(1)}s.
              </div>
            )}
          </section>

          <section className="lg:col-span-3 border-l border-[var(--rule)] pl-8">
            <div className="kicker mb-3">Ticker</div>
            <div className="flex flex-col max-h-[64vh] overflow-y-auto">
              {ticker.length === 0 && <p className="text-[12px] text-[var(--ink-dim)]">Waiting...</p>}
              {ticker.map((row, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 py-1.5 text-[12px] data-in ${
                    i < ticker.length - 1 ? "border-b border-[var(--rule)]" : ""
                  }`}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{
                      background: row.cached
                        ? "var(--ink-fade)"
                        : row.spans > 0
                          ? "var(--amber)"
                          : "var(--sage)",
                    }}
                  />
                  <span className="code text-[var(--ink)] flex-1 truncate">{row.path}</span>
                  {row.owner && <span className="font-mono text-[10px] text-[var(--ink-fade)] truncate max-w-[140px]">{row.owner}</span>}
                  {row.cached ? (
                    <span className="kbd">cache</span>
                  ) : (
                    <span className="text-[var(--ink-dim)] font-mono text-[11px]">{row.spans}</span>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone, hint }: { label: string; value: string | number; tone?: "sage" | "amber" | "citrine"; hint?: string }) {
  const color = tone === "sage" ? "text-[var(--sage)]" : tone === "amber" ? "text-[var(--amber)]" : tone === "citrine" ? "text-[var(--citrine)]" : "text-[var(--ink)]";
  return (
    <div>
      <div className="meta mb-2">{label}</div>
      <div className={`font-mono text-[28px] leading-none ${color}`}>{value}</div>
      {hint && <div className="text-[10px] text-[var(--ink-fade)] mt-1 tracking-wide uppercase">{hint}</div>}
    </div>
  );
}
