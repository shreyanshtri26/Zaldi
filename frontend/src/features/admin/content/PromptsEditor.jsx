import { useEffect, useState } from "react";
import { getPrompts, resetPrompt, savePrompt } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const HINTS = {
  agent_system: "Instructions for answering product and policy questions (tone, language, formatting). Tools and the product database are unchanged.",
  chitchat: "Instructions for friendly small talk. Must contain {input}, where the customer's message goes, and no other { } braces.",
};
const MAX_LENGTH = 4000;

function PromptCard({ prompt, onChange }) {
  const { token } = useAuth();
  const toast = useToast();
  const [text, setText] = useState(prompt.content);
  const [busy, setBusy] = useState(false);
  const dirty = text !== prompt.content;

  async function run(action, success) {
    setBusy(true);
    try { const next = await action(); setText(next.content); onChange(next); toast(success); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <div><div className="panel-title">{prompt.label}</div><div className="panel-sub">{HINTS[prompt.name]}</div></div>
        <span className={`badge ${prompt.is_custom ? "warn" : ""}`}>{prompt.is_custom ? "Customised" : "Default"}</span>
      </div>
      <div className="panel-body">
        <textarea className="textarea" rows={9} value={text} maxLength={MAX_LENGTH} aria-label={prompt.label} onChange={(e) => setText(e.target.value)} />
        <div className="prompt-foot">
          <span className="hint">{text.length} / {MAX_LENGTH} · changes apply to the next customer message</span>
          <span style={{ display: "flex", gap: 8 }}>
            <button className="btn ghost sm" disabled={busy || !prompt.is_custom} onClick={() => run(() => resetPrompt(prompt.name, token), "Restored the default prompt")}>Reset to default</button>
            <button className="btn sm" disabled={busy || !dirty} onClick={() => run(() => savePrompt(prompt.name, text, token), "Prompt saved")}>Save prompt</button>
          </span>
        </div>
      </div>
    </section>
  );
}

export default function PromptsEditor() {
  const { token } = useAuth();
  const toast = useToast();
  const [prompts, setPrompts] = useState(null);
  useEffect(() => { getPrompts(token).then(setPrompts).catch((e) => toast(e.message, "bad")); }, [token, toast]);
  if (!prompts) return <div className="empty">Loading…</div>;
  return (
    <div style={{ display: "grid", gap: 16 }}>
      {prompts.map((p) => (
        <PromptCard key={`${p.name}-${p.is_custom}`} prompt={p} onChange={(next) => setPrompts(prompts.map((x) => (x.name === next.name ? next : x)))} />
      ))}
    </div>
  );
}
