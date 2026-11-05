import { Send } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Badge, Button, Card } from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import { api } from "../../services/api";
import type { Run } from "../../types";
import { Timeline } from "./ExecutionTimeline";

const SUGGESTIONS = ["Show me red sarees under 5000", "Is COD available?", "What is the return policy?"];

/** Sends a real message through the store's chat pipeline and shows exactly what ran. */
export default function TestPanel({ agentId, disabled, onRun }: { agentId: number; disabled?: boolean; onRun?: () => void }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<Run | null>(null);

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setBusy(true); setRun(null);
    try { setRun(await api.testAgent(agentId, message.trim())); onRun?.(); } catch (e) { toast((e as Error).message, "bad"); } finally { setBusy(false); }
  }
  const submit = (e: FormEvent) => { e.preventDefault(); void send(text); };

  return (
    <div className="space-y-4">
      <p className="rounded-lg border border-line bg-surface2 px-3 py-2 text-ink2">
        Live test: this runs the real store pipeline against your actual products and policies. It is recorded in Executions.
      </p>
      <div className="flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => <button key={s} disabled={busy || disabled} onClick={() => { setText(s); void send(s); }}
          className="rounded-full border border-line px-3 py-1 text-ink2 hover:text-ink disabled:opacity-50">{s}</button>)}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input className="input" aria-label="Test message" placeholder="Type a customer message" value={text} onChange={(e) => setText(e.target.value)} />
        <Button loading={busy} disabled={disabled || !text.trim()} aria-label="Send test"><Send size={15} /></Button>
      </form>
      {disabled && <p className="text-warn">This agent is paused. Resume it to test.</p>}
      {run && (
        <Card className="space-y-4 p-4">
          <div className="flex items-center justify-between gap-2"><span className="font-medium">Execution</span>
            <Badge tone={run.status === "success" ? "ok" : "bad"}>{run.status} · {run.duration_ms} ms</Badge></div>
          <Timeline steps={run.steps} />
          {run.result && <p className="whitespace-pre-wrap rounded-lg bg-surface2 p-3">{run.result}</p>}
          {run.error && <p role="alert" className="text-bad">{run.error}</p>}
          {!!run.products?.length && (
            <ul className="grid gap-2 sm:grid-cols-2">
              {run.products.map((p) => (
                <li key={p.id} className="rounded-lg border border-line p-3">
                  <div className="font-medium">{p.product_name}</div>
                  <div className="text-[12px] text-ink2">{p.brand} · {p.color}</div>
                  <div className="mt-1 flex items-center justify-between"><span>Rs. {p.price.toLocaleString("en-IN")}</span>
                    <Badge tone={p.stock_quantity < 10 ? "warn" : "ok"}>{p.stock_quantity} in stock</Badge></div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
