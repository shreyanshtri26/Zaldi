import { CheckCircle2, ChevronDown, CircleAlert, Loader2 } from "lucide-react";
import { useState } from "react";
import { Badge } from "../../components/ui";
import type { Run, RunStep } from "../../types";

const icon = (s: RunStep["status"]) =>
  s === "done" ? <CheckCircle2 size={15} className="text-ok" />
    : s === "failed" ? <CircleAlert size={15} className="text-bad" />
      : <Loader2 size={15} className="animate-spin text-primary" />;

/** User-facing progress only: what the agent did, which tool ran and how long it took. */
export function Timeline({ steps }: { steps: RunStep[] }) {
  return (
    <ol className="space-y-2">
      {steps.map((s, i) => (
        <li key={i} className="flex items-start gap-2.5">
          <span className="mt-0.5">{icon(s.status)}</span>
          <span>
            {s.label}
            {s.tool && <span className="ml-2 rounded bg-raised px-1.5 py-0.5 font-mono text-[11px] text-ink2">{s.tool}</span>}
            {s.detail && <span className="block text-[12px] text-ink2">{s.detail}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

export const when = (iso: string | null) => (iso ? new Date(iso.replace(" ", "T") + "Z").toLocaleString() : "Never");

export function RunCard({ run, showAgent }: { run: Run; showAgent?: boolean }) {
  const [open, setOpen] = useState(false);
  const tone = run.status === "success" ? "ok" : run.status === "failed" ? "bad" : "warn";
  return (
    <div className="rounded-card border border-line bg-surface">
      <button className="flex w-full items-center gap-3 p-3.5 text-left" aria-expanded={open} onClick={() => setOpen(!open)}>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium">{run.input}</div>
          <div className="mt-0.5 text-[12px] text-ink2">{showAgent && run.agent_name ? `${run.agent_name} · ` : ""}{when(run.created_at)} · {run.duration_ms} ms</div>
        </div>
        <Badge tone={tone}>{run.status.replace("_", " ")}</Badge>
        <ChevronDown size={16} className={`shrink-0 text-ink2 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-4 border-t border-line p-3.5">
          <Timeline steps={run.steps} />
          {run.result && <div><div className="label">Result</div><p className="whitespace-pre-wrap rounded-lg bg-surface2 p-3">{run.result}</p></div>}
          {run.error && <p role="alert" className="text-bad">Error: {run.error}</p>}
          <div className="text-[12px] text-mute">Trigger: {run.trigger_} · Run #{run.id}</div>
        </div>
      )}
    </div>
  );
}
