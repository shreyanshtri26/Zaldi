import { ArrowLeft, ArrowRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge, Button, Card, PageHeader } from "../../components/ui";
import { APPROVAL_ACTIONS, CAPABILITIES, PERMISSIONS, TOOLS, labelOf } from "../../data/options";
import { useToast } from "../../hooks/useToast";
import { api } from "../../services/api";
import type { AgentDraft } from "../../types";
import {
  ApprovalFields, CapabilityFields, IdentityFields, InstructionFields, KnowledgeFields, PermissionFields, ToolFields,
  type SectionProps,
} from "./ConfigSections";
import TestPanel from "./TestPanel";

export const EMPTY_DRAFT: AgentDraft = {
  name: "", description: "", icon: "bot", model: "gemini",
  config: { languages: ["English", "Hindi", "Hinglish"], capabilities: [], tools: [], knowledge: [], permissions: ["read_products"], approval_actions: [] },
};

const STEPS = ["Identity", "Instructions", "Capabilities", "Knowledge", "Tools", "Permissions", "Approval", "Test"] as const;

function Summary({ draft }: { draft: AgentDraft }) {
  const list = (ids: string[] | undefined, src: Parameters<typeof labelOf>[0]) => (ids?.length ? ids.map((i) => labelOf(src, i)).join(", ") : "None");
  const rows: [string, string][] = [
    ["Capabilities", list(draft.config.capabilities, CAPABILITIES)], ["Tools", list(draft.config.tools, TOOLS)],
    ["Permissions", list(draft.config.permissions, PERMISSIONS)], ["Needs approval", list(draft.config.approval_actions, APPROVAL_ACTIONS)],
    ["Knowledge", draft.config.knowledge?.join(", ") || "None"],
  ];
  return <dl className="space-y-2">{rows.map(([k, v]) => <div key={k}><dt className="text-[12px] text-mute">{k}</dt><dd>{v}</dd></div>)}</dl>;
}

export default function AgentWizard() {
  const nav = useNavigate();
  const toast = useToast();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<AgentDraft>(EMPTY_DRAFT);
  const [savedId, setSavedId] = useState<number | null>(null);
  const [busy, setBusy] = useState<"" | "draft" | "active">("");
  const props: SectionProps = { draft, onChange: setDraft };

  const canNext = step !== 0 || draft.name.trim().length > 0;

  async function save(status: "draft" | "active") {
    setBusy(status);
    try {
      const saved = savedId ? await api.updateAgent(savedId, { ...draft, status }) : await api.createAgent({ ...draft, status });
      setSavedId(saved.id);
      toast(status === "active" ? "Agent activated" : "Saved as draft");
      if (status === "active") nav(`/agents/${saved.id}`);
    } catch (e) { toast((e as Error).message, "bad"); } finally { setBusy(""); }
  }

  const body: ReactNode[] = [
    <IdentityFields {...props} />, <InstructionFields {...props} />, CapabilityFields(props, CAPABILITIES), <KnowledgeFields {...props} />,
    ToolFields(props, TOOLS), PermissionFields(props, PERMISSIONS), ApprovalFields(props, APPROVAL_ACTIONS),
    <div className="space-y-5">
      <Summary draft={draft} />
      {savedId
        ? <TestPanel agentId={savedId} />
        : <p className="text-ink2">Save as a draft to run live tests before you activate this agent.</p>}
    </div>,
  ];
  const hints = [
    "Name it and say what it is for.", "Tell the agent how to behave.", "What can this agent do?", "Which policies may it use?",
    "Which tools can it call?", "What is it allowed to access?", "Which actions must a person approve first?", "Review, test, then activate.",
  ];

  return (
    <>
      <Link to="/agents" className="mb-3 inline-flex items-center gap-1.5 text-ink2 hover:text-ink"><ArrowLeft size={14} />Agents</Link>
      <PageHeader eyebrow="New agent" title={draft.name.trim() || "Create an agent"} />
      <div className="mb-5 flex gap-1.5 overflow-x-auto pb-1" aria-label="Steps">
        {STEPS.map((s, i) => (
          <button key={s} onClick={() => canNext && setStep(i)} aria-current={i === step ? "step" : undefined}
            className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 ${i === step ? "border-primary bg-primary text-app" : i < step ? "border-primary/40 text-primary" : "border-line text-ink2"}`}>
            <span className="text-[11px] font-bold">{i + 1}</span><span className="hidden sm:inline">{s}</span>
          </button>
        ))}
      </div>
      <Card className="mx-auto max-w-3xl p-5">
        <div className="mb-4 flex items-center justify-between gap-2">
          <div><h2 className="text-[17px] font-semibold">{STEPS[step]}</h2><p className="text-ink2">{hints[step]}</p></div>
          <Badge tone="mute">Step {step + 1} of {STEPS.length}</Badge>
        </div>
        {body[step]}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-line pt-4">
          <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><ArrowLeft size={14} />Back</Button>
          {step < STEPS.length - 1
            ? <Button disabled={!canNext} onClick={() => setStep(step + 1)}>Next<ArrowRight size={14} /></Button>
            : <div className="flex gap-2">
              <Button variant="ghost" loading={busy === "draft"} disabled={!!busy || !draft.name.trim()} onClick={() => save("draft")}>Save as draft</Button>
              <Button loading={busy === "active"} disabled={!!busy || !draft.name.trim()} onClick={() => save("active")}>Activate agent</Button>
            </div>}
        </div>
      </Card>
    </>
  );
}
