import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

/**
 * The Python sources live in public/py/bundle.json (rebuilt by `bundle-python.mjs --watch`) and
 * are loaded once, by the Pyodide worker. Hot-swapping React would keep the worker running the
 * old Python, so a new bundle reloads the whole page.
 */
function reloadOnPython(): Plugin {
  return {
    name: "reload-on-python",
    configureServer(server) {
      server.watcher.add("public/py/bundle.json");
      server.watcher.on("change", (file) => {
        if (file.endsWith("public/py/bundle.json")) server.ws.send({ type: "full-reload" });
      });
    },
  };
}

export default defineConfig({
  plugins: [tailwindcss(), react(), reloadOnPython()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } }, // @/features/…, @/shared/…
  worker: { format: "es" },
  // where the app is served (BASE: on GitHub Pages, /<repository>/); assets from there, not from the
  // address of a route like /n/:id
  base: process.env.BASE ?? "/",
  server: { port: 5190, strictPort: true },
});
