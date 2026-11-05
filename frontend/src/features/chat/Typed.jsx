import { useEffect, useState } from "react";

// Reveals a reply word by word, each word easing from blurred to sharp. All words are rendered up front (transparent),
// so the bubble keeps its final height and nothing jumps while it types. Skipped for reduced motion and old messages.
export default function Typed({ text, animate, onDone }) {
  const tokens = text.split(/(\s+)/); // words and the whitespace between them
  const [shown, setShown] = useState(animate ? 0 : tokens.length);

  useEffect(() => {
    if (!animate) return;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setShown(tokens.length); onDone?.(); return; }
    const step = Math.max(1, Math.ceil(tokens.length / 80)); // long answers still finish in about 3 seconds
    let at = 0;
    const timer = setInterval(() => {
      at = Math.min(at + step, tokens.length);
      setShown(at);
      if (at >= tokens.length) { clearInterval(timer); onDone?.(); }
    }, 38);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return tokens.map((t, i) => <span key={i} className={i < shown ? "w on" : "w"}>{t}</span>);
}
