import { useEffect, useState } from "react";
import { listItems } from "../../api/client.js";
import Icon from "../../shared/components/Icon.jsx";
import StockBadge from "./StockBadge.jsx";

const LOW = 10;
const LANGUAGES = ["English", "Hindi", "Hinglish"];

export default function Dashboard({ stats, onNavigate }) {
  const [lowStock, setLowStock] = useState(null); // null = still loading
  useEffect(() => {
    listItems("products")
      .then((rows) => setLowStock(rows.filter((p) => p.stock_quantity < LOW).sort((a, b) => a.stock_quantity - b.stock_quantity)))
      .catch(() => setLowStock([]));
  }, []);

  const cards = [["Products", stats.products, "products"], ["Policies", stats.policies, "policies"], ["Chats", stats.chats, "chats"]];
  return (
    <div className="col-wide dash">
      <div className="page-head">
        <div><h2>Overview</h2><p>What is happening in your store assistant today.</p></div>
      </div>

      <section className="assistant-card">
        <span className="agent-orb"><Icon name="bot" size={22} /></span>
        <div className="assistant-copy">
          <h3>Zaldi assistant</h3>
          <p>Answers customer questions from your products and policies. Edit the content here and it is used right away.</p>
        </div>
        <ul className="langs" aria-label="Supported languages">{LANGUAGES.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>

      <div className="stats">
        {cards.map(([label, value, view]) => (
          <button key={label} className="stat-card" onClick={() => onNavigate(view)} aria-label={`${value} ${label}, open ${label}`}>
            <span className="stat-num">{value}</span><span className="stat-label">{label}</span><Icon name="chevronRight" size={16} />
          </button>
        ))}
        <button className={`stat-card${stats.low_stock ? " hot" : ""}`} onClick={() => onNavigate("products")} aria-label={`${stats.low_stock} low stock items, open Products`}>
          <span className="stat-num">{stats.low_stock}</span><span className="stat-label">Low stock items</span><Icon name="chevronRight" size={16} />
        </button>
      </div>

      <div className="grid-2">
        <section className="panel">
          <div className="panel-head"><div><div className="panel-title">Needs restocking</div><div className="panel-sub">Products with fewer than {LOW} in stock</div></div></div>
          <div className="panel-body flush">
            {lowStock === null && [0, 1, 2].map((i) => <div key={i} className="skel-row" />)}
            {lowStock?.length === 0 && <div className="empty">Everything is well stocked.</div>}
            {lowStock?.slice(0, 6).map((p) => (
              <button className="rowline link" key={p.id} onClick={() => onNavigate("products", p.product_name)}>
                <span className="grow">{p.product_name}</span>
                <span className="meter" aria-hidden="true"><i className={p.stock_quantity < 5 ? "low" : ""} style={{ width: `${Math.max(6, (p.stock_quantity / LOW) * 100)}%` }} /></span>
                <StockBadge quantity={p.stock_quantity} />
              </button>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><div><div className="panel-title">Recent chats</div><div className="panel-sub">Latest customer questions</div></div></div>
          <div className="panel-body flush">
            {!stats.recent_chats.length && <div className="empty">No chats yet.</div>}
            {stats.recent_chats.slice(0, 6).map((c) => (
              <button className="rowline link" key={c.id} onClick={() => onNavigate("chats")}>
                <span className="grow">{c.query}</span><span className={`badge ${c.route === "products" ? "teal" : ""}`}>{c.route}</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
