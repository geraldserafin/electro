// End-to-end check in a real browser engine: Pyodide starts in the worker, the example
// notebook runs, outputs appear, and a schematic element can be placed and dragged.
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { webkit } from "playwright";

const port = 4174;
const server = spawn("pnpm", ["exec", "vite", "preview", "--port", String(port), "--strictPort"], { stdio: "ignore" });
const shots = process.env.SHOTS ?? tmpdir();  // screenshots, for looking at by hand
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

  await page.getByRole("button", { name: "Uruchom wszystko" }).click();
  await page.locator(".output-svg svg").nth(1).waitFor({ timeout: 60_000 });
  const text = await page.locator(".outputs").allInnerTexts();
  check("steps() rendered with KaTeX", (await page.locator(".outputs .katex").count()) > 0);
  check("answer R_2 = 200 Ω", text.join(" ").includes("200"));
  check("schematic outputs", (await page.locator(".output-svg svg").count()) === 2);
  check("no error outputs", (await page.locator(".output-error").count()) === 0);
  await page.screenshot({ path: `${shots}/notebook.png`, fullPage: true });

  // "Symuluj" on the drawing, with a measurement for the unknown
  const bridge = page.locator(".cell-schematic").first();
  await bridge.locator(".sim-bar input").fill("I_A_1 = 0");
  await bridge.getByRole("button", { name: "Symuluj" }).click();
  await bridge.locator(".outputs table").waitFor({ timeout: 30_000 });
  check("simulation: table and values on the drawing",
    (await bridge.locator(".outputs table").innerText()).includes("200 Ω")
    && (await bridge.locator(".canvas .label.solved").textContent()).includes("200"));

  // "show code" turns the drawing into plain electro code in a new cell
  await page.getByRole("button", { name: "Kod", exact: true }).first().click();
  await page.getByText("mostek = net(").waitFor({ timeout: 30_000 });
  check("schematic → code cell", true);

  // editor: place a resistor on the bridge canvas
  const canvas = page.locator(".canvas").first();
  const before = await canvas.locator(".element").count();
  await page.getByTitle("Rezystor").first().click();
  const box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width * 0.8, box.y + box.height * 0.5);
  check("element placed", (await canvas.locator(".element").count()) === before + 1);
  check("inspector shows the new label", (await page.locator(".inspector input").first().inputValue()) === "R_5");
  await canvas.screenshot({ path: `${shots}/editor.png` });

  // wiring by hand in a fresh schematic: drag from a pin, then the wire tool; rotation
  await page.locator(".cellbar").getByRole("button", { name: "+ Schemat" }).click();
  const cell = page.locator(".cell-schematic").last();  // added at the end of the notebook
  await cell.scrollIntoViewIfNeeded();
  const grid = cell.locator(".canvas");
  const at = async (gx, gy) => { const b = await grid.boundingBox(); return [b.x + gx * 20, b.y + gy * 20]; };
  const click = async (gx, gy) => { const [x, y] = await at(gx, gy); await page.mouse.click(x, y); };
  const code = async () => {
    await cell.getByRole("button", { name: "Kod", exact: true }).click();
    const inserted = cell.locator("xpath=following-sibling::section[1]");  // the new cell right below
    await inserted.locator(".cm-content").waitFor();
    const text = await inserted.locator(".cm-content").innerText();
    await inserted.hover();
    await inserted.getByTitle("Usuń komórkę").click();
    return text;
  };
  await cell.getByTitle("Źródło napięcia").click(); await click(4, 6);
  await cell.getByTitle("Rezystor").click(); await click(12, 3);
  check("new elements show open pins", (await grid.locator(".open-pin").count()) === 4);
  const [x1, y1] = await at(8, 6); const [x2, y2] = await at(12, 3);
  await page.mouse.move(x1, y1); await page.mouse.down(); await page.mouse.move(x2, y2, { steps: 8 }); await page.mouse.up();
  await cell.getByRole("button", { name: "Przewód" }).click();
  for (const p of [[16, 3], [20, 3], [20, 10], [4, 10], [4, 6]]) await click(...p);  // ends on a pin by itself
  await page.keyboard.press("Escape");
  check("wired into a loop", (await code()) === "uklad = loop(VoltageSource(), Resistor())");
  await click(14, 3); await page.keyboard.press("r");
  check("rotating 90° disconnects", (await grid.locator(".open-pin").count()) === 2);
  await click(14, 3); await page.keyboard.press("r");
  check("rotating 180° reverses in place", (await code()) === "uklad = loop(VoltageSource(), Resistor())");
  // drag the bottom segment of the loop's return wire two squares down: still the same circuit
  const [sx, sy] = await at(12, 10); const [tx, ty] = await at(12, 12);
  await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(tx, ty, { steps: 6 }); await page.mouse.up();
  check("moving a wire segment keeps connections", (await code()) === "uklad = loop(VoltageSource(), Resistor())"
    && (await grid.locator(".open-pin").count()) === 0);

  // the examples notebook from the menu runs without a single error
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Plik" }).click();
  await page.getByRole("button", { name: "Przykład: Przykłady: niewiadome i dziury" }).click();
  await page.getByRole("button", { name: "Uruchom wszystko" }).click();
  await page.locator(".cell-code").last().locator(".outputs").waitFor({ timeout: 60_000 });
  check("examples run without errors", (await page.locator(".output-error").count()) === 0
    && (await page.locator(".cell-code .outputs").count()) === (await page.locator(".cell-code").count()));

  check("no page errors", errors.length === 0);
  if (errors.length) console.log(errors);
  await browser.close();
} finally {
  server.kill();
}
process.exit(failed ? 1 : 0);
