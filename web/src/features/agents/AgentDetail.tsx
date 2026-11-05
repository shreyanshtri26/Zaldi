import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Badge, Button, Card, Empty, ErrorNote, PageHeader, Spinner } from "../../components/ui";
import { APPROVAL_ACTIONS, CAPABILITIES, PERMISSIONS, STATUS_TONE, TOOLS } from "../../data/options";
import { useAsync } from "../../hooks/useAsync";
import { useToast } from "../../hooks/useToast";
import { api } from "../../services/api";
import type { Agent, AgentDraft } from "../../types";
import {
  ApprovalFields, CapabilityFields, IdentityFields, InstructionFields, KnowledgeFields, PermissionFields, ToolFields,
} from "./ConfigSections";
import { RunCard, when } from "./ExecutionTimeline";
import TestPanel from "./TestPanel";

const TABS = [["overview", "Overview"], ["instructions", "Instructions"], ["tools", "Tools"], ["knowledge", "Knowledge"],
  ["permissions", "Permissions"], ["testing", "Testing"], ["executions", "Executions"]] as const;

const toDraft = (a: Agent): AgentDraft => ({ name: a.name, description: a.description, icon: a.icon, model: a.model, config: a.config });

function Executions({ agentId, refreshKey }: { agentId: number; refreshKey: number }) {
  const { data, error, loading, reload } = useAsync(() => api.runs(agentId), [agentId, refreshKey]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!data?.length) return <Empty>No executions yet. Run a test to create one.</Empty>;
  return <div className="space-y-2">{data.map((r) => <RunCard key={r.id} run={r} />)}</div>;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <Card className="p-4"><div className="text-[12px] text-mute">{label}</div><div className="mt-1 text-xl font-semibold">{value}</div></Card>;
}

export default function AgentDetail() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab = TABS.find(([t]) => t === params.get("tab"))?.[0] ?? "overview";
  const toast = useToast();
  const { data: agent, error, loading, reload } = useAsync(() => api.agent(id), [id]);
  const [draft, setDraft] = useState<AgentDraft | null>(null);
  const [saving, setSaving] = useState(false);
  const [runs, setRuns] = useState(0);

  useEffect(() => { if (agent) setDraft(toDraft(agent)); }, [agent]);

  if (loading && !agent) return <Spinner />;
  if (error || !agent || !draft) return <ErrorNote message={error || "Agent not found"} onRetry={reload} />;

  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(agent));
  const editable = ["instructions", "tools", "knowledge", "permissions"].includes(tab) || tab === "overview";
  const props = { draft, onChange: setDraft };

  async function save() {
    setSaving(true);
    try { await api.updateAgent(id, draft!); toast("Changes saved"); await reload(); } catch (e) { toast((e as Error).message, "bad"); } finally { setSaving(false); }
  }
  async function setStatus(status: "active" | "paused") {
    try { await api.updateAgent(id, { status }); toast(status === "active" ? "Agent active" : "Agent paused"); await reload(); } catch (e) { toast((e as Error).message, "bad"); }
  }

  return (
    <>
      <Link to="/agents" className="mb-3 inline-flex items-center gap-1.5 text-ink2 hover:text-ink"><ArrowLeft size={14} />Agents</Link>
      <PageHeader eyebrow="Agent" title={agent.name} subtitle={agent.description}
        actions={<>
          <Badge tone={STATUS_TONE[agent.status]}>{agent.status}</Badge>
          <Button variant="ghost" onClick={() => setStatus(agent.status === "active" ? "paused" : "active")}>{agent.status === "active" ? "Pause" : "Activate"}</Button>
        </>} />
      <div className="mb-5 flex gap-1.5 overflow-x-auto" role="tablist">
        {TABS.map(([t, label]) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setParams(t === "overview" ? {} : { tab: t })}
            className={`shrink-0 rounded-full border px-3.5 py-1.5 font-medium ${tab === t ? "border-primary bg-primary text-app" : "border-line bg-surface text-ink2 hover:text-ink"}`}>{label}</button>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_300px]">
        <div className="min-w-0">
          {tab === "overview" && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Executions" value={agent.executions} />
                <Stat label="Success rate" value={agent.success_rate === null ? "-" : `${agent.success_rate}%`} />
                <Stat label="Model" value={agent.model} />
                <Stat label="Last activity" value={agent.last_activity ? when(agent.last_activity).split(",")[0] : "Never"} />
              </div>
              <Card className="p-5"><IdentityFields {...props} /></Card>
            </div>
          )}
          {tab === "instructions" && <Card className="p-5"><InstructionFields {...props} /></Card>}
          {tab === "tools" && <Card className="space-y-5 p-5"><div><h3 className="mb-2 font-semibold">Capabilities</h3>{CapabilityFields(props, CAPABILITIES)}</div>
            <div><h3 className="mb-2 font-semibold">Tools</h3>{ToolFields(props, TOOLS)}</div></Card>}
          {tab === "knowledge" && <Card className="p-5"><KnowledgeFields {...props} /></Card>}
          {tab === "permissions" && <Card className="space-y-5 p-5"><div><h3 className="mb-2 font-semibold">Permissions</h3>{PermissionFields(props, PERMISSIONS)}</div>
            <div><h3 className="mb-1 font-semibold">Needs human approval</h3><p className="mb-2 text-ink2">Policy edits always go through the Approvals queue.</p>{ApprovalFields(props, APPROVAL_ACTIONS)}</div></Card>}
          {tab === "testing" && <Card className="p-5"><TestPanel agentId={id} disabled={agent.status === "paused"} onRun={() => { setRuns((n) => n + 1); void reload(); }} /></Card>}
          {tab === "executions" && <Executions agentId={id} refreshKey={runs} />}
          {editable && (
            <div className="sticky bottom-3 mt-4 flex items-center justify-between gap-3 rounded-card border border-line bg-surface/95 p-3 backdrop-blur">
              <span className={dirty ? "text-warn" : "text-ink2"}>{dirty ? "Unsaved changes" : "All changes saved"}</span>
              <div className="flex gap-2">
                <Button variant="ghost" disabled={!dirty || saving} onClick={() => setDraft(toDraft(agent))}>Discard</Button>
                <Button loading={saving} disabled={!dirty || !draft.name.trim()} onClick={save}>Save changes</Button>
              </div>
            </div>
          )}
        </div>
        <aside className="hidden lg:block">
          <Card className="sticky top-20 space-y-3 p-4">
            <h3 className="font-semibold">Configuration summary</h3>
            {([["Capabilities", draft.config.capabilities?.length], ["Tools", draft.config.tools?.length], ["Policies", draft.config.knowledge?.length],
              ["Permissions", draft.config.permissions?.length], ["Needs approval", draft.config.approval_actions?.length]] as const).map(([k, v]) => (
              <div key={k} className="flex justify-between"><span className="text-ink2">{k}</span><span>{v ?? 0}</span></div>))}
          </Card>
        </aside>
      </div>
    </>
  );
}
