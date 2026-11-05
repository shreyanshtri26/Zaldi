// Renders "What's on *your mind*?" with the starred part in the accent colour (React escapes the text).
export default function Accent({ text }) {
  return String(text).split(/\*([^*]+)\*/).map((part, i) => (i % 2 ? <em key={i} className="accent">{part}</em> : part));
}
