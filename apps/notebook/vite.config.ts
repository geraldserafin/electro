import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
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

const notesServer = process.env.NOTES_SERVER ?? "http://localhost:5191";

export default defineConfig({
  plugins: [react(), reloadOnPython()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } }, // @/features/…, @/shared/…
  worker: { format: "es" },
  base: "/", // routes like /notes/:id: assets from the root
  // the notes server (apps/server) behind /api, in development and in the preview build
  server: { port: 5190, strictPort: true, proxy: { "/api": notesServer } },
  preview: { proxy: { "/api": notesServer } },
});
