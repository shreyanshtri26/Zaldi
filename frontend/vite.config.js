import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` proxies /api to Flask on :5000. Prod: Flask serves dist/.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/store-sim": "http://127.0.0.1:5000", // demo storefront the checkout automation drives
      "/api": {
        target: "http://127.0.0.1:5000",
        configure: (proxy) => {
          // Without this, a stopped backend shows up as a bare "500 Internal Server Error".
          proxy.on("error", (_err, _req, res) => {
            if (res.writeHead && !res.headersSent) {
              res.writeHead(502, { "Content-Type": "application/json" });
              res.end(JSON.stringify({ error: "Backend is not running. Start it with: python wsgi.py" }));
            }
          });
        },
      },
    },
  },
});
