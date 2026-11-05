import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { ICONS, LANGUAGES, type Option } from "../../data/options";
import type { AgentConfig, AgentDraft } from "../../types";

export interface SectionProps { draft: AgentDraft; onChange: (d: AgentDraft) => void }

const setCfg = (p: SectionProps, patch: AgentConfig) => p.onChange({ ...p.draft, config: { ...p.draft.config, ...patch } });

export function toggle(list: string[] | undefined, id: string): string[] {
  const cur = list ?? [];
  return cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
}

export function IdentityFields(p: SectionProps) {
  const { draft } = p;
  return (
    <div className="space-y-4">
      <div>
        <label className="label" htmlFor="a-name">Agent name</label>
        <input id="a-name" className="input" maxLength={60} value={draft.name} onChange={(e) => p.onChange({ ...draft, name: e.target.value })} />
      </div>
      <div>
        <label className="label" htmlFor="a-desc">Description</label>
        <input id="a-desc" className="input" value={draft.description} onChange={(e) => p.onChange({ ...draft, description: e.target.value })} />
      </div>
      <div>
        <label className="label" htmlFor="a-purpose">Purpose</label>
        <textarea id="a-purpose" rows={2} className="input" placeholder="What is this agent for?" value={draft.config.purpose ?? ""}
          onChange={(e) => setCfg(p, { purpose: e.target.value })} />
      </div>
      <div>
        <span className="label">Icon</span>
        <div className="flex flex-wrap gap-2">
          {Object.entries(ICONS).map(([id, Icon]) => (
            <button key={id} type="button" aria-label={`Icon ${id}`} aria-pressed={draft.icon === id} onClick={() => p.onChange({ ...draft, icon: id })}
              className={`grid h-10 w-10 place-items-center rounded-lg border ${draft.icon === id ? "border-primary bg-primary/15 text-primary" : "border-line text-ink2 hover:text-ink"}`}>
              <Icon size={18} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function InstructionFields(p: SectionProps) {
  const c = p.draft.config;
  const field = (key: "role" | "objective" | "rules" | "style", label: string, hint: string, rows = 2) => (
    <div>
      <label className="label" htmlFor={`i-${key}`}>{label}</label>
      <textarea id={`i-${key}`} rows={rows} className="input" placeholder={hint} value={c[key] ?? ""} onChange={(e) => setCfg(p, { [key]: e.target.value })} />
    </div>
  );
  return (
    <div className="space-y-4">
      {field("role", "Role", "e.g. You are a friendly shopping assistant for an Indian ethnic-wear store")}
      {field("objective", "Objective", "e.g. Help customers find products that match their budget and occasion")}
      {field("rules", "Behavioural rules", "e.g. Never invent prices. Say so when an item is out of stock.", 3)}
      {field("style", "Response style", "e.g. Short, warm and clear")}
      <div>
        <span className="label">Languages</span>
        <div className="flex flex-wrap gap-2">
          {LANGUAGES.map((l) => {
            const on = (c.languages ?? []).includes(l);
            return (
              <button key={l} type="button" aria-pressed={on} onClick={() => setCfg(p, { languages: toggle(c.languages, l) })}
                className={`rounded-full border px-3 py-1 ${on ? "border-primary bg-primary/15 text-primary" : "border-line text-ink2"}`}>{l}</button>
            );
          })}
        </div>
      </div>
      <p className="text-[12px] text-mute">Saved with the agent. The live storefront assistant is still controlled by the Assistant prompts in the current admin; agents do not replace them yet.</p>
    </div>
  );
}

export function CheckList({ options, value, onChange }: { options: Option[]; value: string[] | undefined; onChange: (v: string[]) => void }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {options.map((o) => {
        const on = (value ?? []).includes(o.id);
        return (
          <li key={o.id}>
            <button type="button" role="checkbox" aria-checked={on} onClick={() => onChange(toggle(value, o.id))}
              className={`flex w-full items-start gap-3 rounded-lg border p-3 text-left transition ${on ? "border-primary/60 bg-primary/10" : "border-line hover:bg-surface2"}`}>
              <span className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border ${on ? "border-primary bg-primary text-app" : "border-mute"}`}>{on && <Check size={11} strokeWidth={3} />}</span>
              <span><span className="block font-medium">{o.label}</span><span className="block text-[12px] text-ink2">{o.hint}</span></span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function KnowledgeFields(p: SectionProps) {
  const [titles, setTitles] = useState<string[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.policies().then((r) => setTitles(r.map((x) => x.title))).catch((e: Error) => setError(e.message)); }, []);
  if (error) return <p role="alert" className="text-bad">{error}</p>;
  if (!titles) return <p className="text-ink2">Loading policies…</p>;
  return (
    <div className="space-y-3">
      <p className="text-ink2">Choose the store policies this agent may use. Uploaded documents and website sources arrive with the Knowledge phase.</p>
      <CheckList options={titles.map((t) => ({ id: t, label: t, hint: "Store policy" }))} value={p.draft.config.knowledge}
        onChange={(v) => setCfg(p, { knowledge: v })} />
    </div>
  );
}

export const CapabilityFields = (p: SectionProps, options: Option[]) =>
  <CheckList options={options} value={p.draft.config.capabilities} onChange={(v) => setCfg(p, { capabilities: v })} />;
export const ToolFields = (p: SectionProps, options: Option[]) =>
  <CheckList options={options} value={p.draft.config.tools} onChange={(v) => setCfg(p, { tools: v })} />;
export const PermissionFields = (p: SectionProps, options: Option[]) =>
  <CheckList options={options} value={p.draft.config.permissions} onChange={(v) => setCfg(p, { permissions: v })} />;
export const ApprovalFields = (p: SectionProps, options: Option[]) =>
  <CheckList options={options} value={p.draft.config.approval_actions} onChange={(v) => setCfg(p, { approval_actions: v })} />;
