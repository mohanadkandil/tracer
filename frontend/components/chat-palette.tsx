"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, Search, FileText, X, Cpu, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

type Source = { file_path: string; score: number; preview: string };
type Health = { provider: string; chunks_indexed: number } | null;

export function ChatPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [health, setHealth] = useState<Health>(null);
  const esRef = useRef<EventSource | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const answerEndRef = useRef<HTMLDivElement | null>(null);

  // Keyboard shortcut: ⌘K / Ctrl-K
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape" && open) {
        setOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Load suggestions + health when opened
  useEffect(() => {
    if (!open) return;
    api.chatSuggestions().then(setSuggestions).catch(() => {});
    api.chatHealth().then(setHealth).catch(() => setHealth(null));
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [open]);

  // Auto-scroll on streaming
  useEffect(() => {
    answerEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [answer]);

  const close = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
    setOpen(false);
    setStreaming(false);
  }, []);

  const reset = () => {
    esRef.current?.close();
    esRef.current = null;
    setAnswer("");
    setSources([]);
    setSubmitted(null);
    setStreaming(false);
  };

  function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed) return;
    reset();
    setSubmitted(trimmed);
    setStreaming(true);
    const es = api.chatStream(trimmed);
    esRef.current = es;
    es.addEventListener("sources", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setSources(d.sources || []);
    });
    es.addEventListener("token", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setAnswer((a) => a + (d.text || ""));
    });
    es.addEventListener("done", () => {
      setStreaming(false);
      es.close();
    });
    es.onerror = () => {
      setStreaming(false);
      es.close();
    };
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh] px-4">
      {/* backdrop */}
      <div
        className="absolute inset-0 bg-[#1a1815]/40 backdrop-blur-sm"
        onClick={close}
      />

      {/* panel */}
      <div className="relative w-full max-w-[720px] card shadow-paper overflow-hidden flex flex-col"
           style={{ maxHeight: "76vh" }}>
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--rule)]">
          <Search size={16} className="text-[var(--ink-dim)]" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run(query)}
            placeholder='Ask about your data — "who is at highest risk?", "where does Hans Müller appear?"'
            className="flex-1 bg-transparent text-[14px] focus:outline-none placeholder:text-[var(--ink-fade)]"
          />
          <button onClick={close} className="text-[var(--ink-dim)] hover:text-[var(--ink)]" title="Close (Esc)">
            <X size={14} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {!submitted ? (
            <SuggestionsView
              suggestions={suggestions}
              onPick={(q) => { setQuery(q); run(q); }}
              health={health}
            />
          ) : (
            <AnswerView
              query={submitted}
              answer={answer}
              sources={sources}
              streaming={streaming}
              answerEndRef={answerEndRef}
              onReset={() => { setQuery(""); reset(); }}
            />
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-[var(--rule)] flex items-center justify-between text-[10px] text-[var(--ink-fade)] font-mono">
          <div className="flex items-center gap-3">
            <span><span className="kbd">↵</span> run</span>
            <span><span className="kbd">esc</span> close</span>
            <span><span className="kbd">⌘K</span> toggle</span>
          </div>
          {health && (
            <div className="flex items-center gap-1.5">
              <Cpu size={10} />
              <span>{health.provider} · {health.chunks_indexed} chunks indexed</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SuggestionsView({
  suggestions,
  onPick,
  health,
}: {
  suggestions: string[];
  onPick: (q: string) => void;
  health: Health;
}) {
  return (
    <div className="px-4 py-4 flex flex-col gap-4">
      <div>
        <div className="kicker mb-2">Suggested</div>
        <div className="flex flex-col">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => onPick(s)}
              className={`flex items-center gap-2 px-2 py-2 rounded-md text-[13px] text-left text-[var(--ink)] hover:bg-[var(--paper-aged)]/60 transition-colors ${
                i > 0 ? "border-t border-[var(--rule)]" : ""
              }`}
            >
              <Sparkles size={12} className="text-[var(--citrine)] shrink-0" />
              <span>{s}</span>
            </button>
          ))}
          {suggestions.length === 0 && (
            <p className="text-[12px] text-[var(--ink-dim)] py-3">Loading suggestions…</p>
          )}
        </div>
      </div>

      {(!health || health.chunks_indexed === 0) && (
        <div className="border-l-2 border-[var(--amber)] pl-3 py-1">
          <p className="text-[12px] text-[var(--ink-dim)] leading-relaxed">
            No chunks indexed yet. Run a scan from <span className="kbd">Live Scan</span> to make chat answers useful.
          </p>
        </div>
      )}
    </div>
  );
}

function AnswerView({
  query,
  answer,
  sources,
  streaming,
  answerEndRef,
  onReset,
}: {
  query: string;
  answer: string;
  sources: Source[];
  streaming: boolean;
  answerEndRef: React.RefObject<HTMLDivElement | null>;
  onReset: () => void;
}) {
  return (
    <div className="px-4 py-4">
      <div className="kicker mb-2">Question</div>
      <div className="text-[14px] text-[var(--ink)] mb-4">{query}</div>

      <div className="kicker mb-2 flex items-center gap-2">
        Answer {streaming && <Loader2 size={11} className="animate-spin text-[var(--citrine)]" />}
      </div>
      <div className="text-[13.5px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap mb-1">
        {answer || (streaming ? <span className="text-[var(--ink-fade)]">Thinking…</span> : "")}
      </div>
      <div ref={answerEndRef} />

      {sources.length > 0 && (
        <div className="mt-5">
          <div className="kicker mb-2">Sources</div>
          <div className="flex flex-col gap-1.5">
            {sources.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-[12px]">
                <FileText size={12} className="text-[var(--ink-dim)] shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="code text-[var(--ink)] break-all">{s.file_path}</div>
                  <div className="text-[11px] text-[var(--ink-dim)] mt-0.5 line-clamp-2">
                    {s.preview}
                  </div>
                </div>
                <span className="font-mono text-[10px] text-[var(--ink-dim)] shrink-0">
                  {(s.score * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 pt-3 border-t border-[var(--rule)]">
        <button onClick={onReset} className="text-[11px] text-[var(--ink-dim)] hover:text-[var(--ink)] font-mono">
          ← Ask another question
        </button>
      </div>
    </div>
  );
}
