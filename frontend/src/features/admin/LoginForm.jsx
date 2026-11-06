import { useState } from "react";
import { useAuth } from "../../shared/context/AuthContext.jsx";

const MODES = [["account", "Sign in"], ["create", "Create a store"], ["token", "Server admin"]];

// Three ways in: a store owner's account, creating a new store (when the server allows it), and the server admin token.
export default function LoginForm() {
  const { login, loginAccount, signup } = useAuth();
  const [mode, setMode] = useState("account");
  const [f, setF] = useState({ email: "", password: "", store: "", name: "", token: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "token") await login(f.token);
      else if (mode === "create") await signup({ email: f.email, password: f.password, store: f.store, name: f.name });
      else await loginAccount(f.email, f.password);
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
        <div className="tabs" role="tablist">
          {MODES.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={mode === id} className={mode === id ? "active" : ""} onClick={() => { setMode(id); setError(""); }}>{label}</button>)}
        </div>
        {mode === "token" ? (
          <>
            <p>The server admin manages every store.</p>
            <input className="input" type="password" placeholder="Admin token" aria-label="Admin token" autoFocus value={f.token} onChange={set("token")} />
          </>
        ) : (
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
        <button className="btn" disabled={busy || (mode === "token" ? !f.token : !f.email || !f.password)}>{busy ? "Checking…" : mode === "create" ? "Create store" : "Sign in"}</button>
        {error && <p className="err">{error}</p>}
        <a href="/" style={{ color: "var(--muted)" }}>Back to chat</a>
      </form>
    </div>
  );
}
