import { useCallback, useEffect, useRef, useState } from "react";
import { getServerSettings, getStats } from "../../api/client.js";
import AppShell from "../../shared/components/AppShell.jsx";
import Icon from "../../shared/components/Icon.jsx";
import useLenis from "../../shared/hooks/useLenis.js";
import { useAuth } from "../../shared/context/AuthContext.jsx";
import Skeleton from "../../shared/components/Skeleton.jsx";

import ChatsView from "./ChatsView.jsx";
import ContentView from "./content/ContentView.jsx";
import MetricsView from "./MetricsView.jsx";
import Dashboard from "./Dashboard.jsx";
import PoliciesView from "./PoliciesView.jsx";
import ProductsView from "./ProductsView.jsx";
import SearchDialog from "./SearchDialog.jsx";
import ServerView from "./ServerView.jsx";
import StoresView from "./StoresView.jsx";

// [view id, label, icon name]
const NAV_ITEMS = [["overview", "Overview", "dash"], ["products", "Products", "box"], ["policies", "Policies", "doc"], ["chats", "Chats", "msgs"], ["metrics", "Metrics", "dash"], ["content", "Content", "sliders"]];
const viewFromHash = () => {
  const hash = window.location.hash.slice(1);
  return NAV_ITEMS.some(([id]) => id === hash) || hash === "server" || hash === "stores" ? hash : "overview";
};

export default function AdminWorkspace() {
  const { token, logout } = useAuth();
  const [view, setView] = useState(viewFromHash);
  const [stats, setStats] = useState(null);
  const [server, setServer] = useState(null); // only the server admin can read this; for a store owner it stays null and the Server page is hidden
  const pageRef = useRef(null);
  useLenis(pageRef);
  const [searchOpen, setSearchOpen] = useState(false);
  const [presetQuery, setPresetQuery] = useState("");

  const goTo = useCallback((nextView, query = "") => {
    window.location.hash = nextView;
    setPresetQuery(query);
    setView(nextView);
    setSearchOpen(false);
  }, []);

  useEffect(() => { getStats(token).then(setStats).catch(logout); }, [token, logout, view]);
  useEffect(() => { getServerSettings(token).then(setServer).catch(() => setServer(null)); }, [token]);

  useEffect(() => {
    const onHashChange = () => setView(viewFromHash());
    const onKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("hashchange", onHashChange); window.removeEventListener("keydown", onKeyDown); };
  }, []);

  const nav = (
    <nav className="tabs">
      {(server ? [...NAV_ITEMS, ["stores", "Stores", "box"], ["server", "Server", "shield"]] : NAV_ITEMS).map(([id, label, icon]) => (
        <button key={id} className={`tab${view === id ? " active" : ""}`} onClick={() => goTo(id)}>
          <Icon name={icon} size={15} /> {label}
          {id === "products" && stats?.low_stock > 0 && <span className="count">{stats.low_stock} low</span>}
        </button>
      ))}
    </nav>
  );
  const actions = (
    <>
      <button className="btn ghost sm" onClick={() => setSearchOpen(true)}><Icon name="search" size={15} /> Search <kbd>Ctrl K</kbd></button>
      <a className="icon-btn" href="/" aria-label="Open chat" title="Open chat"><Icon name="chat" size={17} /></a>
      <button className="icon-btn" aria-label="Log out" title="Log out" onClick={logout}><Icon name="out" size={17} /></button>
    </>
  );

  return (
    <AppShell nav={nav} actions={actions} status={stats ? { label: "Connected", ok: true } : { label: "Connecting…" }}>
      <div className="page" ref={pageRef}>
        <div className="page-in">
        {view === "overview" && (stats ? <Dashboard stats={stats} onNavigate={goTo} /> : <Skeleton cards={4} />)}
        {view === "products" && <ProductsView key={presetQuery} initialQuery={presetQuery} />}
        {view === "policies" && <PoliciesView key={presetQuery} initialQuery={presetQuery} />}
        {view === "chats" && <ChatsView chats={stats?.recent_chats || []} />}
        {view === "metrics" && <MetricsView />}
        {view === "stores" && server && <StoresView />}
        {view === "server" && server && <ServerView server={server} onChange={(next) => setServer((s) => ({ ...s, ...next }))} />}
        {view === "content" && <ContentView />}
        </div>
      </div>
      {searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} onPick={goTo} />}
    </AppShell>
  );
}
