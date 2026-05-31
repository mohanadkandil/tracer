export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <header className="px-8 pt-8 pb-6 flex items-end justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-[var(--fg-dim)] mt-1">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}
