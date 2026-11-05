import { useEffect, useMemo, useRef, useState } from "react";
import { listItems } from "../../api/client.js";

// Ctrl/Cmd+K: client-side search across products and policies (fetched once when opened).
export default function SearchDialog({ onClose, onPick }) {
  const [items, setItems] = useState([]);
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef(null);

  useEffect(() => {
    input.current?.focus();
    Promise.all([listItems("products"), listItems("policies")]).then(([p, pol]) =>
      setItems([
        ...p.map((r) => ({ view: "products", title: r.product_name, sub: `${r.category} · Rs. ${r.price}`, key: "p" + r.id })),
        ...pol.map((r) => ({ view: "policies", title: r.title, sub: "Policy", key: "s" + r.id })),
      ])).catch(() => {});
  }, []);

  const hits = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (t ? items.filter((x) => (x.title + " " + x.sub).toLowerCase().includes(t)) : items).slice(0, 8);
  }, [items, q]);
  useEffect(() => { setI(0); }, [q]);

  function onKey(e) {
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") { e.preventDefault(); setI((n) => Math.min(n + 1, hits.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setI((n) => Math.max(n - 1, 0)); }
    else if (e.key === "Enter" && hits[i]) onPick(hits[i].view, hits[i].title);
  }

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <div className="dialog" role="dialog" aria-label="Search" onKeyDown={onKey}>
        <input ref={input} className="input" placeholder="Search products and policies…" aria-label="Search workspace" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="results">
          {hits.map((h, n) => (
            <button key={h.key} className={`result${n === i ? " active" : ""}`} onMouseEnter={() => setI(n)} onClick={() => onPick(h.view, h.title)}>
              <span className={`badge ${h.view === "products" ? "teal" : "warn"}`}>{h.view === "products" ? "Product" : "Policy"}</span>
              <span><b style={{ fontWeight: 500 }}>{h.title}</b><small>{h.sub}</small></span>
            </button>
          ))}
          {!hits.length && <div className="empty">Nothing found</div>}
        </div>
      </div>
    </>
  );
}
