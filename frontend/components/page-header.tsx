export function PageHeader({
  kicker,
  title,
  subtitle,
  action,
}: {
  kicker?: string;
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="px-10 pt-10 pb-8 flex items-end justify-between border-b border-[var(--rule)]">
      <div>
        {kicker && <div className="kicker mb-3">{kicker}</div>}
        <h1 className="display-lg text-[var(--ink)]">{title}</h1>
        {subtitle && (
          <p className="text-[13.5px] text-[var(--ink-dim)] mt-3 max-w-2xl leading-relaxed">{subtitle}</p>
        )}
      </div>
      {action}
    </header>
  );
}
