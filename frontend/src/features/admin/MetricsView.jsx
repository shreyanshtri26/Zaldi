import { useEffect, useState } from "react";
import { getMetrics } from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import Skeleton from "../../shared/components/Skeleton.jsx";

const usd = (n) => `$${(n || 0).toFixed(n && n < 0.01 ? 4 : 2)}`;

function Tile({ label, value, note }) {
  return <div className="card stat"><span>{label}</span><b>{value}</b>{note && <small>{note}</small>}</div>;
}

// Quality, speed and cost of the assistant over the last few days, from what every chat recorded.
export default function MetricsView() {
  const { token } = useAuth();
  const [days, setDays] = useState(7);
  const [m, setM] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { setM(null); getMetrics(token, days).then(setM).catch((e) => setError(e.message)); }, [token, days]);
  if (error) return <div className="card empty">{error}</div>;
  if (!m) return <Skeleton cards={4} />;
  const checks = m.self_check;
  const variants = Object.entries(m.feedback);
  return (
    <div className="col-wide">
      <div className="page-head">
        <div><h2>Metrics</h2><p>How the assistant is doing: speed, cost, accuracy checks and shopper feedback.</p></div>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period">
          {[1, 7, 30].map((d) => <option key={d} value={d}>Last {d} day{d > 1 ? "s" : ""}</option>)}
        </select>
      </div>
      <div className="stat-grid">
        <Tile label="Chats" value={m.chats} note={`${m.agent_chats} handled by the agent`} />
        <Tile label="Speed (median / slowest 5%)" value={`${m.latency_ms.p50} / ${m.latency_ms.p95} ms`} />
        <Tile label="Estimated cost" value={usd(m.cost_usd)} note={`${usd(m.cost_usd_per_agent_chat)} per agent chat`} />
        <Tile label="Tokens used" value={m.tokens.toLocaleString()} />
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Answer check</h3>
        <p className="muted">Every agent answer is checked against what the tools returned. "Repaired" means a price was wrong and the model fixed it; "Replaced" means it could not, so a plain summary was shown.</p>
        <p>{checks.ok} passed · {checks.repaired} repaired · {checks.fallback} replaced · {checks.ask} questions asked</p>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Tools</h3>
        {!m.tools.length ? <p className="muted">No tool calls in this period.</p> : (
          <table className="table"><thead><tr><th>Tool</th><th>Calls</th><th>Failed</th><th>Average</th></tr></thead>
            <tbody>{m.tools.map((t) => <tr key={t.tool}><td>{t.tool}</td><td>{t.calls}</td><td>{t.failures}</td><td>{t.avg_ms} ms</td></tr>)}</tbody></table>
        )}
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Shopper feedback{variants.length > 1 ? " by prompt version" : ""}</h3>
        {!variants.length ? <p className="muted">No thumbs up or down yet.</p> : variants.map(([v, f]) => (
          <p key={v}>Version {v}: {f.up} up, {f.down} down{f.up + f.down ? ` (${Math.round((100 * f.up) / (f.up + f.down))}% positive)` : ""}</p>
        ))}
      </div>
    </div>
  );
}
