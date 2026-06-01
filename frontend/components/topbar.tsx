"use client";

import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { NotificationBell } from "./notification-bell";
import { ChatPalette } from "./chat-palette";

export function Topbar() {
  const [mac, setMac] = useState(true);
  useEffect(() => {
    if (typeof navigator !== "undefined") {
      setMac(/Mac|iPod|iPhone|iPad/.test(navigator.platform || navigator.userAgent));
    }
  }, []);

  function openPalette() {
    window.dispatchEvent(new KeyboardEvent("keydown", {
      key: "k", metaKey: mac, ctrlKey: !mac, bubbles: true,
    }));
  }

  return (
    <>
      <div className="h-12 border-b border-[var(--rule)] bg-[var(--paper-elev)] flex items-center justify-end px-4 gap-3">
        <button
          onClick={openPalette}
          className="flex items-center gap-2 px-3 py-1.5 bg-[var(--paper-card)] hover:bg-[var(--paper-aged)] border border-[var(--rule)] rounded-md text-[12px] text-[var(--ink-dim)] transition-colors"
          title="Ask Forgetter (⌘K)"
        >
          <Sparkles size={13} className="text-[var(--citrine)]" />
          <span>Ask Forgetter</span>
          <span className="kbd">{mac ? "⌘K" : "Ctrl K"}</span>
        </button>
        <NotificationBell />
      </div>
      <ChatPalette />
    </>
  );
}
