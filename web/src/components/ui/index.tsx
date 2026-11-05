import { Loader2 } from "lucide-react";
import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-primary text-app hover:bg-primary-hover",
  ghost: "border border-line bg-surface text-ink2 hover:bg-surface2 hover:text-ink",
  danger: "border border-bad/40 bg-bad/10 text-bad hover:bg-bad/20",
};

export function Button({ variant = "primary", loading, className = "", children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button {...rest} disabled={disabled || loading}
      className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-[13px] font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}>
      {loading && <Loader2 size={14} className="animate-spin" />}{children}
    </button>
  );
}

const TONES = { ok: "bg-ok/15 text-ok", warn: "bg-warn/15 text-warn", bad: "bg-bad/15 text-bad", info: "bg-info/15 text-info", mute: "bg-raised text-ink2" };
export function Badge({ tone = "mute", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${TONES[tone]}`}>{children}</span>;
}

export const Card = ({ className = "", children }: { className?: string; children: ReactNode }) =>
  <div className={`rounded-card border border-line bg-surface ${className}`}>{children}</div>;

export function PageHeader({ eyebrow, title, subtitle, actions }: { eyebrow: string; title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1 className="mt-1 text-[26px] font-bold leading-tight tracking-tight sm:text-[30px]">{title}</h1>
        {subtitle && <p className="mt-1 text-ink2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export const Empty = ({ children }: { children: ReactNode }) =>
  <div className="rounded-card border border-dashed border-line px-4 py-10 text-center text-ink2">{children}</div>;

export const Spinner = () => <div className="flex justify-center py-10 text-ink2"><Loader2 className="animate-spin" /></div>;

export const ErrorNote = ({ message, onRetry }: { message: string; onRetry?: () => void }) => (
  <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-bad/40 bg-bad/10 px-4 py-3 text-bad">
    {message}{onRetry && <Button variant="ghost" onClick={onRetry}>Retry</Button>}
  </div>
);

/** Bottom sheet on phones, centred dialog on larger screens. Closes on Escape or backdrop click. */
export function Modal({ open, title, onClose, children, wide }: { open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/60 sm:items-center sm:p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}
        className={`max-h-[92vh] w-full overflow-y-auto rounded-t-2xl border border-line bg-surface p-5 sm:rounded-card ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}>
        <h2 className="mb-4 text-[17px] font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function Confirm({ open, title, body, confirmLabel, onConfirm, onClose }:
  { open: boolean; title: string; body: string; confirmLabel: string; onConfirm: () => void; onClose: () => void }) {
  return (
    <Modal open={open} title={title} onClose={onClose}>
      <p className="mb-5 text-ink2">{body}</p>
      <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="danger" onClick={onConfirm}>{confirmLabel}</Button></div>
    </Modal>
  );
}
