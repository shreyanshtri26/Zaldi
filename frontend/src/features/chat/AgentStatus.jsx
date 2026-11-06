import Icon from "../../shared/components/Icon.jsx";
import { routeLabel, stepsFor } from "../../shared/utils/agentSteps.js";

// Compact waiting box: blurred lines that "type" themselves, and under them each tool step as soon as it finishes
// (for example "Found 6 products for kurta"), so a slow answer shows real progress.
export function AgentWorking({ steps = [] }) {
  return (
    <div className="run-card" role="status" aria-live="polite">
      <div className="typing" aria-hidden="true"><i /><i /><i /><i /></div>
      {steps.length > 0 && (
        <ul className="live-steps">
          {steps.slice(-4).map((s, i) => <li key={`${s.tool}-${i}`} className={s.ok === false ? "bad" : ""}>{s.summary}</li>)}
        </ul>
      )}
    </div>
  );
}

// Tool-execution card above a reply: what ran, how long it took, and the steps taken (collapsible).
export function AgentCompleted({ route, ms, steps: ran }) {
  const steps = stepsFor(route, ran);
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
