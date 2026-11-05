import { useCallback, useEffect, useMemo, useState } from "react";
import { createItem, deleteItem, listItems, updateItem } from "../../api/client.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import { useToast } from "../../shared/context/ToastContext.jsx";
import Drawer from "../../shared/components/Drawer.jsx";
import Icon from "../../shared/components/Icon.jsx";
import { hue, inr } from "../../shared/utils/format.js";
import StockBadge from "./StockBadge.jsx";

const FIELDS = [
  ["product_code", "Code", { required: true }], ["category", "Category"],
  ["product_name", "Name", { required: true, full: true }],
  ["brand", "Brand"], ["material", "Material"], ["size", "Sizes"], ["color", "Colour"], ["gender", "Gender"],
  ["price", "Price (Rs.)", { type: "number", required: true }], ["stock_quantity", "Stock", { type: "number" }],
  ["image_url", "Image URL (https://…)", { full: true }],
  ["description", "Description", { full: true, area: true }],
];
const SORTS = {
  name: ["Name", (a, b) => a.product_name.localeCompare(b.product_name)],
  priceUp: ["Price: low to high", (a, b) => a.price - b.price],
  priceDown: ["Price: high to low", (a, b) => b.price - a.price],
  stock: ["Stock: lowest first", (a, b) => a.stock_quantity - b.stock_quantity],
};
export default function ProductsView({ initialQuery = "" }) {
  const { token } = useAuth();
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [q, setQ] = useState(initialQuery);
  const [cat, setCat] = useState("All");
  const [sort, setSort] = useState("name");
  const [view, setView] = useState(() => { try { return localStorage.getItem("zaldi_pview") || "table"; } catch { return "table"; } });
  const [form, setForm] = useState(null); // null closed, {} new, row = editing
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => listItems("products").then(setRows).catch((e) => { setError(e.message); setRows([]); }), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { try { localStorage.setItem("zaldi_pview", view); } catch {} }, [view]);

  const cats = useMemo(() => ["All", ...new Set((rows || []).map((r) => r.category).filter(Boolean))], [rows]);
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (rows || [])
      .filter((r) => (cat === "All" || r.category === cat) &&
        (!t || [r.product_name, r.brand, r.color, r.description, r.product_code].some((v) => (v || "").toLowerCase().includes(t))))
      .sort(SORTS[sort][1]);
  }, [rows, q, cat, sort]);

  async function save() {
    setSaving(true); setError("");
    try {
      form.id ? await updateItem("products", form.id, form, token) : await createItem("products", form, token);
      toast(form.id ? "Product updated" : "Product added");
      setForm(null); load();
    } catch (e) { toast(e.message, "bad"); } finally { setSaving(false); }
  }
  async function remove(r) {
    if (!window.confirm(`Delete "${r.product_name}"?`)) return;
    try { await deleteItem("products", r.id, token); toast("Product deleted"); load(); } catch (e) { toast(e.message, "bad"); }
  }
  const actions = (r) => (
    <>
      <button className="icon-btn" aria-label={`Edit ${r.product_name}`} onClick={() => setForm(r)}><Icon name="edit" size={16} /></button>
      <button className="icon-btn" aria-label={`Delete ${r.product_name}`} onClick={() => remove(r)}><Icon name="trash" size={16} /></button>
    </>
  );

  return (
    <div className="col-wide">
      <div className="page-head">
        <div><div className="eyebrow">Catalogue</div><h2>Products</h2><p>{rows ? `${shown.length} of ${rows.length} products` : "Loading…"}</p></div>
        <span className="spacer" />
        <button className="btn" onClick={() => setForm({})}><Icon name="plus" size={16} /> Add product</button>
      </div>
      {error && <p className="err">{error}</p>}
      <div className="toolbar">
        <div className="search"><Icon name="search" size={16} /><input className="input" placeholder="Search products…" aria-label="Search products" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <select className="select" style={{ width: "auto" }} aria-label="Sort" value={sort} onChange={(e) => setSort(e.target.value)}>
          {Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}
        </select>
        <div className="seg">
          <button className={view === "table" ? "active" : ""} aria-label="Table view" onClick={() => setView("table")}><Icon name="list" /></button>
          <button className={view === "grid" ? "active" : ""} aria-label="Grid view" onClick={() => setView("grid")}><Icon name="grid" /></button>
        </div>
      </div>
      <div className="chips">{cats.map((c) => <button key={c} className={`chip${c === cat ? " active" : ""}`} onClick={() => setCat(c)}>{c}</button>)}</div>

      {rows && !shown.length && <div className="card empty">No products match. Try a different search or category.</div>}
      {shown.length > 0 && view === "table" && (
        <div className="table-wrap"><table>
          <thead><tr><th>Product</th><th>Category</th><th className="num">Price</th><th>Stock</th><th /></tr></thead>
          <tbody>{shown.map((r) => (
            <tr key={r.id}>
              <td><b>{r.product_name}</b><div className="sub">{r.product_code} · {r.brand || "-"}</div></td>
              <td>{r.category}</td><td className="num">{inr(r.price)}</td><td><StockBadge quantity={r.stock_quantity} /></td>
              <td className="act">{actions(r)}</td>
            </tr>))}</tbody>
        </table></div>
      )}
      {shown.length > 0 && view === "grid" && (
        <div className="pgrid">{shown.map((r) => (
          <article className="pcard" key={r.id}>
            <div className="thumb" style={r.image_url ? undefined : { background: `linear-gradient(135deg, hsl(${hue(r.category)} 45% 38%), hsl(${hue(r.product_name)} 50% 52%))` }}>
              {r.image_url ? <img src={r.image_url} alt={r.product_name} loading="lazy" /> : r.product_name[0]}
            </div>
            <div className="body"><span className="badge teal" style={{ justifySelf: "start" }}>{r.category}</span><h4>{r.product_name}</h4><p>{r.description}</p><StockBadge quantity={r.stock_quantity} /></div>
            <div className="foot"><span className="price">{inr(r.price)}</span>{actions(r)}</div>
          </article>))}</div>
      )}

      {form && (
        <Drawer title={form.id ? "Edit product" : "Add product"} onClose={() => setForm(null)} onSubmit={save} saving={saving}>
          {FIELDS.map(([key, label, o = {}]) => (
            <label key={key} className={`field${o.full ? " full" : ""}`}>{label}
              {o.area
                ? <textarea className="textarea" rows={4} value={form[key] ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
                : <input className="input" type={o.type || "text"} min={o.type === "number" ? 0 : undefined} required={o.required}
                    value={form[key] ?? ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />}
            </label>
          ))}
        </Drawer>
      )}
    </div>
  );
}
