import Orb from "./Orb.jsx";

// The assistant's avatar in chat: the small Zaldi orb. It shows the thinking state while a reply is being prepared.
export default function BotAvatar({ size = 30, active = false }) {
  return <Orb size={size} state={active ? "processing" : "idle"} />;
}
