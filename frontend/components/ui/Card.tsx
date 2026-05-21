import type { ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  dense?: boolean;
}

export function Card({
  title,
  action,
  children,
  className = "",
  bodyClassName = "",
  dense = false,
}: CardProps) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/80 backdrop-blur-sm ${className}`}
    >
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-[var(--color-border-soft)] px-3 py-2">
          <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
            {title}
          </h2>
          {action && <div className="flex items-center gap-2">{action}</div>}
        </header>
      )}
      <div
        className={`flex min-h-0 flex-1 flex-col ${dense ? "" : "p-3"} ${bodyClassName}`}
      >
        {children}
      </div>
    </section>
  );
}
