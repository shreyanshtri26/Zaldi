import { useCallback, useEffect, useState } from "react";
import {
  accountResetLink, accountTwoStepOff, createAccountAdmin, createStoreAdmin, deleteAccountAdmin, deleteStoreAdmin,
  listAccountsAdmin, listStoresAdmin, setAccountRole, setStoreStatus,
} from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useToast } from "../../shared/context/ToastContext.jsx";

function Accounts({ slug }) {
  const { token } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [link, setLink] = useState(null);
  const [form, setForm] = useState({ email: "", password: "", role: "owner" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => listAccountsAdmin(slug, token).then((d) => setRows(d.accounts)).catch((e) => toast(e.message, "bad")), [slug, token, toast]);
  useEffect(() => { load(); }, [load]);

  async function run(action, success) {
    setBusy(true);
    try { await action(); if (success) toast(success); await load(); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  }
  const add = (e) => { e.preventDefault(); run(async () => { await createAccountAdmin(slug, form, token); setForm({ email: "", password: "", role: "owner" }); }, "Account created"); };
  const makeLink = async (email) => {
    setBusy(true);
    try { setLink({ email, ...(await accountResetLink(slug, email, token)) }); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  };
  const copy = async (text) => { try { await navigator.clipboard.writeText(text); toast("Copied"); } catch { toast("Select the text and copy it", "bad"); } };

  if (!rows) return <div className="empty">Loading…</div>;
  return (
    <div style={{ display: "grid", gap: 12 }}>
      {rows.length === 0 ? <p className="hint">No accounts yet. Add the shop owner below.</p> : (
        <table className="table">
          <thead><tr><th>Email</th><th>Role</th><th>Two-step</th><th /></tr></thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.email}>
                <td>{a.email}</td>
                <td>
                  <select className="select" value={a.role} disabled={busy} aria-label={`Role of ${a.email}`} onChange={(e) => run(() => setAccountRole(slug, a.email, e.target.value, token), "Role changed. They must sign in again.")}>
                    <option value="owner">Owner</option><option value="viewer">Viewer</option>
                  </select>
                </td>
                <td>{a.two_step ? "On" : "Off"}</td>
                <td className="table-actions">
                  <button type="button" className="btn ghost sm" disabled={busy} onClick={() => makeLink(a.email)}>Reset link</button>
                  {a.two_step && <button type="button" className="btn ghost sm" disabled={busy} onClick={() => run(() => accountTwoStepOff(slug, a.email, token), "Two-step turned off")}>Turn off two-step</button>}
                  <button type="button" className="btn ghost sm" disabled={busy} onClick={() => run(() => deleteAccountAdmin(slug, a.email, token), "Account deleted")}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {link && (
        <div className="note ok" role="status">
          <strong>Reset link for {link.email}</strong> (works once, for one hour). Send it to them yourself:
          <code className="copy-line" style={{ marginTop: 8 }}>{link.link}</code>
          <div className="actions" style={{ marginTop: 8 }}><button type="button" className="btn ghost sm" onClick={() => copy(link.link)}>Copy link</button>
            <button type="button" className="btn ghost sm" onClick={() => setLink(null)}>Hide</button></div>
        </div>
      )}
      <form className="form-grid" onSubmit={add}>
        <label className="field">Email<input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label className="field">Password<input className="input" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <span className="hint">At least 10 characters. They can change it after signing in.</span></label>
        <label className="field">Role
          <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="owner">Owner (can change everything)</option><option value="viewer">Viewer (read only)</option></select>
        </label>
        <div className="actions full"><button className="btn" disabled={busy || !form.email || !form.password}>Add account</button></div>
      </form>
    </div>
  );
}

// Every store on this server: create, set draft or live, delete, and manage who can sign in to each one.
export default function StoresView() {
  const { token } = useAuth();
  const toast = useToast();
  const [stores, setStores] = useState(null);
  const [open, setOpen] = useState(null);
  const [form, setForm] = useState({ slug: "", name: "" });
  const [confirm, setConfirm] = useState({ slug: "", typed: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => listStoresAdmin(token).then((d) => setStores(d.stores)).catch((e) => toast(e.message, "bad")), [token, toast]);
  useEffect(() => { load(); }, [load]);

  async function run(action, success) {
    setBusy(true);
    try { await action(); if (success) toast(success); await load(); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  }
  const create = (e) => { e.preventDefault(); run(async () => { await createStoreAdmin(form.slug, form.name, token); setForm({ slug: "", name: "" }); }, "Store created. Add its owner next."); };

  if (!stores) return <div className="empty">Loading…</div>;
  return (
    <div className="col-wide" style={{ display: "grid", gap: 16 }}>
      <div className="page-head"><div><h2>Stores</h2><p>Every shop on this server. Each has its own products, chats, settings and sign-ins.</p></div></div>
      <section className="panel">
        <div className="panel-head"><div><div className="panel-title">New store</div><div className="panel-sub">A new store starts empty, as a draft.</div></div></div>
        <form className="panel-body form-grid" onSubmit={create}>
          <label className="field">Store name<input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field">Store id<input className="input" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} placeholder="my-shop" />
            <span className="hint">3 to 32 lowercase letters, digits or dashes. It goes in the website snippet.</span></label>
          <div className="actions full"><button className="btn" disabled={busy || !form.slug || !form.name}>Create store</button></div>
        </form>
      </section>
      {stores.map((s) => (
        <section className="panel" key={s.slug}>
          <div className="panel-head">
            <div><div className="panel-title">{s.name} <span className="muted">· {s.slug}</span></div>
              <div className="panel-sub">{s.slug === "default" ? "The original store on this server." : `Created ${s.created_at || ""}`}</div></div>
            <div className="table-actions">
              {s.slug !== "default" && (
                <select className="select" value={s.status} disabled={busy} aria-label={`Status of ${s.name}`} onChange={(e) => run(() => setStoreStatus(s.slug, e.target.value, token), `${s.name} is now ${e.target.value}`)}>
                  <option value="draft">Draft</option><option value="live">Live</option>
                </select>
              )}
              <button type="button" className="btn ghost sm" onClick={() => setOpen(open === s.slug ? null : s.slug)}>{open === s.slug ? "Hide accounts" : "Accounts"}</button>
              {s.slug !== "default" && <button type="button" className="btn ghost sm" onClick={() => setConfirm(confirm.slug === s.slug ? { slug: "", typed: "" } : { slug: s.slug, typed: "" })}>Delete</button>}
            </div>
          </div>
          {confirm.slug === s.slug && (
            <div className="panel-body"><div className="note bad">
              Deleting <strong>{s.name}</strong> erases all of its products, policies, chats, settings and carts, and cannot be undone. Type <code>{s.slug}</code> to confirm.
              <div className="actions" style={{ marginTop: 8 }}>
                <input className="input" value={confirm.typed} onChange={(e) => setConfirm({ ...confirm, typed: e.target.value })} aria-label="Type the store id" style={{ maxWidth: 220 }} />
                <button type="button" className="btn" disabled={busy || confirm.typed !== s.slug} onClick={() => run(async () => { await deleteStoreAdmin(s.slug, confirm.typed, token); setConfirm({ slug: "", typed: "" }); }, "Store deleted")}>Delete this store</button>
              </div>
            </div></div>
          )}
          {open === s.slug && <div className="panel-body"><Accounts slug={s.slug} /></div>}
        </section>
      ))}
    </div>
  );
}
