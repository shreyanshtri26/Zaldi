import { useState } from "react";
import { useAuth } from "../../shared/context/AuthContext.jsx";

// Shown under the reply to "@admin login": a masked password field. The password goes straight to the login
// endpoint; it is never sent to the assistant, never added to the chat history and not kept after submitting.
export default function AdminPrompt() {
  const { token, login } = useAuth();
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  if (token) return <p className="admin-ok">Admin mode is on. Use the admin button in the top bar.</p>;
  const submit = async (e) => {
    e.preventDefault();
    if (!pw || busy) return;
    setBusy(true);
    try { await login(pw); setError(""); } catch (err) { setError(/invalid/i.test(err.message) ? "Wrong password." : /many|rate|limit/i.test(err.message) ? err.message : "Could not reach the server. Wait a few seconds and try again."); }
    setPw(""); setBusy(false);
  };
  return (
    <form className="admin-pass" onSubmit={submit} autoComplete="off">
      <span className="pw-field">
        <input className="input" type={show ? "text" : "password"} value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Admin password" aria-label="Admin password" autoFocus autoComplete="off" />
        <button type="button" className="icon-btn" aria-label={show ? "Hide password" : "Show password"} aria-pressed={show} onClick={() => setShow(!show)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" />{show && <path d="M3 3l18 18" />}
          </svg>
        </button>
      </span>
      <button className="btn sm" disabled={busy || !pw}>Unlock</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  );
}
