// Packs electro (and the notebook kernel) into public/py/bundle.json,
// a {path: source} map the Pyodide worker writes into its file system.
import { mkdirSync, readdirSync, readFileSync, statSync, watch, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const repo = join(dirname(fileURLToPath(import.meta.url)), "../../..");
const roots = ["packages/electro/src", "apps/notebook/python"];

let files = {};
function walk(root, dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name !== "__pycache__") walk(root, path);
    } else if (name.endsWith(".py") && !name.startsWith("test_")) {
      files[relative(root, path)] = readFileSync(path, "utf8");
    }
  }
}
const out = join(repo, "apps/notebook/public/py/bundle.json");

function bundle() {
  files = {};
  for (const root of roots) walk(join(repo, root), join(repo, root));
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, JSON.stringify(files));
  console.log(`python bundle: ${Object.keys(files).length} files → public/py/bundle.json`);
}

bundle();

// --watch: rebuild on every change to a .py file; reloading the page picks it up.
if (process.argv.includes("--watch")) {
  let timer;
  for (const root of roots) {
    watch(join(repo, root), { recursive: true }, (_, name) => {
      if (!name?.endsWith(".py")) return;
      clearTimeout(timer);
      timer = setTimeout(bundle, 100);
    });
  }
  console.log("watching Python sources…");
}
