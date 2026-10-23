import type { ReactNode } from "react";
import type { ApiError } from "../lib/api";

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function ErrorBox({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  return (
    <div role="alert" className="card border-danger/40 p-4 text-sm">
      <p className="font-medium text-danger">{error.code === "network_error" ? "Backend unreachable" : "Something went wrong"}</p>
      <p className="mt-1 text-muted">{error.message}</p>
      {onRetry && <button className="btn mt-3" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card p-8 text-center">
      <p className="font-serif text-lg">{title}</p>
      <div className="mt-2 text-sm text-muted max-w-xl mx-auto">{children}</div>
    </div>
  );
}

export function Section({ id, title, subtitle, children, right }: { id: string; title: string; subtitle?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      <div className="flex items-end justify-between gap-4 mb-3">
        <div>
          <h2 className="text-xl">{title}</h2>
          {subtitle && <p className="text-sm text-muted mt-0.5 max-w-3xl">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}
