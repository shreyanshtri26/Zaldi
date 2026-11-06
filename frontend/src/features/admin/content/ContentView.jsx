import { useState } from "react";
import PromptsEditor from "./PromptsEditor.jsx";
import QuickActionsEditor from "./QuickActionsEditor.jsx";
import StorefrontSettings from "./StorefrontSettings.jsx";
import StoreConnection from "./StoreConnection.jsx";

const TABS = [["storefront", "Storefront"], ["assistant", "Assistant"], ["store", "Store connection"]];

// CMS-managed content that is not a product or policy: customer-facing text, quick actions and assistant prompts.
export default function ContentView() {
  const [tab, setTab] = useState("storefront");
  return (
    <div className="col-wide">
      <div className="page-head">
        <div>
          <h2>Content</h2>
          <p>Everything starts with the built-in defaults. Change it here and the chat updates; reset to go back.</p>
        </div>
      </div>
      <div className="tabs">
        {TABS.map(([id, label]) => <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}
      </div>
      {tab === "storefront" && <div style={{ display: "grid", gap: 16 }}><StorefrontSettings /><QuickActionsEditor /></div>}
      {tab === "assistant" && <PromptsEditor />}
      {tab === "store" && <StoreConnection />}
    </div>
  );
}
