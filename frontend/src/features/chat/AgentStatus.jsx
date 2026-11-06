import Icon from "../../shared/components/Icon.jsx";
import { AGENT_STEPS, routeLabel } from "../../shared/utils/agentSteps.js";

// Compact waiting box: a title and blurred lines that "type" themselves. The API has no streaming, so there is no real
// progress to show; a short note appears only if the reply is slow.
export function AgentWorking() {
  return (
    <div className="run-card" role="status" aria-live="polite">
      <div className="typing" aria-hidden="true"><i /><i /><i /><i /></div>
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
