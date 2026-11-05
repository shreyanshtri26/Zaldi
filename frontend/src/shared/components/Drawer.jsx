import { useEffect } from "react";
import Icon from "./Icon.jsx";

// Right-hand slide-over used for the product / policy editors. Esc or backdrop click closes it.
export default function Drawer({ title, onClose, onSubmit, saving, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label={title}>
        <header>{title}<span className="spacer" /><button className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="x" /></button></header>
        <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
          <div className="fields">{children}</div>
          <footer>
            <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
            <button className="btn" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </footer>
        </form>
      </aside>
    </>
  );
}
