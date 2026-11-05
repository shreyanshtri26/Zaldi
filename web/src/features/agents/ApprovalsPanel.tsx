import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorNote, Modal, Spinner } from "../../components/ui";
import { useAsync } from "../../hooks/useAsync";
import { useToast } from "../../hooks/useToast";
import { api } from "../../services/api";
import type { Approval, Policy } from "../../types";
import { when } from "./ExecutionTimeline";

function ApprovalCard({ a, onDone }: { a: Approval; onDone: () => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(a.proposed_content);
  const [busy, setBusy] = useState("");

  async function decide(action: "approve" | "reject") {
    setBusy(action);
    try {
      await api.decide(a.id, action, editing ? text : undefined);
      toast(action === "approve" ? `${a.policy_title} updated and re-indexed` : "Proposal rejected");
      onDone();
    } catch (e) { toast((e as Error).message, "bad"); } finally { setBusy(""); }
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div><div className="font-semibold">{a.agent_name ?? "Merchant"} proposes updating {a.policy_title}</div>
          <div className="text-[12px] text-ink2">{when(a.created_at)}</div></div>
        <Badge tone={a.status === "pending" ? "warn" : a.status === "approved" ? "ok" : "mute"}>{a.status}</Badge>
      </div>
      {a.reason && <p className="mb-3 text-ink2"><span className="font-medium text-ink">Reason: </span>{a.reason}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        <div><div className="label">Current</div><p className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-surface2 p-3 text-ink2">{a.current_content}</p></div>
        <div><div className="label">Proposed</div>
          {editing
            ? <textarea className="input min-h-32" aria-label="Edit proposal" value={text} onChange={(e) => setText(e.target.value)} />
            : <p className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg border border-primary/30 bg-primary/5 p-3">{a.proposed_content}</p>}
        </div>
      </div>
      {a.status === "pending" && (
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={() => setEditing(!editing)}>{editing ? "Stop editing" : "Edit proposal"}</Button>
          <Button variant="danger" loading={busy === "reject"} disabled={!!busy} onClick={() => decide("reject")}>Reject</Button>
          <Button loading={busy === "approve"} disabled={!!busy || !text.trim()} onClick={() => decide("approve")}>Approve and publish</Button>
        </div>
      )}
    </Card>
  );
}

function ProposeModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const toast = useToast();
  const { data: policies } = useAsync<Policy[]>(() => api.policies());
  const [policyId, setPolicyId] = useState(0);
  const [content, setContent] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const policy = policies?.find((p) => p.id === policyId);

  async function submit() {
    setBusy(true);
    try {
      await api.propose(policyId, content, reason);
      toast("Proposal created. Nothing changes until it is approved.");
      setContent(""); setReason(""); setPolicyId(0); onDone(); onClose();
    } catch (e) { toast((e as Error).message, "bad"); } finally { setBusy(false); }
  }

  return (
    <Modal open={open} title="Propose a policy change" onClose={onClose} wide>
      <div className="space-y-3">
        <div><label className="label" htmlFor="p-policy">Policy</label>
          <select id="p-policy" className="input" value={policyId} onChange={(e) => { const id = Number(e.target.value); setPolicyId(id); setContent(policies?.find((p) => p.id === id)?.content ?? ""); }}>
            <option value={0}>Choose a policy…</option>{policies?.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          </select></div>
        {policy && <div><label className="label" htmlFor="p-new">New content</label><textarea id="p-new" rows={6} className="input" value={content} onChange={(e) => setContent(e.target.value)} /></div>}
        <div><label className="label" htmlFor="p-why">Reason</label><input id="p-why" className="input" value={reason} onChange={(e) => setReason(e.target.value)} /></div>
        <div className="flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={busy} disabled={!policy || !content.trim() || content.trim() === policy.content.trim()} onClick={submit}>Create proposal</Button></div>
      </div>
    </Modal>
  );
}

export default function ApprovalsPanel({ onChange }: { onChange?: () => void }) {
  const { data, error, loading, reload } = useAsync(() => api.approvals());
  const [proposing, setProposing] = useState(false);
  const refresh = () => { void reload(); onChange?.(); };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-ink2">Agents never change a policy on their own. Every change waits here for your approval.</p>
        <Button variant="ghost" onClick={() => setProposing(true)}>Propose a change</Button>
      </div>
      {loading && !data ? <Spinner /> : error ? <ErrorNote message={error} onRetry={reload} />
        : !data?.length ? <Empty>No proposals yet.</Empty> : data.map((a) => <ApprovalCard key={a.id} a={a} onDone={refresh} />)}
      <ProposeModal open={proposing} onClose={() => setProposing(false)} onDone={refresh} />
    </div>
  );
}
