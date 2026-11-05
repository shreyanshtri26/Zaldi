import { useEffect, useState } from "react";
import { getAdminSettings, saveAdminSettings } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useSiteConfig } from "../../../shared/context/SiteConfigContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const FIELDS = [
  ["brand_name", "Brand name", "Shown in the sidebar and browser tab"],
  ["tagline", "Tagline", "Small text under the brand name"],
  ["welcome_heading", "Welcome heading", "Large text on an empty chat"],
  ["welcome_subtitle", "Welcome text", "Short help text under the heading", true],
  ["input_placeholder", "Message box placeholder", "Hint inside the empty message box"],
];

export default function StorefrontSettings() {
  const { token } = useAuth();
  const toast = useToast();
  const { reload } = useSiteConfig();
  const [values, setValues] = useState(null);
  const [defaults, setDefaults] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getAdminSettings(token).then((r) => { setValues(r.settings); setDefaults(r.defaults); }).catch((e) => toast(e.message, "bad"));
  }, [token, toast]);

  // Sending "" resets a setting to its default, so values equal to the default are sent as "".
  async function save(payload) {
    setSaving(true);
    try {
      const r = await saveAdminSettings(payload, token);
      setValues(r.settings);
      reload();
      toast("Storefront text saved");
    } catch (e) { toast(e.message, "bad"); } finally { setSaving(false); }
  }
  const saveAll = () => save(Object.fromEntries(FIELDS.map(([k]) => [k, values[k] === defaults[k] ? "" : values[k]])));
  const resetAll = () => save(Object.fromEntries(FIELDS.map(([k]) => [k, ""])));

  if (!values) return <div className="empty">Loading…</div>;
  return (
    <section className="panel">
      <div className="panel-head">
        <div><div className="panel-title">Storefront text</div><div className="panel-sub">What customers see on the chat page. Empty a field to restore its default.</div></div>
      </div>
      <form className="panel-body form-grid" onSubmit={(e) => { e.preventDefault(); saveAll(); }}>
        {FIELDS.map(([key, label, hint, area]) => (
          <label key={key} className={`field${area ? " full" : ""}`}>{label}
            {area
              ? <textarea className="textarea" rows={3} value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />
              : <input className="input" value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />}
            <span className="hint">{hint}{values[key] !== defaults[key] && " · customised"}</span>
          </label>
        ))}
        <div className="actions full">
          <button className="btn" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
          <button type="button" className="btn ghost" disabled={saving} onClick={resetAll}>Reset to defaults</button>
        </div>
      </form>
    </section>
  );
}
