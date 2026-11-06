import { useEffect, useRef, useState } from "react";
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
  const box = useRef(null);
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && box.current) box.current.open = false; };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const clear = () => { setPrefs({ max_price: "", gender: "", size: "", brand: "", exclude_brands: "" }); setSaved(false); };
  return (
    <details className="history prefs-menu" ref={box}>
      <summary className="nav-btn" aria-label="Assistant settings" data-tip="Assistant settings"><Icon name="sliders" size={20} /></summary>
      <form className="history-pop prefs" onSubmit={save}>
        <header className="prefs-head">
          <span className="prefs-ico"><Icon name="sliders" size={16} /></span>
          <div><b>Shopping preferences</b><small>Applied to every search, so you don't have to repeat them.</small></div>
        </header>
        <div className="prefs-grid">
          <label>Max budget<span className="prefix"><i>Rs.</i><input className="input" inputMode="numeric" value={prefs.max_price ?? ""} onChange={set("max_price")} placeholder="No limit" /></span></label>
          <label>Shopping for
            <select className="select" value={prefs.gender || ""} onChange={set("gender")}>
              <option value="">Anyone</option><option>Women</option><option>Men</option><option>Girls</option><option>Boys</option>
            </select>
          </label>
          <label>Usual size<input className="input" value={prefs.size || ""} onChange={set("size")} placeholder="e.g. M or 40" /></label>
          <label>Only this brand<input className="input" value={prefs.brand || ""} onChange={set("brand")} placeholder="Any brand" /></label>
          <label className="wide">Never show brands<input className="input" value={prefs.exclude_brands || ""} onChange={set("exclude_brands")} placeholder="comma separated" /></label>
        </div>
        {error && <p className="form-error">{error}</p>}
        <footer className="prefs-foot">
          <button type="button" className="btn ghost sm" onClick={clear}>Clear all</button>
          <button className="btn sm">{saved ? "Saved" : "Save"}</button>
        </footer>
      </form>
    </details>
  );
}
