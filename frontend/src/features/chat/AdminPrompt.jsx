import { useState } from "react";
import { useAuth } from "../../shared/context/AuthContext.jsx";

// Shown under the reply to "@admin login": a masked password field. The password goes straight to the login
// endpoint; it is never sent to the assistant, never added to the chat history and not kept after submitting.
export default function AdminPrompt() {
  const { token, login } = useAuth();
  const [pw, setPw] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (token) return <p className="admin-ok">Admin mode is on. Use the admin button in the top bar.</p>;
  const submit = async (e) => {
    e.preventDefault();
    if (!pw || busy) return;
    setBusy(true);
    try { await login(pw); setError(""); } catch (err) { setError(/many|rate|limit/i.test(err.message) ? err.message : "Wrong password."); }
    setPw(""); setBusy(false);
  };
  return (
    <form className="admin-pass" onSubmit={submit} autoComplete="off">
      <input className="input" type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="Admin password" aria-label="Admin password" autoFocus autoComplete="off" />
      <button className="btn sm" disabled={busy || !pw}>Unlock</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  );
}
