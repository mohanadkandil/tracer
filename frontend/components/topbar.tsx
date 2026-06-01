import { NotificationBell } from "./notification-bell";

export function Topbar() {
  return (
    <div className="h-12 border-b border-[var(--rule)] bg-[var(--paper-elev)] flex items-center justify-end px-4 gap-2">
      <NotificationBell />
    </div>
  );
}
