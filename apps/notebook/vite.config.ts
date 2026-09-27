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
  plugins: [react(), reloadOnPython()],
  worker: { format: "es" },
  base: "./",
  server: { port: 5190, strictPort: true },
});
