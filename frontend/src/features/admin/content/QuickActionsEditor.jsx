import { useCallback, useEffect, useState } from "react";
import { createItem, deleteItem, listItems, updateItem } from "../../../api/client.js";
import Drawer from "../../../shared/components/Drawer.jsx";
import Icon, { QUICK_ICONS } from "../../../shared/components/Icon.jsx";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useSiteConfig } from "../../../shared/context/SiteConfigContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const BLANK = { title: "", subtitle: "", message: "", icon: "chat", position: 0, active: 1 };

export default function QuickActionsEditor() {
  const { token } = useAuth();
  const toast = useToast();
  const { reload } = useSiteConfig();
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => listItems("quick_actions").then(setRows).catch((e) => { toast(e.message, "bad"); setRows([]); }), [toast]);
  useEffect(() => { load(); }, [load]);
  const changed = () => { load(); reload(); };

  async function save() {
    setSaving(true);
    try {
      form.id ? await updateItem("quick_actions", form.id, form, token) : await createItem("quick_actions", form, token);
      toast("Quick action saved");
      setForm(null);
      changed();
    } catch (e) { toast(e.message, "bad"); } finally { setSaving(false); }
  }
  async function toggle(row) {
    try { await updateItem("quick_actions", row.id, { active: row.active ? 0 : 1 }, token); changed(); } catch (e) { toast(e.message, "bad"); }
  }
  async function remove(row) {
    if (!window.confirm(`Delete "${row.title}"?`)) return;
    try { await deleteItem("quick_actions", row.id, token); toast("Quick action deleted"); changed(); } catch (e) { toast(e.message, "bad"); }
  }
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <section className="panel">
      <div className="panel-head">
        <div><div className="panel-title">Quick actions</div><div className="panel-sub">Suggestion cards on the empty chat. Clicking one sends its message.</div></div>
        <button className="btn sm" onClick={() => setForm({ ...BLANK, position: (rows?.length || 0) + 1 })}><Icon name="plus" size={14} /> Add card</button>
      </div>
      <div className="table-wrap" style={{ border: 0, borderRadius: 0 }}>
        <table>
          <thead><tr><th>Card</th><th>Message sent</th><th className="num">Order</th><th>Shown</th><th /></tr></thead>
          <tbody>
            {(rows || []).map((r) => (
              <tr key={r.id}>
                <td><span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><Icon name={r.icon} size={16} /><b>{r.title}</b></span><div className="sub">{r.subtitle}</div></td>
                <td>{r.message}</td>
                <td className="num">{r.position}</td>
                <td><button className={`chip${r.active ? " active" : ""}`} aria-pressed={!!r.active} onClick={() => toggle(r)}>{r.active ? "Shown" : "Hidden"}</button></td>
                <td className="act">
                  <button className="icon-btn" aria-label={`Edit ${r.title}`} onClick={() => setForm(r)}><Icon name="edit" size={16} /></button>
                  <button className="icon-btn" aria-label={`Delete ${r.title}`} onClick={() => remove(r)}><Icon name="trash" size={16} /></button>
                </td>
              </tr>
            ))}
            {rows && !rows.length && <tr><td colSpan={5} className="empty">No cards. The chat will show an empty welcome screen.</td></tr>}
          </tbody>
        </table>
      </div>
      {form && (
        <Drawer title={form.id ? "Edit quick action" : "Add quick action"} onClose={() => setForm(null)} onSubmit={save} saving={saving}>
          <label className="field full">Title<input className="input" required value={form.title ?? ""} onChange={set("title")} /></label>
          <label className="field full">Subtitle<input className="input" value={form.subtitle ?? ""} onChange={set("subtitle")} /></label>
          <label className="field full">Message sent to the assistant<input className="input" required value={form.message ?? ""} onChange={set("message")} /></label>
          <label className="field">Icon
            <select className="select" value={form.icon} onChange={set("icon")}>{QUICK_ICONS.map((i) => <option key={i}>{i}</option>)}</select>
          </label>
          <label className="field">Order<input className="input" type="number" min="0" value={form.position ?? 0} onChange={set("position")} /></label>
        </Drawer>
      )}
    </section>
  );
}
