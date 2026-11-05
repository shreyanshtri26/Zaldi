import { useEffect, useState } from "react";
import Icon from "../../shared/components/Icon.jsx";
import { AGENT_STEPS, routeLabel } from "../../shared/utils/agentSteps.js";

// Steps shown while waiting. The API has no streaming, so progress advances on a timer and holds on the last step.
const PLAN = ["Understanding your request", "Checking store data", "Writing the answer"];

// Live task card: plan with done / current / pending steps.
export function AgentWorking() {
  const [at, setAt] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setAt((n) => Math.min(n + 1, PLAN.length - 1)), 1400);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="run-card" role="status" aria-live="polite">
      <div className="run-head"><span className="orb" aria-hidden="true" /><b>Working</b><span className="run-meta">Step {at + 1} of {PLAN.length}</span></div>
      <ol className="plan">
        {PLAN.map((label, i) => (
          <li key={label} className={i < at ? "done" : i === at ? "now" : ""}>
            <span className="plan-dot">{i < at && <Icon name="check" size={11} />}</span>{label}
          </li>
        ))}
      </ol>
      <div className="agent-bar" aria-hidden="true"><i /></div>
    </div>
  );
}

// Tool-execution card above a reply: what ran, how long it took, and the steps taken (collapsible).
export function AgentCompleted({ route, ms }) {
  const steps = AGENT_STEPS[route];
  if (!steps) return null;
  return (
    <details className="tool-card">
      <summary>
        <span className="tick"><Icon name="check" size={12} /></span>
        <span className="tool-name">{routeLabel(route)}</span>
        <span className="tool-meta">{steps.length} steps{ms ? ` · ${(ms / 1000).toFixed(1)}s` : ""}</span>
        <Icon name="chevron" size={14} />
      </summary>
      <ol className="steps">
        {steps.map(([title, detail], i) => (
          <li key={title} style={{ animationDelay: `${i * 60}ms` }}>
            <span className="tick"><Icon name="check" size={12} /></span>
            <div><b>{title}</b><span>{detail}</span></div>
          </li>
        ))}
      </ol>
    </details>
  );
}
