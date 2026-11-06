import { useEffect, useState } from "react";
import { getEmbed, saveAdminSettings } from "../../../api/client.js";
import { useAuth } from "../../../shared/context/AuthContext.jsx";
import { useToast } from "../../../shared/context/ToastContext.jsx";

// The one line a shop owner pastes into their website, and the list of websites that may show the assistant.
export default function EmbedPanel() {
  const { token } = useAuth();
  const toast = useToast();
  const [info, setInfo] = useState(null);
  const [origins, setOrigins] = useState("");
  const load = () => getEmbed(token).then((d) => { setInfo(d); setOrigins(d.allowed_origins.join(", ")); }).catch((e) => toast(e.message, "bad"));
  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e) {
    e.preventDefault();
    try { await saveAdminSettings({ embed_origins: origins }, token); await load(); toast("Allowed websites saved"); } catch (err) { toast(err.message, "bad"); }
  }
  const copy = async () => { try { await navigator.clipboard.writeText(info.snippet); toast("Copied"); } catch { toast("Select the text and copy it", "bad"); } };

  if (!info) return <div className="empty">Loading…</div>;
  return (
    <section className="panel">
      <div className="panel-head"><div><div className="panel-title">Add the assistant to your website</div>
        <div className="panel-sub">Paste this line into your site's pages, just before the closing body tag. Your shoppers get a chat button.</div></div></div>
      <div className="panel-body form-grid">
        <label className="field full">Your snippet
          <textarea className="input" readOnly rows={2} value={info.snippet} onFocus={(e) => e.target.select()} />
        </label>
        <div className="actions full"><button type="button" className="btn ghost" onClick={copy}>Copy snippet</button></div>
        <form className="full form-grid" onSubmit={save}>
          <label className="field full">Websites allowed to show the assistant
            <input className="input" value={origins} onChange={(e) => setOrigins(e.target.value)} placeholder="https://myshop.com, https://www.myshop.com" />
            <span className="hint">{info.ready ? "Only these websites can show your assistant." : "Add at least one website. Until then the assistant will not appear on any site."}</span>
          </label>
          <div className="actions full"><button className="btn">Save websites</button></div>
        </form>
        <p className="hint full">Tell the assistant what the shopper is viewing with <code>Zaldi.setContext({"{"}title, price, sku{"}"})</code>, and hear what they do with <code>Zaldi.on("add-to-cart", fn)</code>.</p>
      </div>
    </section>
  );
}
