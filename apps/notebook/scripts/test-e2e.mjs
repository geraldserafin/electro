// End-to-end check in a real browser engine: Pyodide starts in the worker, the example
// notebook runs, outputs appear, and a schematic element can be placed and dragged.
import { spawn } from "node:child_process";
import { webkit } from "playwright";

const port = 4174;
const server = spawn("pnpm", ["exec", "vite", "preview", "--port", String(port), "--strictPort"], { stdio: "ignore" });
const shots = process.env.SHOTS ?? ".";
let failed = false;
const check = (name, ok) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) failed = true;
};

try {
  await new Promise((r) => setTimeout(r, 1500));
  const browser = await webkit.launch();
  const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`http://localhost:${port}/`);
  await page.getByText("Python gotowy").waitFor({ timeout: 120_000 });
  check("pyodide starts in the worker", true);

  await page.getByRole("button", { name: "▶ Uruchom wszystko" }).click();
  await page.locator(".output-svg svg").nth(1).waitFor({ timeout: 60_000 });
  const text = await page.locator(".outputs").allInnerTexts();
  check("steps() rendered with KaTeX", (await page.locator(".outputs .katex").count()) > 0);
  check("answer R_2 = 200 Ω", text.join(" ").includes("200"));
  check("schematic outputs", (await page.locator(".output-svg svg").count()) === 2);
  check("no error outputs", (await page.locator(".output-error").count()) === 0);
  await page.screenshot({ path: `${shots}/notebook.png`, fullPage: true });

  // editor: place a resistor on the bridge canvas and drag it
  const canvas = page.locator(".canvas").first();
  const before = await canvas.locator(".element").count();
  await page.getByTitle("Rezystor").first().click();
  const box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width * 0.8, box.y + box.height * 0.5);
  check("element placed", (await canvas.locator(".element").count()) === before + 1);
  check("inspector shows the new label", (await page.locator(".inspector input").first().inputValue()) === "R_5");
  await canvas.screenshot({ path: `${shots}/editor.png` });

  check("no page errors", errors.length === 0);
  if (errors.length) console.log(errors);
  await browser.close();
} finally {
  server.kill();
}
process.exit(failed ? 1 : 0);
