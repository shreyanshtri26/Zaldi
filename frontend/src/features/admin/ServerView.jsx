import { useState } from "react";
import { changeServerPassword, copyDatabase, removeDatabase, removeServerPassword, restartServer, saveDatabase, testDatabase } from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useToast } from "../../shared/context/ToastContext.jsx";

function PasswordSection({ info, onChange }) {
  const { token, login } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", again: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const portal = info.source === "portal";

  async function save(e) {
    e.preventDefault();
    if (f.next !== f.again) { toast("The two new passwords are not the same.", "bad"); return; }
    setBusy(true);
    try {
      onChange(await changeServerPassword(f.current, f.next, token));
      await login(f.next); // keep this browser signed in with the new password
      setF({ current: "", next: "", again: "" });
      toast("Admin password changed");
    } catch (err) { toast(err.message, "bad"); } finally { setBusy(false); }
  }
  async function remove() {
    if (!f.current) { toast("Type the current password first.", "bad"); return; }
    setBusy(true);
    try { onChange(await removeServerPassword(f.current, token)); await login(f.current); setF({ ...f, current: "" }); toast("Back to the ADMIN_TOKEN from the server's environment"); }
    catch (err) { toast(err.message, "bad"); } finally { setBusy(false); }
  }
  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Admin password</div>
        <div className="panel-sub">{portal ? "You set a password in this portal. " : "The server uses its ADMIN_TOKEN setting. "}Set your own here and you never need to edit the host's settings again.</div></div></div>
      <form className="panel-body form-grid" onSubmit={save}>
        <label className="field full">Current password<input className="input" type="password" autoComplete="current-password" value={f.current} onChange={set("current")} /></label>
        <label className="field">New password<input className="input" type="password" autoComplete="new-password" value={f.next} onChange={set("next")} />
          <span className="hint">At least {info.min_length} characters.</span></label>
        <label className="field">New password again<input className="input" type="password" autoComplete="new-password" value={f.again} onChange={set("again")} /></label>
        {info.environment_token_set && <p className="hint full">The ADMIN_TOKEN in the server's environment keeps working as a recovery key if you forget this password. Remove it from the host's settings when you want only the portal password to work.</p>}
        <div className="actions full">
          <button className="btn" disabled={busy || !f.current || !f.next}>Change password</button>
          {portal && <button type="button" className="btn ghost" disabled={busy || !f.current} onClick={remove}>Go back to the environment token</button>}
        </div>
      </form>
    </section>
  );
}

function DatabaseSection({ info, onChange }) {
  const { token } = useAuth();
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(null);
  const [replace, setReplace] = useState(false);
  const [typed, setTyped] = useState("");
  const [restartTyped, setRestartTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const running = info.backend === "postgres" ? `Postgres at ${info.host}${info.database ? ` / ${info.database}` : ""}` : "SQLite files on this server's disk";

  async function run(action, after) {
    setBusy(true);
    try { return await action(); } catch (err) { toast(err.message, "bad"); return null; } finally { setBusy(false); after?.(); }
  }
  const test = async () => { setResult(null); setCopied(null); const out = await run(() => testDatabase(url, token)); if (out) setResult(out); };
  const copy = async () => {
    const out = await run(() => copyDatabase(url, replace, replace ? typed : undefined, token));
    if (out) { setCopied(out.report); toast("Data copied"); }
  };
  const save = async () => { const out = await run(() => saveDatabase(url, token)); if (out) { onChange({ database: out.database }); toast("Saved. Restart the server to start using it."); } };
  const clear = async () => { const out = await run(() => removeDatabase(token)); if (out) { onChange({ database: out.database }); toast("Saved address removed"); } };
  const restart = async () => { const out = await run(() => restartServer("RESTART", token)); if (out) toast(out.message); };

  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Database</div>
        <div className="panel-sub">Running on: {running}. {info.source === "environment" ? "Set by the server's DATABASE_URL." : info.source === "portal" ? "Set in this portal." : ""}</div></div></div>
      <div className="panel-body form-grid">
        {info.environment_overrides && <div className="full note bad">The server's DATABASE_URL environment setting overrides the address saved here. Remove it from the host's settings to use the saved one.</div>}
        {info.restart_needed && (
          <div className="full note ok">An address is saved ({info.saved?.host}). It is used after a restart.
            <div className="actions" style={{ marginTop: 8 }}>
              <input className="input" placeholder="Type RESTART" value={restartTyped} onChange={(e) => setRestartTyped(e.target.value)} style={{ maxWidth: 160 }} />
              <button type="button" className="btn" disabled={busy || restartTyped !== "RESTART"} onClick={restart}>Restart now</button>
            </div>
            <span className="hint">On a hosted server this restarts it by itself. Running on your own computer, it stops and you start it again.</span>
          </div>
        )}
        <label className="field full">Postgres address
          <input className="input" type="password" autoComplete="off" value={url} onChange={(e) => { setUrl(e.target.value); setResult(null); setCopied(null); }}
            placeholder="postgresql://user:password@host/database?sslmode=require" />
          <span className="hint">For Neon, copy the pooled connection string from the dashboard. The address is only sent to your own server, and never shown again.</span>
        </label>
        <div className="actions full">
          <button type="button" className="btn ghost" disabled={busy || !url.trim()} onClick={test}>Test connection</button>
        </div>
        {result && <div className={`full note ${result.ok ? "ok" : "bad"}`} role="status">{result.ok ? `Connected to ${result.host}${result.database ? ` / ${result.database}` : ""} (Postgres ${result.version}). ${result.has_data ? "It already contains Zaldi data." : "It is empty."}` : result.message}</div>}
        {result?.ok && (
          <>
            <div className="field full">Move your data
              <span className="hint">Copies every store from this server's SQLite files into that database. Your files here are not changed, and the search index rebuilds on the first search.</span>
            </div>
            {result.has_data && (
              <label className="field full" style={{ gridTemplateColumns: "auto 1fr", alignItems: "center", gap: 8 }}>
                <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
                <span>Erase what is in that database and replace it with this server's data</span>
              </label>
            )}
            {replace && <input className="input full" placeholder="Type REPLACE to confirm" value={typed} onChange={(e) => setTyped(e.target.value)} />}
            <div className="actions full">
              <button type="button" className="btn ghost" disabled={busy || (result.has_data && !(replace && typed === "REPLACE"))} onClick={copy}>{busy ? "Working…" : "Copy my data"}</button>
              <button type="button" className="btn" disabled={busy} onClick={save}>Save and use after restart</button>
            </div>
          </>
        )}
        {copied && <div className="full note ok" role="status"><strong>Copied.</strong><ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{copied.map((line, i) => <li key={i}>{line}</li>)}</ul></div>}
        {info.saved_in_portal && <div className="actions full"><button type="button" className="btn ghost" disabled={busy} onClick={clear}>Remove the saved address</button></div>}
      </div>
    </section>
  );
}

// Settings for the whole server. Only the server admin gets here (the nav item is hidden for store owners).
export default function ServerView({ server, onChange }) {
  return (
    <div className="col-wide" style={{ display: "grid", gap: 16 }}>
      <div className="page-head"><div><h2>Server</h2><p>Settings for the whole server, not one shop. Only the server admin sees this page.</p></div></div>
      <PasswordSection info={server.admin_password} onChange={onChange} />
      <DatabaseSection info={server.database} onChange={onChange} />
    </div>
  );
}
