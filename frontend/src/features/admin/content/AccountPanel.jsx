import { useState } from "react";
import { changeAccountPassword } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

// A store owner changes their own sign-in password.
export default function AccountPanel() {
  const { token } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", again: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (f.next !== f.again) { toast("The two new passwords are not the same.", "bad"); return; }
    setBusy(true);
    try { await changeAccountPassword(f.current, f.next, token); setF({ current: "", next: "", again: "" }); toast("Password changed. Use it next time you sign in."); }
    catch (err) { toast(err.message, "bad"); } finally { setBusy(false); }
  }
  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Your password</div>
        <div className="panel-sub">Change the password you use to sign in to this store. (The server admin changes theirs under Server.)</div></div></div>
      <form className="panel-body form-grid" onSubmit={save}>
        <label className="field full">Current password<input className="input" type="password" autoComplete="current-password" value={f.current} onChange={set("current")} /></label>
        <label className="field">New password<input className="input" type="password" autoComplete="new-password" value={f.next} onChange={set("next")} /><span className="hint">At least 10 characters.</span></label>
        <label className="field">New password again<input className="input" type="password" autoComplete="new-password" value={f.again} onChange={set("again")} /></label>
        <div className="actions full"><button className="btn" disabled={busy || !f.current || !f.next}>Change password</button></div>
      </form>
    </section>
  );
}
