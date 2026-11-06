import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icon from "../../shared/components/Icon.jsx";
import { hue } from "../../shared/utils/format.js";

export const label = (name) => name.charAt(0).toUpperCase() + name.slice(1);
// "Sarees" and "Saree" are the same category: used to avoid showing a help shortcut that duplicates a category card
export const norm = (text) => text.toLowerCase().replace(/[^a-z]/g, "").replace(/s$/, "");
const GROUP_ORDER = ["Women", "Men", "Kids", "Everyone", "Unisex", "More"];
// Departments in a fixed order; a category the store gave an unknown group goes under "More".
const groupsOf = (list) => GROUP_ORDER.map((g) => [g, list.filter((c) => (GROUP_ORDER.includes(c.group) ? c.group : "More") === g)]).filter(([, l]) => l.length);

// One category as a woven-fabric tile. Its product photo fills the tile when the store has one; otherwise a textile motif
// (bandhani dots, ikat stripes, block-print diamonds, zari lines, weave, scallops) picked from the name, so each category looks distinct.
const MOTIFS = 6;
function CategoryCard({ c, onPick }) {
  const h = hue(c.name);
  const [broken, setBroken] = useState(false);
  const photo = c.image && !broken;
  return (
    <button className={`cat-tile fabric motif-${h % MOTIFS}${photo ? " has-photo" : ""}`} style={{ "--h": h }} onClick={() => onPick(c.name)}
      aria-label={label(c.name)}>
      {photo && <img src={c.image} alt="" decoding="async" referrerPolicy="no-referrer" onError={() => setBroken(true)} />}
      <span className="cat-name" aria-hidden="true">{label(c.name)}</span>
    </button>
  );
}

// Every category, grouped by department, with a filter box.
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
    return groupsOf(categories.filter((c) => c.name.toLowerCase().includes(q)));
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
              <div className="cat-grid">{list.map((c) => <CategoryCard key={c.name} c={c} onPick={onPick} />)}</div>
            </section>
          ))}
          {!groups.length && <p className="empty">No category matches "{query}".</p>}
        </div>
      </aside>
    </>
  );
}

// Home page: a "Shop by category" button. Hovering or focusing it (or tapping it on a phone) reveals the category tiles beneath it.
// `children` are the help shortcuts (Payment, Returns...) that sit on the same line as the button.
export default function CategoryChips({ categories, shown, onPick, children }) {
  const [all, setAll] = useState(false);
  const [hover, setHover] = useState(false);
  const [pinned, setPinned] = useState(false); // a click or tap keeps it open (touch screens have no hover)
  const open = hover || pinned;
  if (!categories.length) return children ? <div className="chips help-line">{children}</div> : null;
  const top = categories.slice(0, shown);
  return (
    <section className={`cats${open ? " open" : ""}`} aria-label="Shop by category" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      onKeyDown={(e) => e.key === "Escape" && setPinned(false)}>
      <div className="cats-line">
        <button className="chip cats-trigger" aria-expanded={open} aria-controls="cats-reveal" onClick={() => setPinned((v) => !v)}>
          Shop by category<Icon name="chevron" size={14} />
        </button>
        {children}
      </div>
      <div id="cats-reveal" className="cats-reveal" inert={!open || undefined}>
        <div className="cats-reveal-head"><button className="cats-all" aria-haspopup="dialog" onClick={() => setAll(true)}>See all {categories.length}<Icon name="chevronRight" size={14} /></button></div>
        <div className="cat-rail">{top.map((c) => <CategoryCard key={c.name} c={c} onPick={onPick} />)}</div>
      </div>
      {/* in a portal: the welcome block is animated, and a transformed parent would trap this fixed panel inside it */}
      {all && createPortal(<CategoryPanel categories={categories} onClose={() => setAll(false)} onPick={(name) => { setAll(false); onPick(name); }} />, document.body)}
    </section>
  );
}
