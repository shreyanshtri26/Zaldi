import { useCallback, useEffect, useState } from "react";
import { createItem, deleteItem, listItems, updateItem } from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useToast } from "../../shared/context/ToastContext.jsx";
import Drawer from "../../shared/components/Drawer.jsx";
import Icon from "../../shared/components/Icon.jsx";

export default function PoliciesView({ initialQuery = "" }) {
  const { token } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState(initialQuery);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => listItems("policies").then(setRows).catch((e) => { toast(e.message, "bad"); setRows([]); }), [toast]);
  useEffect(() => { load(); }, [load]);

  const t = q.trim().toLowerCase();
  const shown = (rows || []).filter((r) => !t || r.title.toLowerCase().includes(t) || r.content.toLowerCase().includes(t));

  async function save() {
    setSaving(true);
    try {
      form.id ? await updateItem("policies", form.id, form, token) : await createItem("policies", form, token);
      toast("Policy saved. The chatbot will use it right away.");
      setForm(null); load();
    } catch (e) { toast(e.message, "bad"); } finally { setSaving(false); }
  }
  async function remove(r) {
    if (!window.confirm(`Delete "${r.title}"?`)) return;
    try { await deleteItem("policies", r.id, token); toast("Policy deleted"); load(); } catch (e) { toast(e.message, "bad"); }
  }

  return (
    <div className="col-wide">
      <div className="page-head">
        <div><div className="eyebrow">Store knowledge</div><h2>Policies</h2><p>The chatbot answers shipping, payment, returns and support questions from these.</p></div>
        <span className="spacer" />
        <button className="btn" onClick={() => setForm({})}><Icon name="plus" size={16} /> Add policy</button>
      </div>
      <div className="toolbar"><div className="search"><Icon name="search" size={16} /><input className="input" placeholder="Search policies…" aria-label="Search policies" value={q} onChange={(e) => setQ(e.target.value)} /></div></div>
      {rows && !shown.length && <div className="card empty">No policies found.</div>}
      <div className="grid-2">
        {shown.map((r) => (
          <article className="card" key={r.id}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <h3 style={{ margin: 0, flex: 1 }}>{r.title}</h3>
              <button className="icon-btn" aria-label={`Edit ${r.title}`} onClick={() => setForm(r)}><Icon name="edit" size={16} /></button>
              <button className="icon-btn" aria-label={`Delete ${r.title}`} onClick={() => remove(r)}><Icon name="trash" size={16} /></button>
            </div>
            <p style={{ margin: 0, color: "var(--muted)", display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}>{r.content}</p>
            <div className="sub" style={{ marginTop: 10, color: "var(--muted)", fontSize: 12 }}>Updated {r.updated_at}</div>
          </article>
        ))}
      </div>
      {form && (
        <Drawer title={form.id ? "Edit policy" : "Add policy"} onClose={() => setForm(null)} onSubmit={save} saving={saving}>
          <label className="field full">Title<input className="input" required value={form.title ?? ""} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label className="field full">Content<textarea className="textarea" rows={14} required value={form.content ?? ""} onChange={(e) => setForm({ ...form, content: e.target.value })} /></label>
        </Drawer>
      )}
    </div>
  );
}
