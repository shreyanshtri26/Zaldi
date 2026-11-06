import { useEffect, useMemo, useRef, useState } from "react";
import Icon from "../../shared/components/Icon.jsx";

export const label = (name) => name.charAt(0).toUpperCase() + name.slice(1);
// "Sarees" and "Saree" are the same category: used to avoid showing a help shortcut that duplicates a category chip
export const norm = (text) => text.toLowerCase().replace(/[^a-z]/g, "").replace(/s$/, "");
const GROUP_ORDER = ["Women", "Men", "Kids", "Unisex", "More"];

// Every category, grouped, with a filter box: for when the catalogue has more categories than fit on the home page.
function CategoryPanel({ categories, onPick, onClose }) {
  const [query, setQuery] = useState("");
  const input = useRef(null);
  useEffect(() => {
    input.current?.focus();
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const found = categories.filter((c) => c.name.toLowerCase().includes(q));
    return GROUP_ORDER.map((g) => [g, found.filter((c) => (GROUP_ORDER.includes(c.group) ? c.group : "More") === g)]).filter(([, list]) => list.length);
  }, [categories, query]);

  return (
    <>
      <div className="overlay" onClick={onClose} />
      <aside className="drawer cat-panel" role="dialog" aria-label="All categories">
        <header>All categories<span className="spacer" /><button className="icon-btn" aria-label="Close" onClick={onClose}><Icon name="x" /></button></header>
        <div className="fields">
          <label className="sr" htmlFor="cat-filter">Filter categories</label>
          <input id="cat-filter" ref={input} className="input" placeholder="Filter categories" value={query} onChange={(e) => setQuery(e.target.value)} />
          {groups.map(([group, list]) => (
            <section key={group} aria-label={group}>
              <h3 className="cat-group">{group}</h3>
              <div className="chips left">
                {list.map((c) => <button key={c.name} className="chip cat" onClick={() => onPick(c.name)}>{label(c.name)}<small>{c.count}</small></button>)}
              </div>
            </section>
          ))}
          {!groups.length && <p className="empty">No category matches "{query}".</p>}
        </div>
      </aside>
    </>
  );
}

export default function CategoryChips({ categories, shown, onPick, align }) {
  const [open, setOpen] = useState(false);
  const [peek, setPeek] = useState(false); // collapsed until hovered, focused or tapped
  if (!categories.length) return null;
  const top = categories.slice(0, shown);
  return (
    <section className={`cats${peek ? " open" : ""}`} aria-label="Shop by category" onMouseEnter={() => setPeek(true)} onMouseLeave={() => setPeek(false)}>
      <button className="cats-label" aria-expanded={peek} onClick={() => setPeek((v) => !v)}>Shop by category<Icon name="chevron" size={13} /></button>
      <div className={`chips cats-row ${align}`}>
        {top.map((c) => <button key={c.name} className="chip cat" onClick={() => onPick(c.name)}>{label(c.name)}<small>{c.count}</small></button>)}
        {categories.length > top.length && <button className="chip cat all" aria-haspopup="dialog" onClick={() => setOpen(true)}>All {categories.length}<Icon name="chevronRight" size={14} /></button>}
      </div>
      {open && <CategoryPanel categories={categories} onClose={() => setOpen(false)} onPick={(name) => { setOpen(false); onPick(name); }} />}
    </section>
  );
}
