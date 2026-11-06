import { useEffect, useState } from "react";
import { getStore, resetStore, saveStore, testStore } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

const LABELS = { local: "This store (built-in catalogue and cart)", woocommerce: "WooCommerce", shopify: "Shopify", escuelajs: "Platzi Fake Store API (free demo catalogue)",
  feed: "Product feed (CSV or JSON link)", rest: "Custom API (any shop with a search address)", links: "Product page links",
  amazon: "Amazon (Associates account)", flipkart: "Flipkart (Affiliate account)" };
const LEVELS = { catalogue: "Shoppers can search, compare and open products on the store.", cart: "Shoppers can also build a cart in the chat.", orders: "Shoppers can also check orders and start returns." };
// fields shown per connector: [key, label, hint, secret?]
const FIELDS = {
  woocommerce: [["woocommerce_url", "Store address", "https://your-store.com", false], ["woocommerce_key", "Consumer key", "Read-only key from WooCommerce > Settings > Advanced > REST API", true],
    ["woocommerce_secret", "Consumer secret", "Shown once when you create the key", true]],
  shopify: [["shopify_domain", "Store domain", "your-store.myshopify.com", false], ["shopify_token", "Storefront access token", "Shopify admin > Apps > Develop apps > Storefront API", true],
    ["shopify_version", "API version", "Optional. Example: 2025-07", false]],
  escuelajs: [["escuelajs_url", "Address", "Leave empty to use https://api.escuelajs.co/api/v1", false]],
  feed: [["feed_url", "Feed link", "A public https link to a CSV or JSON product list (Google Merchant exports work)", false], ["feed_label", "Name shown on cards", "Optional. Example: My Shop", false]],
  rest: [["rest_config", "API mapping (JSON)", "Search address with {query}, and which fields hold the name, price, image and link. See the README for an example", true]],
  links: [["link_urls", "Product page links", "One https link per line (up to 50). Pages must publish standard product data", false], ["feed_label", "Name shown on cards", "Optional", false]],
  amazon: [["amazon_credential_id", "Credential ID", "From your Amazon Associates Creators API credentials", true], ["amazon_credential_secret", "Credential secret", "Shown once when you create the credential", true],
    ["amazon_partner_tag", "Partner tag", "Your tracking id, for example yourname-21", false], ["amazon_token_url", "Token address", "Copy it from the credentials page (https://...)", false],
    ["amazon_marketplace", "Marketplace", "Default www.amazon.in", false]],
  flipkart: [["flipkart_affiliate_id", "Affiliate tracking ID", "From affiliate.flipkart.com", false], ["flipkart_token", "API token", "Dashboard > API > API Token", true]],
  local: [],
};

export default function StoreConnection() {
  const { token } = useAuth();
  const toast = useToast();
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const load = (data) => { setInfo(data); setForm({ ...data.values }); setResult(null); };
  useEffect(() => { getStore(token).then(load).catch((e) => toast(e.message, "bad")); }, [token, toast]);

  async function run(action, success) {
    setBusy(true);
    try { const out = await action(); if (out) load(out); if (success) toast(success); } catch (e) { toast(e.message, "bad"); } finally { setBusy(false); }
  }
  const save = (e) => { e.preventDefault(); run(() => saveStore(form, token), "Store connection saved"); };
  const test = async () => { setBusy(true); setResult(null); try { setResult(await testStore(token)); } catch (e) { setResult({ ok: false, message: e.message }); } finally { setBusy(false); } };

  if (!info) return <div className="empty">Loading…</div>;
  const kind = form.connector || "local";
  return (
    <section className="panel">
      <div className="panel-head">
        <div><div className="panel-title">Store connection</div><div className="panel-sub">Which store the assistant searches. Connected stores are read-only: shoppers buy on the store itself.</div></div>
      </div>
      <form className="panel-body form-grid" onSubmit={save}>
        <label className="field full">Store
          <select className="select" value={kind} onChange={(e) => { setForm({ ...form, connector: e.target.value }); setResult(null); }}>
            {info.connectors.map((c) => <option key={c} value={c}>{LABELS[c] || c}</option>)}
          </select>
          <span className="hint">Changes apply to the next customer message.</span>
        </label>
        {FIELDS[kind].map(([key, label, hint, secret]) => (
          <label key={key} className="field">{label}
            <input className="input" type={secret ? "password" : "text"} autoComplete="off" value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              placeholder={secret && info.secrets_set[key] ? "Saved. Type to replace" : ""} />
            <span className="hint">{hint}{secret && info.secrets_set[key] && " · a key is saved"}</span>
          </label>
        ))}
        {kind !== "local" && <p className="hint full">Keys are saved in the app database and are never sent back to this page. For production, set them as environment variables instead.</p>}
        {result && (
          <div className={`full note ${result.ok ? "ok" : "bad"}`} role="status">
            {result.checks ? (
              <>
                <strong>{result.ok ? `Connected to ${result.store}.` : "Not ready yet."}</strong> {result.level && LEVELS[result.level]}
                <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                  {result.checks.map((c) => <li key={c.name}>{c.ok ? "✓" : c.blocking ? "✗" : "!"} {c.name}: {c.detail}{c.fix ? ` ${c.fix}` : ""}</li>)}
                </ul>
              </>
            ) : (result.ok ? `Connected to ${result.store}.` : result.message)}
          </div>
        )}
        <div className="actions full">
          <button className="btn" disabled={busy}>{busy ? "Working…" : "Save"}</button>
          <button type="button" className="btn ghost" disabled={busy} onClick={test}>Test connection</button>
          <button type="button" className="btn ghost" disabled={busy || !info.overridden.length} onClick={() => run(() => resetStore(token), "Back to environment settings")}>Use environment settings</button>
        </div>
      </form>
    </section>
  );
}
