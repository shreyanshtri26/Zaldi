import { useCallback, useEffect, useState } from "react";
import { changeAccountPassword, disableTwoStep, enableTwoStep, getTwoStep, setupTwoStep } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

function PasswordSection() {
  const { token, login } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", again: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  async function save(e) {
    e.preventDefault();
    if (f.next !== f.again) { toast("The two new passwords are not the same.", "bad"); return; }
    setBusy(true);
    try {
      const out = await changeAccountPassword(f.current, f.next, token);
      await login(out.token); // other sessions end when the password changes; this one carries on
      setF({ current: "", next: "", again: "" });
      toast("Password changed. Any other signed-in device was signed out.");
    } catch (err) { toast(err.message, "bad"); } finally { setBusy(false); }
  }
  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Your password</div>
        <div className="panel-sub">Change the password you use to sign in to this store. Changing it signs out your other devices.</div></div></div>
      <form className="panel-body form-grid" onSubmit={save}>
        <label className="field full">Current password<input className="input" type="password" autoComplete="current-password" value={f.current} onChange={set("current")} /></label>
        <label className="field">New password<input className="input" type="password" autoComplete="new-password" value={f.next} onChange={set("next")} /><span className="hint">At least 10 characters.</span></label>
        <label className="field">New password again<input className="input" type="password" autoComplete="new-password" value={f.again} onChange={set("again")} /></label>
        <div className="actions full"><button className="btn" disabled={busy || !f.current || !f.next}>Change password</button></div>
      </form>
    </section>
  );
}

// Two-step sign-in with an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, Authy...).
function TwoStepSection() {
  const { token, login } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState(null);
  const [setup, setSetup] = useState(null);
  const [codes, setCodes] = useState(null);
  const [f, setF] = useState({ password: "", code: "" });
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => getTwoStep(token).then(setStatus).catch(() => setStatus(false)), [token]);
  useEffect(() => { load(); }, [load]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function run(action) { setBusy(true); try { return await action(); } catch (err) { toast(err.message, "bad"); return null; } finally { setBusy(false); } }
  const start = async (e) => { e.preventDefault(); const out = await run(() => setupTwoStep(f.password, token)); if (out) { setSetup(out); setF({ ...f, password: "" }); } };
  const finish = async (e) => {
    e.preventDefault();
    const out = await run(() => enableTwoStep(f.code, token));
    if (out) { setCodes(out.recovery_codes); setSetup(null); setF({ password: "", code: "" }); load(); }
  };
  const turnOff = async (e) => {
    e.preventDefault();
    const out = await run(() => disableTwoStep(f.password, f.code, token));
    if (out) { await login(out.token); setF({ password: "", code: "" }); toast("Two-step sign-in is off"); load(); }
  };
  const copy = async (text) => { try { await navigator.clipboard.writeText(text); toast("Copied"); } catch { toast("Select the text and copy it", "bad"); } };

  if (status === null) return <div className="empty">Loading…</div>;
  if (status === false) return null;
  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Two-step sign-in {status.enabled ? "· on" : "· off"}</div>
        <div className="panel-sub">Adds a code from your phone after your password, so a stolen password alone is not enough.</div></div></div>
      <div className="panel-body form-grid">
        {codes && (
          <div className="full note ok" role="status">
            <strong>Two-step sign-in is on. Save these recovery codes now.</strong> Each works once if you lose your phone. They will not be shown again.
            <ul className="code-grid">{codes.map((c) => <li key={c}>{c}</li>)}</ul>
            <div className="actions" style={{ marginTop: 8 }}><button type="button" className="btn ghost sm" onClick={() => copy(codes.join("\n"))}>Copy all</button><button type="button" className="btn ghost sm" onClick={() => setCodes(null)}>I have saved them</button></div>
          </div>
        )}
        {!status.enabled && !setup && (
          <form className="full form-grid" onSubmit={start}>
            <label className="field full">Your password<input className="input" type="password" autoComplete="current-password" value={f.password} onChange={set("password")} /><span className="hint">We ask again before changing how you sign in.</span></label>
            <div className="actions full"><button className="btn" disabled={busy || !f.password}>Set up two-step sign-in</button></div>
          </form>
        )}
        {setup && (
          <form className="full form-grid" onSubmit={finish}>
            <p className="full">In your authenticator app choose <em>Add account</em> and enter this key (type of key: time-based):</p>
            <code className="copy-line full">{setup.secret}</code>
            <div className="actions full"><button type="button" className="btn ghost sm" onClick={() => copy(setup.secret)}>Copy key</button>
              <a className="btn ghost sm" href={setup.uri}>Open in an authenticator app</a></div>
            <label className="field full">Then type the 6-digit code it shows<input className="input" inputMode="numeric" autoComplete="one-time-code" value={f.code} onChange={set("code")} /></label>
            <div className="actions full"><button className="btn" disabled={busy || !f.code}>Turn on</button></div>
          </form>
        )}
        {status.enabled && (
          <form className="full form-grid" onSubmit={turnOff}>
            <p className="full hint">{status.recovery_codes_left} recovery code{status.recovery_codes_left === 1 ? "" : "s"} left. To turn two-step off, confirm with your password and a current code.</p>
            <label className="field">Password<input className="input" type="password" autoComplete="current-password" value={f.password} onChange={set("password")} /></label>
            <label className="field">Code<input className="input" inputMode="numeric" autoComplete="one-time-code" value={f.code} onChange={set("code")} /></label>
            <div className="actions full"><button className="btn ghost" disabled={busy || !f.password || !f.code}>Turn off two-step sign-in</button></div>
          </form>
        )}
      </div>
    </section>
  );
}

// A store owner's own sign-in settings.
export default function AccountPanel() {
  return <div style={{ display: "grid", gap: 16 }}><PasswordSection /><TwoStepSection /></div>;
}
