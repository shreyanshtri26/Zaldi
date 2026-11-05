import { useState, type FormEvent } from "react";
import { Button, Card } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";

export default function Login() {
  const { login } = useAuth();
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try { await login(token.trim()); } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <Card className="w-full max-w-sm p-6">
        <img src="/zaldi_mark.svg" alt="" className="mb-4 h-10 w-10 rounded-lg bg-white p-1.5" />
        <h1 className="text-xl font-bold">Merchant Control Center</h1>
        <p className="mb-5 mt-1 text-ink2">Enter your admin token to continue.</p>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="label" htmlFor="token">Admin token</label>
            <input id="token" type="password" className="input" value={token} onChange={(e) => setToken(e.target.value)} autoFocus />
          </div>
          {error && <p role="alert" className="text-bad">{error}</p>}
          <Button className="w-full" loading={busy} disabled={!token.trim()}>Sign in</Button>
        </form>
      </Card>
    </div>
  );
}
