import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import { AuthProvider } from "./shared/context/AuthContext.jsx";
import { SiteConfigProvider } from "./shared/context/SiteConfigContext.jsx";
import "./styles/index.css";

createRoot(document.getElementById("root")).render(
  <AuthProvider>
    <SiteConfigProvider>
      <App />
    </SiteConfigProvider>
  </AuthProvider>
);
