import { useEffect, useState } from "react";
import { getAdminSettings, saveAdminSettings } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useSiteConfig } from "../../../shared/context/SiteConfigContext.jsx";
import { FONTS, PALETTE, themeVars } from "../../../shared/theme.js";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const LOOK = [...PALETTE.map(([k]) => k), "font_family", "font_size", "cards_align", "cards_position", "bar_position", "bar_width", "bar_shape", "photo_button"];
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
      toast("Storefront saved");
    } catch (e) { toast(e.message, "bad"); } finally { setSaving(false); }
  }
  const saveAll = () => save(Object.fromEntries([...FIELDS.map(([k]) => k), ...LOOK].map((k) => [k, values[k] === defaults[k] ? "" : values[k]])));
  const resetAll = () => save(Object.fromEntries([...FIELDS.map(([k]) => k), ...LOOK].map((k) => [k, ""])));

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
        <div className="panel-title full">Look and layout</div>
        <div className="panel-title full" style={{ fontSize: 13 }}>Brand colours (also recolour the logo and tab icon)</div>
        {PALETTE.map(([key, label, hint]) => (
          <label key={key} className="field">{label}
            <span style={{ display: "flex", gap: 8 }}>
              <input type="color" value={values[key]} onChange={(e) => setValues({ ...values, [key]: e.target.value })} aria-label={`${label} colour`} />
              <input className="input" value={values[key]} maxLength={7} onChange={(e) => setValues({ ...values, [key]: e.target.value })} />
            </span>
            <span className="hint">{hexToRgb(values[key])} · {hint}</span>
          </label>
        ))}
        <label className="field">Font
          <select className="select" value={values.font_family} onChange={(e) => setValues({ ...values, font_family: e.target.value })}>
            {Object.entries(FONTS).map(([k, [name]]) => <option key={k} value={k}>{name}</option>)}
          </select>
        </label>
        <label className="field">Font size: {values.font_size}px
          <input type="range" min="12" max="20" value={values.font_size} onChange={(e) => setValues({ ...values, font_size: e.target.value })} />
        </label>
        <label className="field">Suggestion cards
          <span style={{ display: "flex", gap: 8 }}>
            <select className="select" value={values.cards_position} onChange={(e) => setValues({ ...values, cards_position: e.target.value })}>
              <option value="below">Below message box</option><option value="above">Above message box</option>
            </select>
            <select className="select" value={values.cards_align} onChange={(e) => setValues({ ...values, cards_align: e.target.value })}>
              <option value="left">Left</option><option value="center">Centre</option><option value="right">Right</option>
            </select>
          </span>
        </label>
        <label className="field">Message bar position
          <select className="select" value={values.bar_position} onChange={(e) => setValues({ ...values, bar_position: e.target.value })}><option value="center">Centre, then docks to bottom</option><option value="bottom">Always at bottom</option><option value="top">Always at top</option></select>
        </label>
        <label className="field">Message bar size and shape
          <span style={{ display: "flex", gap: 8 }}>
            <select className="select" value={values.bar_width} onChange={(e) => setValues({ ...values, bar_width: e.target.value })}><option value="narrow">Narrow</option><option value="normal">Normal</option><option value="wide">Wide</option></select>
            <select className="select" value={values.bar_shape} onChange={(e) => setValues({ ...values, bar_shape: e.target.value })}><option value="pill">Pill</option><option value="rounded">Rounded</option><option value="square">Square</option></select>
            <select className="select" value={values.photo_button} onChange={(e) => setValues({ ...values, photo_button: e.target.value })}><option value="show">Photo button on</option><option value="hide">Photo button off</option></select>
          </span>
        </label>
        <div className="full">
          <div className="hint">Live preview (unsaved)</div>
          <Preview values={values} />
        </div>
        <div className="actions full">
          <button className="btn" disabled={saving}>{saving ? "Saving…" : "Save changes"}</button>
          <button type="button" className="btn ghost" disabled={saving} onClick={resetAll}>Reset to defaults</button>
        </div>
      </form>
    </section>
  );
}

const hexToRgb = (h) => /^#[0-9a-f]{6}$/i.test(h) ? `rgb(${[1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)).join(", ")})` : "invalid hex";

// Mini empty-chat page using the unsaved values; the same CSS variables the real page gets.
function Preview({ values }) {
  const { quickActions } = useSiteConfig();
  const chips = (
    <div className={`chips ${values.cards_align} ${values.cards_position}`}>
      {quickActions.map((q) => <span key={q.id} className="chip">{q.title}</span>)}
    </div>
  );
  const box = <div className="composer" style={{ padding: "10px 14px", color: "var(--muted)" }}>{values.input_placeholder}</div>;
  const font = FONTS[values.font_family]?.[1];
  return (
    <div className="welcome themed" style={{ ...themeVars(values), fontSize: `${values.font_size}px`, fontFamily: font || undefined, border: "1px solid var(--border)", borderRadius: 14, padding: 20, background: "var(--bg)", color: "var(--ink)" }}>
      <b style={{ color: "var(--accent)" }}>{values.brand_name}</b>
      <h2 style={{ fontFamily: font || undefined }}>{values.welcome_heading}</h2>
      <p>{values.welcome_subtitle}</p>
      {values.cards_position === "above" && chips}
      {box}
      {values.cards_position !== "above" && chips}
    </div>
  );
}
