import { useState } from "react";
import { forgotPassword, resetPassword } from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";

const MODES = [["account", "Sign in"], ["create", "Create a store"], ["token", "Server admin"]];
const resetToken = () => { try { return new URLSearchParams(window.location.search).get("reset") || ""; } catch { return ""; } };

// Sign-in, in four moods: a store owner's account (with an optional second step), creating a store, the server admin's password,
// and getting back in (forgot password, or the page a reset link opens).
export default function LoginForm() {
  const { login, loginAccount, finishTwoStep, signup } = useAuth();
  const [mode, setMode] = useState(resetToken() ? "reset" : "account");
  const [f, setF] = useState({ email: "", password: "", store: "", name: "", token: "", code: "", next: "", again: "" });
  const [challenge, setChallenge] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const go = (next) => { setMode(next); setError(""); setMessage(""); setChallenge(null); };

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "token") await login(f.token);
      else if (mode === "create") await signup({ email: f.email, password: f.password, store: f.store, name: f.name });
      else if (mode === "forgot") {
        const out = await forgotPassword(f.email);
        setMessage(out.email_enabled ? "If that email has an account, a reset link is on its way. It works for one hour." : "This server does not send email. Ask your server admin for a reset link.");
      } else if (mode === "reset") {
        if (f.next !== f.again) throw new Error("The two passwords are not the same.");
        await resetPassword(resetToken(), f.next);
        window.history.replaceState({}, "", "/admin");
        setF({ ...f, next: "", again: "", password: "" });
        setMode("account");
        setMessage("Password changed. Sign in with the new one.");
      } else if (challenge) await finishTwoStep(challenge, f.code);
      else { const step = await loginAccount(f.email, f.password); if (step) setChallenge(step.challenge); }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const tabs = mode !== "forgot" && mode !== "reset";
  const ready = mode === "token" ? f.token : mode === "forgot" ? f.email : mode === "reset" ? f.next && f.again : challenge ? f.code : f.email && f.password;
  const label = mode === "create" ? "Create store" : mode === "forgot" ? "Send reset link" : mode === "reset" ? "Set new password" : challenge ? "Verify" : "Sign in";
  return (
    <div className="login">
      <form onSubmit={submit}>
        <span className="mark lg" role="img" aria-label="Zaldi" style={{ margin: "0 auto" }} />
        <h2>{mode === "forgot" ? "Reset your password" : mode === "reset" ? "Choose a new password" : "Zaldi admin"}</h2>
        {tabs && (
          <div className="tabs" role="tablist">
            {MODES.map(([id, text]) => <button key={id} type="button" role="tab" aria-selected={mode === id} className={mode === id ? "active" : ""} onClick={() => go(id)}>{text}</button>)}
          </div>
        )}
        {message && <p className="note ok" role="status">{message}</p>}
        {mode === "token" && (
          <>
            <p>The server admin manages every store.</p>
            <input className="input" type="password" placeholder="Admin password or token" aria-label="Admin token" autoFocus value={f.token} onChange={set("token")} />
          </>
        )}
        {mode === "forgot" && (
          <>
            <p>Enter your account email. We will send a link if the server can send email.</p>
            <input className="input" type="email" placeholder="Email" aria-label="Email" autoFocus value={f.email} onChange={set("email")} />
          </>
        )}
        {mode === "reset" && (
          <>
            <input className="input" type="password" placeholder="New password (10+ characters)" aria-label="New password" autoFocus value={f.next} onChange={set("next")} />
            <input className="input" type="password" placeholder="New password again" aria-label="New password again" value={f.again} onChange={set("again")} />
          </>
        )}
        {(mode === "account" || mode === "create") && !challenge && (
          <>
            <p>{mode === "create" ? "Set up your own store. You will be its owner." : "Sign in to manage your store."}</p>
            {mode === "create" && (
              <>
                <input className="input" placeholder="Store name" aria-label="Store name" value={f.name} onChange={set("name")} />
                <input className="input" placeholder="Store id (letters, digits, dashes)" aria-label="Store id" value={f.store} onChange={set("store")} />
              </>
            )}
            <input className="input" type="email" placeholder="Email" aria-label="Email" autoFocus value={f.email} onChange={set("email")} />
            <input className="input" type="password" placeholder={mode === "create" ? "Password (10+ characters)" : "Password"} aria-label="Password" value={f.password} onChange={set("password")} />
          </>
        )}
        {challenge && (
          <>
            <p>Enter the 6-digit code from your authenticator app. Lost your phone? Use one of your recovery codes instead.</p>
            <input className="input" inputMode="numeric" autoComplete="one-time-code" placeholder="123456 or a recovery code" aria-label="Code" autoFocus value={f.code} onChange={set("code")} />
          </>
        )}
        <button className="btn" disabled={busy || !ready}>{busy ? "Checking…" : label}</button>
        {error && <p className="err">{error}</p>}
        {mode === "account" && !challenge && <button type="button" className="link-btn" onClick={() => go("forgot")}>Forgot your password?</button>}
        {(mode === "forgot" || challenge) && <button type="button" className="link-btn" onClick={() => go("account")}>Back to sign in</button>}
        <a href="/" style={{ color: "var(--muted)" }}>Back to chat</a>
      </form>
    </div>
  );
}
