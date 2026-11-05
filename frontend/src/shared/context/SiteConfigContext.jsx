import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getSiteConfig } from "../../api/client.js";
import { SITE_DEFAULTS } from "../siteDefaults.js";
import { markUrl, themeVars } from "../theme.js";

const SiteConfigContext = createContext({ ...SITE_DEFAULTS, reload: () => {} });
export const useSiteConfig = () => useContext(SiteConfigContext);

// Loads the CMS-managed storefront text once. If the API is unreachable the built-in defaults are used.
export function SiteConfigProvider({ children }) {
  const [config, setConfig] = useState(SITE_DEFAULTS);
  const [ready, setReady] = useState(false);

  const reload = useCallback(
    () => getSiteConfig()
      .then((c) => setConfig({ settings: { ...SITE_DEFAULTS.settings, ...c.settings }, quickActions: c.quick_actions }))
      .catch(() => {})
      .finally(() => setReady(true)),
    [],
  );
  useEffect(() => { reload(); }, [reload]);
  useEffect(() => { document.title = `${config.settings.brand_name} - AI Fashion Assistant`; }, [config.settings.brand_name]);

  useEffect(() => {
    const icon = document.querySelector('link[rel="icon"]');
    if (icon) icon.href = themeVars(config.settings)["--mark-url"] ? markUrl(config.settings) : "/zaldi_mark.svg";
  }, [config.settings]);

  useEffect(() => {
    const vars = themeVars(config.settings), root = document.documentElement.style;
    Object.entries(vars).forEach(([k, val]) => root.setProperty(k, val));
    return () => Object.keys(vars).forEach((k) => root.removeProperty(k));
  }, [config.settings]);

  return <SiteConfigContext.Provider value={{ ...config, reload }}>{ready ? children : null}</SiteConfigContext.Provider>;
}
