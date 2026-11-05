import { hue, inr } from "../../shared/utils/format.js";

// Product results under a reply. "Add" goes straight to the cart API (the same cart the chat edits).
export default function ProductCards({ products, onAdd, busyId }) {
  if (!products?.length) return null;
  return (
    <div className="p-grid">
      {products.map((p, i) => (
        <article key={p.id} className="p-card" style={{ animationDelay: `${i * 50}ms` }}>
          <div className="p-thumb" style={p.image_url ? undefined : { background: `linear-gradient(135deg, hsl(${hue(p.product_name)} 45% 32%), hsl(${(hue(p.product_name) + 40) % 360} 50% 18%))` }}>
            {p.image_url ? <img src={p.image_url} alt={p.product_name} decoding="async" /> : <span>{p.category}</span>}
            <b className="p-num">{i + 1}</b>
          </div>
          <div className="p-body">
            <h4>{p.product_name}</h4>
            <p>{[p.brand, p.color].filter(Boolean).join(" · ")}</p>
            <div className="p-foot">
              <strong>{inr(p.price)}</strong>
              <button className="btn sm" disabled={busyId === p.id || p.stock_quantity < 1} onClick={() => onAdd(p)}>
                {p.stock_quantity < 1 ? "Sold out" : busyId === p.id ? "Adding…" : "Add"}
              </button>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
