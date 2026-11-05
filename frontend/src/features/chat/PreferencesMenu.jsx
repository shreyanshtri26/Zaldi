import { useEffect, useState } from "react";
import { getPreferences, savePreferences } from "../../api/client.js";
import Icon from "../../shared/components/Icon.jsx";

// Saved shopping preferences: applied automatically to every product search.
export default function PreferencesMenu() {
  const [prefs, setPrefs] = useState({});
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { getPreferences().then(setPrefs).catch(() => {}); }, []);
  const set = (k) => (e) => { setPrefs({ ...prefs, [k]: e.target.value }); setSaved(false); };
  const save = async (e) => {
    e.preventDefault();
    try { setPrefs(await savePreferences(prefs)); setSaved(true); setError(""); } catch (err) { setError(err.message); }
  };
  return (
    <details className="history">
      <summary className="nav-btn" aria-label="Assistant settings" data-tip="Assistant settings"><Icon name="sliders" size={20} /></summary>
      <form className="history-pop prefs" onSubmit={save}>
        <b>Shopping preferences</b>
        <label>Max budget (Rs.)<input className="input" inputMode="numeric" value={prefs.max_price ?? ""} onChange={set("max_price")} placeholder="No limit" /></label>
        <label>Shopping for
          <select className="select" value={prefs.gender || ""} onChange={set("gender")}>
            <option value="">Anyone</option><option>Women</option><option>Men</option><option>Girls</option><option>Boys</option>
          </select>
        </label>
        <label>Usual size<input className="input" value={prefs.size || ""} onChange={set("size")} placeholder="e.g. M or 40" /></label>
        <label>Only this brand<input className="input" value={prefs.brand || ""} onChange={set("brand")} /></label>
        <label>Never show brands<input className="input" value={prefs.exclude_brands || ""} onChange={set("exclude_brands")} placeholder="comma separated" /></label>
        {error && <p className="form-error">{error}</p>}
        <button className="btn sm">{saved ? "Saved" : "Save"}</button>
      </form>
    </details>
  );
}
