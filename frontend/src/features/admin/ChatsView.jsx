import { useState } from "react";
import { AGENT_STEPS, routeLabel } from "../../shared/utils/agentSteps.js";
import Icon from "../../shared/components/Icon.jsx";

// Master/detail transcript viewer. Data comes from /admin/stats (the 20 most recent chats).
export default function ChatsView({ chats }) {
  const [selectedId, setSelectedId] = useState(null);
  const current = chats.find((c) => c.id === selectedId) || chats[0];
  return (
    <div className="col-wide">
      <div className="page-head"><div><h2>Chats</h2><p>Recent customer conversations and how the assistant handled them.</p></div></div>
      {!chats.length ? <div className="card empty">No chats yet. Questions asked on the chat page will show up here.</div> : (
        <div className="split">
          <div className="card qlist" style={{ padding: 8 }}>
            {chats.map((c) => (
              <button key={c.id} className={`qitem${c.id === current.id ? " active" : ""}`} onClick={() => setSelectedId(c.id)}>
                <b>{c.query}</b><span>{c.created_at} · {routeLabel(c.route)}</span>
              </button>
            ))}
          </div>
          <div className="card">
            <h3 style={{ margin: "0 0 4px" }}>Customer</h3>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{current.query}</p>
            <h3 style={{ margin: "20px 0 4px" }}>Zaldi</h3>
            <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{current.response}</p>
            <div className="agent-run">
              <div className="agent-run-head"><b>Execution timeline</b><span className="status done"><Icon name="check" size={12} /> Completed</span></div>
              <ol className="steps">
                {(AGENT_STEPS[current.route] || []).map(([title, detail]) => (
                  <li key={title}><span className="tick"><Icon name="check" size={12} /></span><div><b>{title}</b><span>{detail}</span></div></li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
