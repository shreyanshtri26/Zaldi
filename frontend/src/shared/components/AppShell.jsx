import { useSiteConfig } from "../context/SiteConfigContext.jsx";

// App frame: a single top bar (brand, page nav, status, actions) over a full-width canvas. No sidebar.
export default function AppShell({ nav, status, actions, raised, children }) {
  const { settings } = useSiteConfig();
  return (
    <div className="shell">
      <header className={`topbar${raised ? " raised" : ""}`}>
        {!raised && (
          <a className="brand" href="/">
            <span className="mark" role="img" aria-label="Zaldi logo" />
            <b>{settings.brand_name}</b>
          </a>
        )}
        {nav}
        <span className="spacer" />
        {status && <span className={`status-pill${status.ok ? " ok" : ""}`}><i className="status-dot" />{status.label}</span>}
        {actions}
      </header>
      <main className="main">{children}</main>
    </div>
  );
}
