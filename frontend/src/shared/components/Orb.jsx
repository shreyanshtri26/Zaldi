import Smoke from "./Smoke.jsx";

const LABEL = { idle: "ready", listening: "listening", processing: "thinking", responding: "replying", inactive: "offline" };

// Zaldi's signature orb. `state` drives every animation through CSS (data-state); `smoke` adds the WebGL vapour behind it.
// Small orbs (chat avatars) skip the breathing and smoke so a long conversation stays quiet and cheap.
export default function Orb({ state = "idle", size = 80, smoke = false }) {
  return (
    <span className="orb3d" data-state={state} data-small={size < 40 || undefined} style={{ "--orb": `${size}px` }}
      role="img" aria-label={`Zaldi assistant, ${LABEL[state]}`}>
      {smoke && <Smoke state={state} />}
      <span className="orb-body" />
      <span className="orb-thread" />
    </span>
  );
}
