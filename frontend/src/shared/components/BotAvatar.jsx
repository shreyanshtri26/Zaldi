import Icon from "./Icon.jsx";

// The AI chatbot symbol: used as the assistant's avatar in chat.
export default function BotAvatar({ size = 30, active = false }) {
  return (
    <span className={`bot-avatar${active ? " active" : ""}`} style={{ width: size, height: size }} role="img" aria-label="Zaldi AI">
      <Icon name="bot" size={Math.round(size * 0.62)} />
    </span>
  );
}
