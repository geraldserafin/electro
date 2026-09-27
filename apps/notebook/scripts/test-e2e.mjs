// End-to-end check in a real browser engine: Pyodide starts in the worker, the example
// notebook runs, outputs appear, and a schematic element can be placed and dragged.
import { spawn } from "node:child_process";
import { tmpdir } from "node:os";
import { webkit } from "playwright";

const port = 4174;
const server = spawn("pnpm", ["exec", "vite", "preview", "--port", String(port), "--strictPort"], { stdio: "ignore", detached: true });  // own process group, see the end
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

  // a schematic cell's code, through its Kod view (and back to the drawing)
  const codeOf = async (cellLocator) => {
    await cellLocator.getByRole("tab", { name: "Kod" }).click();
    await cellLocator.locator(".cm-content").waitFor();
    const text = await cellLocator.locator(".cm-content").innerText();
    await cellLocator.getByRole("tab", { name: "Schemat" }).click();
    await cellLocator.locator(".board .canvas").waitFor();
    return text;
  };

  // "Symuluj" on the drawing, with a measurement for the unknown
  const bridge = page.locator(".cell-schematic").first();
  await bridge.locator(".sim-bar input").fill("I_A_1 = 0");
  await bridge.getByRole("button", { name: "Symuluj" }).click();
  await bridge.locator(".outputs table").waitFor({ timeout: 30_000 });
  check("simulation: table and values on the drawing",
    (await bridge.locator(".outputs table").innerText()).includes("200 Ω")
    && (await bridge.locator(".board .canvas .label.solved").allTextContents()).join(" ").includes("200"));

  // the same measurement typed as the ammeter's reading instead of in "Dane pomiarowe"
  await bridge.locator('.board .canvas .element[data-id="A_1"]').click();
  await bridge.locator(".inspector input").nth(1).fill("0");
  await bridge.locator(".sim-bar input").fill("");
  await bridge.getByRole("button", { name: "Symuluj" }).click();
  await bridge.locator(".stale").waitFor({ state: "detached", timeout: 30_000 });
  await page.waitForTimeout(300);
  check("ammeter reading is a measurement",
    (await bridge.locator(".board .canvas .label.solved").allTextContents()).join(" ").includes("200")
    && (await bridge.locator(".board .canvas").textContent()).includes("A1 = 0 A"));

  // moving part of the bridge as a group keeps every connection (edge wires stretch or follow)
  {
    const grid = bridge.locator(".board .canvas");
    const at = (gx, gy) => grid.evaluate((svg, [x, y]) => {
      const p = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM());
      return [p.x, p.y];
    }, [gx * 20, gy * 20]);
    const bridgeCode = () => codeOf(bridge);
    const before = await bridgeCode();
    const [x0, y0] = await at(12, -1); const [x1, y1] = await at(21, 15);
    await page.keyboard.down("Shift");
    await page.mouse.move(x0, y0); await page.mouse.down(); await page.mouse.move(x1, y1, { steps: 5 }); await page.mouse.up();
    await page.keyboard.up("Shift");
    const [gx, gy] = await at(18, 2); const [hx, hy] = await at(22, 2);
    await page.mouse.move(gx, gy); await page.mouse.down(); await page.mouse.move(hx, hy, { steps: 5 }); await page.mouse.up();
    check("moving a group keeps the bridge connected", (await bridgeCode()) === before
      && (await grid.locator(".open-pin").count()) === 0);
  }

  // Schemat | Kod: a value changed in the code comes back to the same drawing
  {
    const places = () => bridge.locator(".board .canvas .element").evaluateAll((els) => els.map((e) => [e.querySelector(".hit").getAttribute("x"), e.querySelector(".hit").getAttribute("y")]));
    const before = await places();
    await bridge.getByRole("tab", { name: "Kod" }).click();
    await bridge.locator(".cm-content").waitFor();
    const text = await bridge.locator(".cm-content").innerText();
    await bridge.locator(".cm-content").click();
    await page.keyboard.press("Meta+a");
    await page.keyboard.insertText(text.replace("Resistor(50)", "Resistor(60)"));
    await bridge.getByRole("tab", { name: "Schemat" }).click();
    await bridge.locator(".board .canvas").waitFor();
    check("code view: a new value keeps the drawing", text.startsWith("mostek = net(")
      && (await bridge.locator('.board .element[data-id="R_3"]').textContent()).includes("60")
      && JSON.stringify(await places()) === JSON.stringify(before));
  }

  // the PDF: the drawing cropped to what is drawn, without the editor (and its selection)
  await bridge.locator('.board .element[data-id="R_1"]').click();
  await page.emulateMedia({ media: "print" });
  const printed = bridge.locator(".print-drawing svg");
  check("print shows the drawing, not the editor", await printed.isVisible() && !(await bridge.locator(".board").isVisible())
    && (await printed.locator(".selected").count()) === 0 && (await printed.boundingBox()).height < 500);
  await page.emulateMedia({ media: "screen" });

  // editor: place a resistor on the bridge canvas
  const canvas = page.locator(".board .canvas").first();
  const before = await canvas.locator(".element").count();
  const box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.85); // deselect: the inspector would cover the spot
  await page.getByTitle("Rezystor").first().click();
  await page.mouse.click(box.x + box.width * 0.8, box.y + box.height * 0.5);
  check("element placed", (await canvas.locator(".element").count()) === before + 1);
  check("inspector shows the new label", (await page.locator(".inspector input").first().inputValue()) === "R_5");
  await canvas.screenshot({ path: `${shots}/editor.png` });

  // wiring by hand in a fresh schematic: drag from a pin, then the wire tool; rotation
  await page.locator(".cellbar").getByRole("button", { name: "+ Schemat" }).click();
  const cell = page.locator(".cell-schematic").last();  // added at the end of the notebook
  await cell.scrollIntoViewIfNeeded();
  const grid = cell.locator(".board .canvas");
  // grid point → screen point, through the board's camera
  const at = (gx, gy) => grid.evaluate((svg, [x, y]) => {
    const p = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM());
    return [p.x, p.y];
  }, [gx * 20, gy * 20]);
  const click = async (gx, gy) => { const [x, y] = await at(gx, gy); await page.mouse.click(x, y); };
  const code = () => codeOf(cell);
  await cell.getByTitle("Źródło napięcia").click(); await click(4, 6);
  await cell.getByTitle("Rezystor").click(); await click(12, 3);
  check("new elements show open pins", (await grid.locator(".open-pin").count()) === 4);

  // the element library: search, Enter, place — and it joins the recent elements on the toolbar
  await cell.getByRole("button", { name: "Elementy" }).click();
  await page.keyboard.type("kond");
  await page.keyboard.press("Enter");
  await click(24, 3);
  check("library search places an element", (await grid.locator(".element").count()) === 3
    && (await cell.locator(".island.tools").getByTitle("Kondensator").count()) === 1);
  await page.keyboard.press("Delete");  // keep the circuit a simple loop for what follows
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
  // the view pans by dragging empty space; the drawing itself does not move
  const pinBefore = await at(4, 6);
  const [ex, ey] = await at(26, 8);  // empty space inside the view
  await page.mouse.move(ex, ey); await page.mouse.down(); await page.mouse.move(ex - 120, ey - 60, { steps: 6 }); await page.mouse.up();
  const pinAfter = await at(4, 6);
  check("dragging empty space pans the view", Math.round(pinBefore[0] - pinAfter[0]) === 120 && Math.round(pinBefore[1] - pinAfter[1]) === 60
    && (await code()) === "uklad = loop(VoltageSource(), Resistor())");
  await cell.getByRole("button", { name: "Dopasuj widok" }).click();
  check("fit shows the whole drawing", (await grid.locator(".element").count()) === 2);

  // shift + drag selects many; the group moves together and keeps its connections
  const [bx0, by0] = await at(1, 0); const [bx1, by1] = await at(23, 14);
  await page.keyboard.down("Shift");
  await page.mouse.move(bx0, by0); await page.mouse.down(); await page.mouse.move(bx1, by1, { steps: 6 }); await page.mouse.up();
  await page.keyboard.up("Shift");
  const selected = await grid.locator(".element.selected").count();
  const [gx, gy] = await at(14, 3); const [hx, hy] = await at(16, 5);
  await page.mouse.move(gx, gy); await page.mouse.down(); await page.mouse.move(hx, hy, { steps: 6 }); await page.mouse.up();
  check("shift + drag selects many and moves them together", selected === 2
    && (await code()) === "uklad = loop(VoltageSource(), Resistor())" && (await grid.locator(".open-pin").count()) === 0);
  await page.keyboard.press("Meta+z");  // back where it was, for the segment check below

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
  process.kill(-server.pid);  // pnpm and the vite it started
}
process.exit(failed ? 1 : 0);
