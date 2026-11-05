import { useEffect, useState } from "react";
import { listItems } from "../../api/client.js";
import Icon from "../../shared/components/Icon.jsx";
import StockBadge from "./StockBadge.jsx";

export default function Dashboard({ stats, onNavigate }) {
  const [lowStock, setLowStock] = useState([]);
  useEffect(() => {
    listItems("products")
      .then((rows) => setLowStock(rows.filter((p) => p.stock_quantity < 10).sort((a, b) => a.stock_quantity - b.stock_quantity)))
      .catch(() => {});
  }, []);

  const cards = [["Products", stats.products, "products"], ["Policies", stats.policies, "policies"], ["Chats", stats.chats, "chats"]];
  return (
    <div className="col-wide">
      <div className="page-head">
        <div><div className="eyebrow">Workspace</div><h2>Overview</h2><p>What is happening in your store assistant today.</p></div>
      </div>

      <section className="hero">
        <div className="hero-row">
          <span className="agent-orb"><Icon name="bot" size={24} /></span>
          <div>
            <h2>Zaldi assistant</h2>
          </div>
        </div>
        <p>Answers customer questions from your products and policies, in English, Hindi or Hinglish. Edit the content here and it is used right away.</p>
        <div className="tags">
          <span className="tag">{stats.products} products</span>
          <span className="tag">{stats.policies} policies</span>
          <span className="tag">{stats.chats} chats answered</span>
        </div>
      </section>

      <div className="stats">
        {cards.map(([label, value, view]) => (
          <button key={label} className="card stat" style={{ textAlign: "left", cursor: "pointer" }} onClick={() => onNavigate(view)}>
            <b>{value}</b><span>{label}</span>
          </button>
        ))}
        <button className={`card stat${stats.low_stock ? " hot" : ""}`} style={{ textAlign: "left", cursor: "pointer" }} onClick={() => onNavigate("products")}>
          <b>{stats.low_stock}</b><span>Low stock items</span>
        </button>
      </div>

      <div className="grid-2">
        <section className="panel">
          <div className="panel-head"><div><div className="panel-title">Needs restocking</div><div className="panel-sub">Products with fewer than 10 in stock</div></div></div>
          <div className="panel-body">
            {!lowStock.length && <div className="empty">Everything is well stocked.</div>}
            {lowStock.slice(0, 6).map((p) => <div className="rowline" key={p.id}><span className="grow">{p.product_name}</span><StockBadge quantity={p.stock_quantity} /></div>)}
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><div><div className="panel-title">Recent chats</div><div className="panel-sub">Latest customer questions</div></div></div>
          <div className="panel-body">
            {!stats.recent_chats.length && <div className="empty">No chats yet.</div>}
            {stats.recent_chats.slice(0, 6).map((c) => <div className="rowline" key={c.id}><span className="grow">{c.query}</span><span className={`badge ${c.route === "products" ? "teal" : ""}`}>{c.route}</span></div>)}
          </div>
        </section>
      </div>
    </div>
  );
}
