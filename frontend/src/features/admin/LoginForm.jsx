import { useState } from "react";
import { useAuth } from "../../shared/context/AuthContext.jsx";

export default function LoginForm() {
  const { login } = useAuth();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(token);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form onSubmit={submit}>
        <span className="mark lg" role="img" aria-label="Zaldi" style={{ margin: "0 auto" }} />
        <h2>Zaldi admin</h2>
        <p>Enter the admin token to manage products, policies and chats.</p>
        <input className="input" type="password" placeholder="Admin token" aria-label="Admin token" autoFocus
          value={token} onChange={(e) => setToken(e.target.value)} />
        <button className="btn" disabled={busy || !token}>{busy ? "Checking…" : "Sign in"}</button>
        {error && <p className="err">{error}</p>}
        <a href="/" style={{ color: "var(--muted)" }}>Back to chat</a>
      </form>
    </div>
  );
}
