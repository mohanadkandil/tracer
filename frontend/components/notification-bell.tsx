"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Bell, ShieldCheck, ShieldAlert, Inbox } from "lucide-react";
import clsx from "clsx";
import { api, type NotificationItem } from "@/lib/api";

export function NotificationBell() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [open, setOpen] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.notifications(false, 30).then(setItems).catch(() => {});

    const es = api.notificationStream();
    esRef.current = es;
    es.addEventListener("notification", (e) => {
      const item = JSON.parse((e as MessageEvent).data) as NotificationItem;
      setItems((prev) => {
        if (prev.find((p) => p.id === item.id)) return prev;
        return [item, ...prev].slice(0, 50);
      });
    });
    es.onerror = () => { /* let browser auto-reconnect */ };
    return () => es.close();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const unseen = items.filter((i) => !i.seen).length;

  return (
    <div className="relative" ref={panelRef}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative w-9 h-9 rounded-md hover:bg-[var(--paper-card)] flex items-center justify-center transition-colors"
        title="Notifications"
      >
        <Bell size={16} strokeWidth={1.6} className="text-[var(--ink-dim)]" />
        {unseen > 0 && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[var(--citrine)] pulse-dot" />
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-[380px] card overflow-hidden shadow-paper z-50"
          style={{ maxHeight: "70vh" }}
        >
          <div className="px-4 py-3 border-b border-[var(--rule)] flex items-center justify-between">
            <div className="kicker">Notifications {unseen > 0 && <span className="text-[var(--ink)] ml-1">· {unseen} new</span>}</div>
            <Link
              href="/dsar"
              onClick={() => setOpen(false)}
              className="text-[11px] text-[var(--ink-dim)] hover:text-[var(--ink)]"
            >
              View all
            </Link>
          </div>

          <div className="overflow-y-auto" style={{ maxHeight: "60vh" }}>
            {items.length === 0 && (
              <div className="px-4 py-10 text-center">
                <Inbox size={20} className="mx-auto text-[var(--ink-fade)] mb-2" />
                <p className="text-[12px] text-[var(--ink-dim)]">No notifications yet</p>
              </div>
            )}
            {items.map((n) => (
              <NotificationRow key={n.id} n={n} onClose={() => setOpen(false)} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NotificationRow({ n, onClose }: { n: NotificationItem; onClose: () => void }) {
  const icon =
    n.kind === "dsar_new" ? <ShieldAlert size={14} className="text-[var(--copper)]" /> :
    n.kind === "dsar_executed" ? <ShieldCheck size={14} className="text-[var(--sage)]" /> :
    <Inbox size={14} className="text-[var(--ink-dim)]" />;

  const content = (
    <div
      className={clsx(
        "px-4 py-3 border-b border-[var(--rule)] last:border-0 flex gap-3 group cursor-pointer",
        !n.seen ? "bg-[var(--paper-aged)]/40" : "hover:bg-[var(--paper-aged)]/30",
      )}
    >
      <div className="mt-0.5 shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="text-[13px] text-[var(--ink)] leading-snug font-medium">{n.title}</div>
        {n.body && (
          <div className="text-[11.5px] text-[var(--ink-dim)] mt-1 whitespace-pre-line leading-relaxed">
            {n.body.replace(/\*([^*]+)\*/g, "$1")}
          </div>
        )}
        <div className="text-[10px] text-[var(--ink-fade)] font-mono mt-1.5">
          {new Date(n.created_at).toLocaleTimeString()}
        </div>
      </div>
      {!n.seen && <span className="w-1.5 h-1.5 rounded-full bg-[var(--citrine)] mt-1.5 shrink-0" />}
    </div>
  );

  if (n.target_url) {
    let path = n.target_url;
    try { path = new URL(n.target_url).pathname; } catch {}
    return (
      <Link
        href={path}
        onClick={() => {
          api.notificationSeen(n.id).catch(() => {});
          onClose();
        }}
      >
        {content}
      </Link>
    );
  }
  return content;
}
