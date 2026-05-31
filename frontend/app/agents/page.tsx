"use client";

import { useEffect, useState } from "react";
import { api, type Agent } from "@/lib/api";
import { PageHeader } from "@/components/page-header";
import { ThumbsUp } from "lucide-react";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    api.agents().then(setAgents);
  }, []);

  async function endorse(id: string) {
    const updated = await api.endorseAgent(id);
    setAgents((prev) => prev.map((a) => (a.id === id ? updated : a)));
  }

  return (
    <div>
      <PageHeader
        title="Agent Registry"
        subtitle="Each capability is a versioned, endorsable artifact. Platform, not script."
      />

      <div className="px-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-12">
        {agents.map((a) => (
          <div key={a.id} className="card p-5 flex flex-col">
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="font-semibold">{a.name}</div>
                <div className="text-[11px] text-[var(--fg-dim)] font-mono">v{a.version} · {a.domain}</div>
              </div>
              <button
                onClick={() => endorse(a.id)}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs bg-[var(--bg-elev)] hover:bg-[var(--accent)] hover:text-[var(--bg)] transition-colors"
              >
                <ThumbsUp size={12} /> {a.endorsements}
              </button>
            </div>
            <p className="text-sm text-[var(--fg-dim)] leading-relaxed mb-4 flex-1">{a.description}</p>

            <div className="grid grid-cols-2 gap-3 text-[10px]">
              <div>
                <div className="uppercase tracking-widest text-[var(--fg-dim)] mb-1">Tools</div>
                <div className="flex flex-wrap gap-1">
                  {a.tools.map((t) => (
                    <span key={t} className="kbd">{t}</span>
                  ))}
                </div>
              </div>
              <div>
                <div className="uppercase tracking-widest text-[var(--fg-dim)] mb-1">I/O</div>
                <div className="text-[var(--fg-dim)] code">
                  {a.inputs.join(", ")} → {a.outputs.join(", ")}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
