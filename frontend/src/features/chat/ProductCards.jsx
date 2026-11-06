import { hue, money } from "../../shared/utils/format.js";

// Product results under a reply. "Add" goes straight to the cart API (the same cart the chat edits); once a product is in the cart
// the button becomes a - 1 + stepper, so quantity can be changed right here without opening the cart.
const MAX_LINE = 10;

export default function ProductCards({ products, onAdd, onSetQty, cartQty = {}, busyId }) {
  if (!products?.length) return null;
  return (
    <div className="p-grid">
      {products.map((p, i) => (
        <article key={p.id} className="p-card" style={{ animationDelay: `${i * 50}ms` }}>
          <div className={`p-thumb${p.catalogue_only ? " contain" : ""}`} style={p.image_url ? undefined : { background: `linear-gradient(135deg, hsl(${hue(p.product_name)} 45% 32%), hsl(${(hue(p.product_name) + 40) % 360} 50% 18%))` }}>
            {p.image_url ? <img src={p.image_url} alt={p.product_name} decoding="async" /> : <span>{p.category}</span>}
            <b className="p-num">{i + 1}</b>
          </div>
          <div className="p-body">
            <h4>{p.product_name}</h4>
            <p>{[p.brand, p.color].filter(Boolean).join(" · ")}</p>
            <div className="p-foot">
              <strong>{money(p.price, p.currency)}</strong>
              {p.catalogue_only ? null : p.buy_url ? (
                <a className="btn sm" href={p.buy_url} target="_blank" rel="noopener noreferrer">View &amp; buy</a>
              ) : (
                (cartQty[p.id] || 0) > 0 ? (
                  <div className="qty" role="group" aria-label={`Quantity of ${p.product_name} in your cart`}>
                    <button aria-label="Decrease quantity" disabled={busyId === p.id} onClick={() => onSetQty(p, cartQty[p.id] - 1)}>−</button>
                    <span aria-live="polite">{cartQty[p.id]}</span>
                    <button aria-label="Increase quantity" disabled={busyId === p.id || cartQty[p.id] >= Math.min(p.stock_quantity ?? MAX_LINE, MAX_LINE)} onClick={() => onSetQty(p, cartQty[p.id] + 1)}>+</button>
                  </div>
                ) : (
                  <button className="btn sm" disabled={busyId === p.id || p.stock_quantity < 1} onClick={() => onAdd(p)}>
                    {p.stock_quantity < 1 ? "Sold out" : busyId === p.id ? "Adding…" : "Add"}
                  </button>
                )
              )}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
