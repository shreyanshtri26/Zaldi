import { Copy, FlaskConical, Pause, Play, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Card, Confirm, Empty, ErrorNote, PageHeader, Spinner } from "../../components/ui";
import { ICONS, STATUS_TONE } from "../../data/options";
import { useAsync } from "../../hooks/useAsync";
import { useToast } from "../../hooks/useToast";
import { api } from "../../services/api";
import type { Agent } from "../../types";
import ApprovalsPanel from "./ApprovalsPanel";
import { RunCard, when } from "./ExecutionTimeline";

function AgentCard({ a, onChange }: { a: Agent; onChange: () => void }) {
  const toast = useToast();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const Icon = ICONS[a.icon] ?? ICONS.bot;

  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); toast(ok); onChange(); } catch (e) { toast((e as Error).message, "bad"); }
  }
  const paused = a.status === "paused";
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-primary/12 text-primary"><Icon size={19} /></span>
        <div className="min-w-0 flex-1">
          <Link to={`/agents/${a.id}`} className="block truncate font-semibold hover:text-primary">{a.name}</Link>
          <p className="mt-0.5 line-clamp-2 text-ink2">{a.description}</p>
        </div>
        <Badge tone={STATUS_TONE[a.status]}>{a.status}</Badge>
      </div>
      <dl className="grid grid-cols-3 gap-2 border-t border-line pt-3 text-[12px]">
        <div><dt className="text-mute">Executions</dt><dd className="font-medium">{a.executions}</dd></div>
        <div><dt className="text-mute">Success</dt><dd className="font-medium">{a.success_rate === null ? "-" : `${a.success_rate}%`}</dd></div>
        <div><dt className="text-mute">Model</dt><dd className="font-medium capitalize">{a.model}</dd></div>
        <div className="col-span-3"><dt className="text-mute">Last activity</dt><dd>{when(a.last_activity)}</dd></div>
      </dl>
      <div className="flex flex-wrap gap-1.5">
        <Link to={`/agents/${a.id}`} className="inline-flex h-8 items-center rounded-lg bg-primary px-3 text-[12px] font-medium text-app hover:bg-primary-hover">Open</Link>
        <Link to={`/agents/${a.id}?tab=testing`} className="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-[12px] text-ink2 hover:text-ink"><FlaskConical size={13} />Test</Link>
        <button className="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-3 text-[12px] text-ink2 hover:text-ink"
          onClick={() => act(() => api.updateAgent(a.id, { status: paused ? "active" : "paused" }), paused ? "Agent resumed" : "Agent paused")}>
          {paused ? <Play size={13} /> : <Pause size={13} />}{paused ? "Resume" : "Pause"}</button>
        <button aria-label={`Duplicate ${a.name}`} className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink2 hover:text-ink"
          onClick={() => act(() => api.duplicateAgent(a.id), "Agent duplicated as a draft")}><Copy size={13} /></button>
        <button aria-label={`Delete ${a.name}`} className="grid h-8 w-8 place-items-center rounded-lg border border-line text-ink2 hover:text-bad"
          onClick={() => setConfirmDelete(true)}><Trash2 size={13} /></button>
      </div>
      <Confirm open={confirmDelete} title={`Delete ${a.name}?`} body="Its settings and execution history are removed. This cannot be undone." confirmLabel="Delete agent"
        onClose={() => setConfirmDelete(false)} onConfirm={() => { setConfirmDelete(false); void act(() => api.deleteAgent(a.id), "Agent deleted"); }} />
    </Card>
  );
}

function AgentList() {
  const { data, error, loading, reload } = useAsync(() => api.agents());
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!data?.length) return <Empty>No agents yet. Create your first one.</Empty>;
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{data.map((a) => <AgentCard key={a.id} a={a} onChange={reload} />)}</div>;
}

function Executions() {
  const { data, error, loading, reload } = useAsync(() => api.runs());
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!data?.length) return <Empty>No executions yet. Run a test from an agent to see one here.</Empty>;
  return <div className="space-y-2">{data.map((r) => <RunCard key={r.id} run={r} showAgent />)}</div>;
}

const TABS = [["agents", "Agents"], ["approvals", "Approvals"], ["executions", "Executions"]] as const;

export default function AgentsPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.find(([id]) => id === params.get("tab"))?.[0] ?? "agents";
  const pending = useAsync(() => api.approvals("pending"));
  return (
    <>
      <PageHeader eyebrow="Agent Studio" title="Agents" subtitle="Create, test and supervise the agents that run your store."
        actions={<Link to="/agents/new" className="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3.5 text-[13px] font-medium text-app hover:bg-primary-hover"><Plus size={15} />New agent</Link>} />
      <div className="mb-5 flex gap-1.5 overflow-x-auto" role="tablist">
        {TABS.map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} onClick={() => setParams(id === "agents" ? {} : { tab: id })}
            className={`flex shrink-0 items-center gap-2 rounded-full border px-3.5 py-1.5 font-medium ${tab === id ? "border-primary bg-primary text-app" : "border-line bg-surface text-ink2 hover:text-ink"}`}>
            {label}{id === "approvals" && !!pending.data?.length && <span className="rounded-full bg-warn px-1.5 text-[11px] text-app">{pending.data.length}</span>}
          </button>
        ))}
      </div>
      {tab === "agents" && <AgentList />}
      {tab === "approvals" && <ApprovalsPanel onChange={pending.reload} />}
      {tab === "executions" && <Executions />}
    </>
  );
}
