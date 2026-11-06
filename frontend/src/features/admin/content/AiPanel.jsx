import { useCallback, useEffect, useState } from "react";
import { getAiModels, getAiSettings, removeAiKey, resetAiModel, resetAiProvider, saveAiKey, saveAiModel, saveAiProvider, testAiKey } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const HELP = {
  google: { where: "Get a key at aistudio.google.com/apikey", placeholder: "AIza…" },
  groq: { where: "Create a key in the Groq console under API Keys", placeholder: "gsk_…" },
};

// One provider: its key (write-only), its model dropdown (the provider's own current list) and a test button.
function ProviderCard({ id, info, active, onChange }) {
  const { token } = useAuth();
  const toast = useToast();
  const [key, setKey] = useState("");
  const [models, setModels] = useState(null);
  const [test, setTest] = useState(null);
  const [busy, setBusy] = useState(false);

  const loadModels = useCallback(() => getAiModels(id, token).then(setModels).catch((e) => toast(e.message, "bad")), [id, token, toast]);
  useEffect(() => { loadModels(); }, [loadModels, info.own_key_set, info.server_key_set]);

  async function run(action, success) {
    setBusy(true);
    try { onChange(await action()); if (success) toast(success); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  }
  const saveKey = (e) => { e.preventDefault(); run(async () => { const out = await saveAiKey(id, key, token); setKey(""); setTest(null); return out; }, `${info.label} key saved`); };
  const runTest = async () => { setBusy(true); setTest(null); try { setTest(await testAiKey(id, token)); } catch (e) { setTest({ ok: false, message: e.message }); } finally { setBusy(false); } };

  const keyNote = info.source === "store" ? `Using your key (${info.own_key_hint}).` : info.source === "server" ? "Using the server's key. Add your own to use your own quota." : "No key yet.";
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <div className="panel-title">{info.label}{active ? " · used for chats" : ""}</div>
          <div className="panel-sub">{keyNote}</div>
        </div>
      </div>
      <div className="panel-body form-grid">
        <form className="full form-grid" onSubmit={saveKey}>
          <label className="field full">{info.own_key_set ? "Replace your API key" : "Your API key"}
            <input className="input" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder={info.own_key_set ? "Saved. Type to replace" : HELP[id].placeholder} />
            <span className="hint">{HELP[id].where}. It is encrypted, only used for your store, and never shown again.</span>
          </label>
          <div className="actions full">
            <button className="btn" disabled={busy || !key.trim()}>Save key</button>
            <button type="button" className="btn ghost" disabled={busy || info.source === "none"} onClick={runTest}>Test key</button>
            <button type="button" className="btn ghost" disabled={busy || !info.own_key_set} onClick={() => run(() => removeAiKey(id, token), "Key removed")}>Remove my key</button>
          </div>
        </form>
        {test && <div className={`full note ${test.ok ? "ok" : "bad"}`} role="status">{test.message}</div>}
        <label className="field full">Model
          <select className="select" value={info.model} disabled={busy || !models}
            onChange={(e) => run(() => saveAiModel(id, e.target.value, token), "Model updated")}>
            {(models?.models || [{ id: info.model, label: info.model }]).map((m) => (
              <option key={m.id} value={m.id}>{m.label === m.id ? m.id : `${m.label} (${m.id})`}{m.id === models?.default ? " · default" : ""}</option>
            ))}
            {models && !models.models.some((m) => m.id === info.model) && <option value={info.model}>{info.model}</option>}
          </select>
          <span className="hint">{models?.live ? "The newest models from your account, straight from the provider." : "A built-in list. Add a key to see the provider's current models."}</span>
        </label>
        <div className="actions full">
          <button type="button" className="btn ghost" disabled={busy} onClick={loadModels}>Refresh list</button>
          <button type="button" className="btn ghost" disabled={busy || info.model_is_default} onClick={() => run(() => resetAiModel(id, token), "Back to the default model")}>Use the default model</button>
        </div>
      </div>
    </section>
  );
}

// Which AI answers your shoppers: the provider, your own keys, and the model for each.
export default function AiPanel() {
  const { token } = useAuth();
  const toast = useToast();
  const [info, setInfo] = useState(null);
  useEffect(() => { getAiSettings(token).then(setInfo).catch((e) => toast(e.message, "bad")); }, [token, toast]);
  if (!info) return <div className="empty">Loading…</div>;
  const pick = async (provider) => { try { setInfo(provider === "default" ? await resetAiProvider(token) : await saveAiProvider(provider, token)); toast("Provider updated"); } catch (e) { toast(e.message, "bad"); } };
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section className="panel">
        <div className="panel-head"><div><div className="panel-title">AI model</div>
          <div className="panel-sub">Choose which AI answers your shoppers, and use your own key so the cost and limits are yours. Changes apply to the next message.</div></div></div>
        <div className="panel-body form-grid">
          <label className="field full">Provider for chats
            <select className="select" value={info.provider_is_default ? "default" : info.provider} onChange={(e) => pick(e.target.value)}>
              <option value="default">Automatic ({info.providers[info.provider].label})</option>
              {Object.entries(info.providers).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}
            </select>
            <span className="hint">Automatic uses the provider you have your own key for, or the server's default. Photo search and similarity search use Gemini.</span>
          </label>
        </div>
      </section>
      {Object.entries(info.providers).map(([id, p]) => <ProviderCard key={id} id={id} info={p} active={info.provider === id} onChange={setInfo} />)}
    </div>
  );
}
