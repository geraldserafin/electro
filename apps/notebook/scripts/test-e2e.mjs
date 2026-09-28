// End-to-end check in a real browser engine: Pyodide starts in the worker, the example
// notebook runs, outputs appear, and a schematic element can be placed and dragged.
import { execFileSync, spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { webkit } from "playwright";

const port = 4174;
const shots = process.env.SHOTS ?? tmpdir();  // screenshots, for looking at by hand
// the notes server with a database of its own, and the built notebook in front of it (/api proxied)
const notesPort = 4175;
const notesUrl = `http://localhost:${notesPort}`;
const database = join(tmpdir(), `electro-e2e-${Date.now()}.sqlite`);
const notes = spawn("pnpm", ["exec", "tsx", "src/main.ts"], {
  cwd: new URL("../../server/", import.meta.url), stdio: "ignore", detached: true,
  env: { ...process.env, PORT: String(notesPort), DATABASE_PATH: database },
});
const server = spawn("pnpm", ["exec", "vite", "preview", "--port", String(port), "--strictPort"], {
  stdio: "ignore", detached: true, env: { ...process.env, NOTES_SERVER: notesUrl },
});  // own process groups, see the end
let failed = false;
const check = (name, ok) => {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) failed = true;
};

try {
  for (let i = 0; i < 60; i++) {  // the notes server is up (and migrated)
    if (await fetch(`${notesUrl}/api/health`).then((r) => r.ok, () => false)) break;
    await new Promise((r) => setTimeout(r, 250));
  }
  const browser = await webkit.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const workers = [];
  page.on("worker", (w) => workers.push(w.url()));
  // / : all notes (none yet) and the examples; an example becomes a note at /notes/:id
  const app = `http://localhost:${port}`;
  // the note on screen: its address (a slug) and, from the server, its id
  const noteRef = () => new URL(page.url()).pathname.match(/^\/notes\/([\w-]+)$/)?.[1];
  const noteOnServer = async (ref = noteRef()) => (await fetch(`${notesUrl}/api/notes/${ref}`)).json();
  // the home page: the notes, then the examples (lists, a card in each item: data-id, the note's id)
  const notesList = page.getByRole("list", { name: "Notatki" });
  const examplesList = page.getByRole("list", { name: "Przykłady" });
  const home = async () => {
    await page.getByRole("link", { name: "Notatki" }).click();
    await notesList.waitFor();
  };
  await page.goto(`${app}/`);
  await page.getByRole("heading", { name: "Przykłady" }).waitFor();
  check("home: no notes yet, the examples", (await notesList.locator("li[data-id]").count()) === 0 && (await examplesList.getByRole("listitem").count()) > 0);
  await examplesList.getByRole("button", { name: /^Sprawozdanie: mostek Wheatstone'a/ }).click();
  await page.waitForURL(/\/notes\/[\w-]+$/);
  check("an example becomes a note at an address from its title", noteRef() === "sprawozdanie-mostek-wheatstonea"
    && (await noteOnServer()).document.title === "Sprawozdanie: mostek Wheatstone'a");
  const pythonReady = (timeout) => page.locator('button[aria-label="Uruchom wszystko"]:not([disabled])').waitFor({ timeout });
  await pythonReady(120_000);
  check("pyodide starts in the worker", true);

  await page.getByRole("button", { name: "Uruchom wszystko" }).click();
  await page.locator('[data-output="svg"] svg').nth(1).waitFor({ timeout: 60_000 });
  const text = await page.locator("[data-outputs]").allInnerTexts();
  check("steps() rendered with KaTeX", (await page.locator("[data-outputs] .katex").count()) > 0);
  check("answer R_2 = 200 Ω", text.join(" ").includes("200"));
  check("schematic outputs", (await page.locator('[data-output="svg"] svg').count()) === 2);
  check("no error outputs", (await page.locator('[data-output="error"]').count()) === 0);
  await page.screenshot({ path: `${shots}/notebook.png`, fullPage: true });

  // pick an element in the side panel, then close the panel (it would cover the left of the board)
  const pick = async (scope, name) => {
    await scope.getByRole("button", { name: "Elementy" }).click();
    await scope.getByRole("complementary", { name: "Biblioteka elementów" }).locator(`button[title="${name}"]`).click();
    await scope.getByRole("button", { name: "Elementy" }).click();
  };

  // a new cell at the end: the add buttons on the last cell's bottom edge
  const addAtEnd = async (name) => {
    const edge = page.locator("[data-cell]").last().getByRole("group", { name: "Dodaj komórkę" });
    await edge.hover();
    await edge.getByRole("button", { name }).click();
  };

  // a schematic cell's code, through its Kod view (and back to the drawing)
  const codeOf = async (cellLocator) => {
    await cellLocator.getByRole("tab", { name: "Kod" }).click();
    await cellLocator.locator(".cm-content").waitFor();
    const text = await cellLocator.locator(".cm-content").innerText();
    await cellLocator.getByRole("tab", { name: "Schemat" }).click();
    await cellLocator.locator("[data-board] .canvas").waitFor();
    return text;
  };

  // the run button of a schematic: values on the drawing and a table; the ammeter's reading (0) is the datum
  const bridge = page.locator('[data-cell="schematic"]').first();
  const runBridge = bridge.getByRole("button", { name: "Policz prądy i napięcia (Shift+Enter w kodzie)" });
  const reading = async (value) => {
    await bridge.locator('[data-board] .canvas .element[data-id="A_1"]').click();
    await bridge.getByRole("group", { name: "Właściwości" }).locator("input").nth(1).fill(value);
  };
  await runBridge.click();
  await bridge.locator('table[aria-label="Wyniki"]:not([data-stale])').waitFor({ timeout: 30_000 });
  check("run: table and values on the drawing, then the button rests",
    (await bridge.getByRole("table", { name: "Wyniki" }).innerText()).includes("200 Ω")
    && (await bridge.locator("[data-board] .canvas .label.solved").allTextContents()).join(" ").includes("200")
    && await runBridge.isDisabled());

  // left alone, a schematic keeps its board (grid, drawing, values); its tools come with the pointer
  {
    await page.mouse.move(4, 600); // over no cell
    await page.waitForTimeout(300);
    const tools = bridge.locator("[data-board]").getByRole("toolbar");
    const hidden = (await bridge.locator("[data-board] .canvas .label.solved").count()) > 0
      && await tools.evaluate((el) => getComputedStyle(el).opacity === "0");
    await bridge.locator("[data-board]").hover();
    await page.waitForTimeout(300);
    check("a schematic: board always there, its tools on hover", hidden
      && await tools.evaluate((el) => getComputedStyle(el).opacity === "1"));
  }

  // no reading: not enough data — a warning sign on the board, unfolding into LaTeX
  await reading("");
  check("a change turns the run button back on", !(await runBridge.isDisabled())
    && (await bridge.locator('table[aria-label="Wyniki"][data-stale]').count()) === 1);
  await runBridge.click();
  await bridge.getByRole("button", { name: "Nie wszystko da się wyznaczyć" }).click();
  check("missing data: a warning sign, names in LaTeX",
    (await bridge.getByRole("dialog", { name: "Nie wszystko da się wyznaczyć" }).locator(".katex").count()) > 0
    && (await bridge.getByRole("dialog", { name: "Nie wszystko da się wyznaczyć" }).innerText()).includes("brakuje"));
  await reading("0");
  await runBridge.click();
  await bridge.getByRole("button", { name: /Nie wszystko da się wyznaczyć|Błąd — nie da się policzyć/ }).waitFor({ state: "detached", timeout: 30_000 });

  // moving part of the bridge as a group keeps every connection (edge wires stretch or follow)
  {
    const grid = bridge.locator("[data-board] .canvas");
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
    const view = () => bridge.locator("[data-board] .canvas").getAttribute("viewBox");
    await bridge.locator("[data-board]").hover();
    const viewStart = await view();
    await page.mouse.wheel(0, 120); // the board is active (clicked before): scrolling pans it
    await page.waitForTimeout(100);
    const viewBefore = await view();
    const places = () => bridge.locator("[data-board] .canvas .element").evaluateAll((els) => els.map((e) => [e.querySelector(".hit").getAttribute("x"), e.querySelector(".hit").getAttribute("y")]));
    const before = await places();
    await bridge.getByRole("tab", { name: "Kod" }).click();
    await bridge.locator(".cm-content").waitFor();
    const text = await bridge.locator(".cm-content").innerText();
    await bridge.locator(".cm-content").click();
    await page.keyboard.press("Meta+a");
    await page.keyboard.insertText(text.replace("Resistor(50)", "Resistor(60)"));
    await bridge.getByRole("tab", { name: "Schemat" }).click();
    await bridge.locator("[data-board] .canvas").waitFor();
    check("back from the code view: same view, the board has the keyboard", viewBefore !== viewStart && (await view()) === viewBefore
      && await bridge.locator("[data-board] .canvas").evaluate((svg) => document.activeElement === svg));
    check("code view: a new value keeps the drawing", text.startsWith("mostek = net(")
      && (await bridge.locator('[data-board] .element[data-id="R_3"]').textContent()).includes("60")
      && JSON.stringify(await places()) === JSON.stringify(before));
  }

  // running from the code view keeps the code as written (a comment, the layout of the lines)
  {
    await bridge.getByRole("tab", { name: "Kod" }).click();
    await bridge.locator(".cm-content").waitFor();
    await bridge.locator(".cm-content").click();
    await page.keyboard.press("Meta+ArrowUp");
    await page.keyboard.insertText("# mój komentarz\n");
    await bridge.getByRole("button", { name: "Policz prądy i napięcia (Shift+Enter w kodzie)" }).click();
    await bridge.locator('table[aria-label="Wyniki"]:not([data-stale])').waitFor({ timeout: 30_000 });
    const afterRun = await bridge.locator(".cm-content").innerText();
    await bridge.getByRole("tab", { name: "Schemat" }).click();
    await bridge.getByRole("tab", { name: "Kod" }).click();
    await bridge.locator(".cm-content").waitFor();
    check("running the code does not reformat it", afterRun.startsWith("# mój komentarz")
      && (await bridge.locator(".cm-content").innerText()).startsWith("# mój komentarz"));
    await bridge.getByRole("tab", { name: "Schemat" }).click();
    await bridge.locator("[data-board] .canvas").waitFor();
  }

  // scrolled away from the drawing: a button brings it back (and only then is it there)
  {
    const back = bridge.getByRole("button", { name: /Wróć do schematu/ });
    const shownAtFirst = await back.count();
    await bridge.locator("[data-board]").hover();
    for (let i = 0; i < 12; i++) await page.mouse.wheel(0, 400);
    await back.waitFor({ timeout: 5_000 });
    await back.click();
    const inView = await bridge.locator('[data-board] .element[data-id="R_1"]').evaluate((el) => {
      const r = el.getBoundingClientRect(), b = el.closest("[data-board]").getBoundingClientRect();
      return r.top >= b.top && r.bottom <= b.bottom && r.left >= b.left && r.right <= b.right;
    });
    check("scrolled away: a button brings the drawing back", shownAtFirst === 0 && inView && (await back.count()) === 0);
  }

  // export: the note set by Typst — its pages in the dialog, the PDF to download; the choices are the note's
  {
    // Typst loads in the background while the note is open: the first export does not wait for it
    // (two workers: Python, then Typst — built, their files have no telling names)
    for (let i = 0; i < 120 && workers.length < 2; i++) await page.waitForTimeout(250);
    const before = workers.length;
    await page.waitForTimeout(8000); // (the compiler and the fonts: long done on a local server)
    const opened = Date.now();
    await page.getByRole("button", { name: "Eksport do PDF" }).click();
    const dialog = page.getByRole("dialog", { name: "Eksport do PDF" });
    const sheets = dialog.locator("[data-sheet]");
    await sheets.first().waitFor({ timeout: 90_000 });
    const firstPages = Date.now() - opened;
    check(`Typst loads in the background: the first export shows its pages at once (${firstPages} ms)`,
      before >= 2 && workers.length === before && firstPages < 3000);
    await dialog.locator("[data-preview]:not([data-busy])").waitFor();
    const firstPage = await sheets.first().getAttribute("src");
    const decoded = await sheets.first().evaluate((img) => img.decode().then(() => img.naturalWidth > 0));
    if (process.env.SHOTS) await dialog.screenshot({ path: `${process.env.SHOTS}/export-classic.png` });
    await dialog.getByRole("radio", { name: /Nowoczesny/ }).click();
    await dialog.getByRole("switch", { name: "Kod komórek" }).uncheck();
    await page.waitForFunction((src) => {
      const img = document.querySelector("[data-sheet]");
      return img && img.getAttribute("src") !== src && !document.querySelector("[data-preview][data-busy]");
    }, firstPage, { timeout: 30_000 });
    if (process.env.SHOTS) await dialog.screenshot({ path: `${process.env.SHOTS}/export-modern.png` });
    const [download] = await Promise.all([page.waitForEvent("download"), dialog.getByRole("button", { name: "Pobierz PDF" }).click()]);
    const file = await readFile(await download.path());
    if (process.env.SHOTS) await writeFile(`${process.env.SHOTS}/export.pdf`, file);
    const [typDownload] = await Promise.all([page.waitForEvent("download"), dialog.getByRole("button", { name: "Pobierz .typ" }).click()]);
    const typ = (await readFile(await typDownload.path())).toString();
    if (process.env.SHOTS) await writeFile(`${process.env.SHOTS}/export.typ`, typ);
    await dialog.getByRole("button", { name: "Zamknij" }).click(); // the X in the corner
    await page.waitForTimeout(1500); // saved with the note
    const settings = (await noteOnServer()).document.settings;
    check("export: Typst's pages in the dialog, the PDF and its .typ to download; the note keeps the choices",
      decoded && file.subarray(0, 5).toString() === "%PDF-" && file.length > 10_000
      && download.suggestedFilename().endsWith(".pdf") && typDownload.suggestedFilename().endsWith(".typ")
      && typ.includes("#show: note") && typ.includes("@preview/mitex") && typ.includes("bytes(\"<svg")
      && settings.codeInPdf === false && settings.pdf.theme === "modern"
      && !(await dialog.isVisible()));
    // Ctrl+P (⌘P) opens the export, not the browser's print; more to choose: author, a title page, columns
    await page.keyboard.press("ControlOrMeta+KeyP");
    await dialog.locator("[data-preview]:not([data-busy]) [data-sheet]").first().waitFor({ timeout: 30_000 });
    const shownBefore = await sheets.first().getAttribute("src");
    await dialog.getByRole("switch", { name: "Kod komórek" }).check();
    await dialog.getByRole("textbox", { name: "Autor" }).fill("Jan Kowalski");
    await dialog.getByRole("switch", { name: /Strona tytułowa/ }).check();
    await dialog.getByRole("radio", { name: "Dwie" }).click();
    await page.waitForFunction((src) => !document.querySelector("[data-preview][data-busy]")
      && document.querySelector("[data-sheet]")?.getAttribute("src") !== src, shownBefore, { timeout: 30_000 });
    const titlePages = await sheets.count();
    if (process.env.SHOTS) await dialog.screenshot({ path: `${process.env.SHOTS}/export-title-page.png` });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(1500);
    const more = (await noteOnServer()).document.settings.pdf;
    check("Ctrl+P opens the export; a title page, an author, columns: kept with the note",
      titlePages >= 2 && more.author === "Jan Kowalski" && more.titlePage === true && more.columns === 2);
  }

  // the PDF's drawing: cropped to what is drawn, without the editor's selection or the simulation
  await bridge.locator('[data-board] .element[data-id="R_1"]').click();
  const drawn = bridge.locator(".pdf-drawing svg");
  check("the PDF's drawing: cropped, no selection, no values of the run",
    (await drawn.locator(".selected").count()) === 0 && Number(await drawn.getAttribute("height")) < 500
    && (await drawn.locator(".reading, .label.solved").count()) === 0);

  // editor: place a resistor on the bridge canvas
  const canvas = page.locator("[data-board] .canvas").first();
  const before = await canvas.locator(".element").count();
  let box = await canvas.boundingBox();
  await page.mouse.click(box.x + box.width * 0.6, box.y + box.height * 0.85); // deselect: the inspector would cover the spot
  await pick(bridge, "Rezystor");
  box = await canvas.boundingBox(); // where it is now
  await page.mouse.click(box.x + box.width * 0.8, box.y + box.height * 0.5);
  check("element placed", (await canvas.locator(".element").count()) === before + 1);
  check("inspector shows the new label", (await page.getByRole("group", { name: "Właściwości" }).locator("input").first().inputValue()) === "R_5");
  await canvas.screenshot({ path: `${shots}/editor.png` });

  // wiring by hand in a fresh schematic: drag from a pin, then the wire tool; rotation
  await addAtEnd("Schemat");
  const cell = page.locator('[data-cell="schematic"]').last();  // added at the end of the notebook
  await cell.scrollIntoViewIfNeeded();
  const grid = cell.locator("[data-board] .canvas");
  // grid point → screen point, through the board's camera
  const at = (gx, gy) => grid.evaluate((svg, [x, y]) => {
    const p = new DOMPoint(x, y).matrixTransform(svg.getScreenCTM());
    return [p.x, p.y];
  }, [gx * 20, gy * 20]);
  const click = async (gx, gy) => { const [x, y] = await at(gx, gy); await page.mouse.click(x, y); };
  const code = () => codeOf(cell);
  await pick(cell, "Źródło napięcia"); await click(4, 6);
  await pick(cell, "Rezystor"); await click(12, 3);
  check("new elements show open pins", (await grid.locator(".open-pin").count()) === 4);

  // the element panel: search, Enter, place; the panel stays open (like Excalidraw's)
  await cell.getByRole("button", { name: "Elementy" }).click();
  await page.keyboard.type("kond");
  await page.keyboard.press("Enter");
  await click(24, 3);
  check("library search places an element", (await grid.locator(".element").count()) === 3
    && await cell.getByRole("complementary", { name: "Biblioteka elementów" }).isVisible());
  await page.keyboard.press("Delete");  // keep the circuit a simple loop for what follows
  await cell.getByRole("button", { name: "Elementy" }).click();  // close the panel
  const [x1, y1] = await at(8, 6); const [x2, y2] = await at(12, 3);
  await page.mouse.move(x1, y1); await page.mouse.down(); await page.mouse.move(x2, y2, { steps: 8 }); await page.mouse.up();
  await cell.getByRole("button", { name: "Przewód" }).click();
  for (const p of [[16, 3], [20, 3], [20, 10], [4, 10], [4, 6]]) await click(...p);  // ends on a pin by itself
  await page.keyboard.press("Escape");
  check("wired into a loop", (await code()) === "układ1 = loop(VoltageSource(), Resistor())");
  await click(14, 3); await page.keyboard.press("r");
  check("rotating 90° disconnects", (await grid.locator(".open-pin").count()) === 2);
  await click(14, 3); await page.keyboard.press("r");
  check("rotating 180° reverses in place", (await code()) === "układ1 = loop(VoltageSource(), Resistor())");
  // drag the bottom segment of the loop's return wire two squares down: still the same circuit
  const [sx, sy] = await at(12, 10); const [tx, ty] = await at(12, 12);
  await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(tx, ty, { steps: 6 }); await page.mouse.up();
  // the view pans by dragging empty space; the drawing itself does not move
  const pinBefore = await at(4, 6);
  const [ex, ey] = await at(26, 8);  // empty space inside the view
  await page.mouse.move(ex, ey); await page.mouse.down(); await page.mouse.move(ex - 120, ey - 60, { steps: 6 }); await page.mouse.up();
  const pinAfter = await at(4, 6);
  check("dragging empty space pans the view", Math.round(pinBefore[0] - pinAfter[0]) === 120 && Math.round(pinBefore[1] - pinAfter[1]) === 60
    && (await code()) === "układ1 = loop(VoltageSource(), Resistor())");
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
    && (await code()) === "układ1 = loop(VoltageSource(), Resistor())" && (await grid.locator(".open-pin").count()) === 0);
  await page.keyboard.press("Meta+z");  // back where it was, for the segment check below

  check("moving a wire segment keeps connections", (await code()) === "układ1 = loop(VoltageSource(), Resistor())"
    && (await grid.locator(".open-pin").count()) === 0);

  // the name in the corner is a variable in code: "Układ 1" → układ1; renaming renames it
  await cell.getByTitle(/^W kodzie:/).click();
  await cell.getByRole("textbox", { name: "Nazwa schematu" }).fill("Mój obwód");
  const hint = await cell.getByText("w kodzie:").locator("code").textContent();
  await page.keyboard.press("Enter");
  await addAtEnd("Kod");
  const user = page.locator('[data-cell="code"]').last();
  await user.locator(".cm-content").click();
  await page.keyboard.insertText("mójobwód.solve(I_R_1=1)\ndisplay(schematic(mójobwód))");
  await user.getByRole("button", { name: /Uruchom/ }).click();
  await user.locator('[data-output="svg"] svg').waitFor({ timeout: 30_000 });
  check("schematic name is a variable in code", hint === "mójobwód" && (await user.locator('[data-output="error"]').count()) === 0);

  // the examples notebook from the menu runs without a single error
  await home();
  await examplesList.getByRole("button", { name: /^Przykłady: niewiadome i dziury/ }).click();
  await page.waitForURL(/\/notes\/przyklady-niewiadome-i-dziury$/);
  await pythonReady(60_000);
  await page.getByRole("button", { name: "Uruchom wszystko" }).click();
  await page.locator('[data-cell="code"]').last().locator("[data-outputs]").waitFor({ timeout: 60_000 });
  check("examples run without errors", (await page.locator('[data-output="error"]').count()) === 0
    && (await page.locator('[data-cell="code"] [data-outputs]').count()) === (await page.locator('[data-cell="code"]').count()));

  // the table of contents: on a wide screen, headings of the text cells; a click scrolls there
  {
    await page.setViewportSize({ width: 1700, height: 900 });
    const outline = page.getByRole("navigation", { name: "Spis treści" });
    const toggle = page.getByRole("button", { name: "Spis treści" });
    if (!(await outline.isVisible())) await toggle.click(); // open (it is, at first, on wide screens)
    await outline.waitFor();
    const entries = await outline.locator("a").allInnerTexts();
    await outline.getByRole("link", { name: "5. Za mało danych" }).click();
    await page.waitForTimeout(800);
    const top = await page.locator("h2", { hasText: "5. Za mało danych" }).evaluate((h) => h.getBoundingClientRect().top);
    check("table of contents: headings, a click scrolls there, the section is marked",
      entries.includes("1. Nieznany opór z pomiaru napięcia") && top > 40 && top < 140
      && (await outline.locator('a[aria-current="location"]').innerText()) === "5. Za mało danych");
    await toggle.click();
    await page.waitForTimeout(400); // it slides away
    check("table of contents: its switch hides it", !(await outline.isVisible()));
    await toggle.click();
    await page.setViewportSize({ width: 1440, height: 900 });
  }


  // text cells: rendered; a click shows the plain Markdown; leaving it renders it again
  {
    const cell = page.locator('[data-cell="markdown"]').first();
    const rendered = (await cell.getByTitle("Kliknij, żeby edytować").innerText());
    await cell.getByTitle("Kliknij, żeby edytować").click();
    const field = cell.locator("textarea");
    const source = await field.inputValue();
    await field.press("Meta+ArrowDown");
    await page.keyboard.insertText("\n\nNowe zdanie z **pogrubieniem** i wzorem $U = R I$");
    await page.mouse.click(4, 400); // leave the field: a click in the empty margin
    const view = cell.getByTitle("Kliknij, żeby edytować");
    check("text cells: click edits the Markdown, leaving renders it",
      source.includes("**▶ Uruchom wszystko**") && !rendered.includes("**")
      && (await view.locator("strong").last().innerText()) === "pogrubieniem" && (await view.locator(".katex").count()) > 0);
    // the button on the side: pencil ↔ eye
    await cell.getByRole("button", { name: "Edytuj Markdown" }).click();
    const editing = await field.isVisible();
    await cell.getByRole("button", { name: /Pokaż tekst/ }).click();
    check("text cells: the side button switches edit / view", editing && !(await field.isVisible())
      && await cell.getByTitle("Kliknij, żeby edytować").isVisible());
  }

  // "+ Kod / + Tekst / + Schemat" only on the edge between cells
  {
    const first = page.locator("[data-cell]").first();
    const pill = first.getByRole("group", { name: "Dodaj komórkę" }).getByRole("button").first();
    await first.hover({ position: { x: 300, y: 20 } });
    const hiddenInside = !(await pill.isVisible());
    const box = await first.boundingBox();
    await page.mouse.move(box.x + 300, box.y + box.height + 4); // just below the cell's edge
    check("add buttons show on the edge only", hiddenInside && await pill.isVisible());
  }

  // the file: the note as the server keeps it, read by Python (electro_notes) — and an old (v1) file
  // becomes a note, migrated
  {
    const file = join(shots, "zapisany.electro.json");
    writeFileSync(file, JSON.stringify((await noteOnServer()).document));
    let python = "";
    try {
      python = execFileSync("python", ["-m", "electro_notes", "check", file], { encoding: "utf8" });
    } catch (error) {
      python = String(error.stdout ?? error);
    }
    check("a saved notebook is read by Python", python.includes("Notebook('Przykłady: niewiadome i dziury'"));
    if (!python.includes("Notebook(")) console.log(python);

    const old = join(shots, "stary.electro.json");
    writeFileSync(old, JSON.stringify({ version: 1, title: "Stary notatnik", codeInPdf: true, cells: [
      { id: "a", type: "markdown", source: "Tekst z **wersji 1**" },
      { id: "b", type: "schematic", name: "mostek", schematic: { elements: [], wires: [] }, data: "I_A_1 = 0", outputs: [] },
    ] }));
    await home();
    await page.locator('input[type="file"]').setInputFiles(old);
    await page.getByTitle("Kliknij, żeby zmienić tytuł").filter({ hasText: "Stary notatnik" }).waitFor({ timeout: 10_000 });
    const saved = (await noteOnServer()).document;
    check("an old (v1) file becomes a note, migrated to the current format", saved.version === 2
      && saved.format === "electro-notebook" && saved.title === "Stary notatnik" && !("data" in saved.cells[1]));
  }

  // notes at their addresses: the list with thumbnails; a new note; back and forth; a conflict
  {
    // the title: a box in the top-left island; a click edits it, Enter keeps it
    const title = page.getByTitle("Kliknij, żeby zmienić tytuł");
    const setTitle = async (text) => {
      await title.click();
      await page.getByRole("textbox", { name: "Tytuł notatki" }).fill(text);
      await page.keyboard.press("Enter");
    };
    const titleIs = (t, timeout = 10_000) =>
      page.waitForFunction((t) => document.querySelector('button[title="Kliknij, żeby zmienić tytuł"]')?.textContent === t, t, { timeout });
    const notes = notesList.locator("li[data-id]");
    const { document: { id }, slug } = await noteOnServer();
    const firstTitle = await title.innerText();
    await home();
    const card = notesList.locator(`li[data-id="${id}"]`);
    await card.waitFor({ timeout: 10_000 });
    check("home: the notes with their first pages as thumbnails",
      (await card.getByText(firstTitle, { exact: true }).count()) === 1 && (await card.locator(".page").innerText()).includes("wersji 1"));

    const before = await notes.count();
    await notesList.getByRole("button", { name: "Nowa notatka", exact: true }).click();
    await page.waitForURL(/\/notes\/notatka(-\d+)?$/); // no title yet
    await setTitle("Druga notatka");
    await page.waitForURL(/\/notes\/druga-notatka$/, { timeout: 10_000 }); // the title makes the address
    const second = (await noteOnServer()).document.id;
    check("renaming a note changes its address", (await noteOnServer()).document.title === "Druga notatka");
    await page.goBack(); // the browser's back: the list again
    await page.waitForFunction((n) => document.querySelectorAll('ul[aria-label="Notatki"] > li[data-id]').length === n, before + 1, { timeout: 10_000 });
    await card.getByRole("link").click();
    await titleIs(firstTitle);
    check("a new note; back to the list; the first note opens from its card", noteRef() === slug);

    await page.goto(`${app}/notes/${second}`); // by id: the note, and the address becomes its slug
    await titleIs("Druga notatka", 60_000);
    await page.waitForURL(/\/notes\/druga-notatka$/);
    await page.goto(`${app}/notes/notatka`); // the slug it had before its title
    await page.waitForURL(/\/notes\/druga-notatka$/, { timeout: 60_000 });
    await page.goto(`${app}/notes/nie-ma-takiej`);
    await page.getByRole("heading", { name: "Nie ma takiej notatki" }).waitFor();
    check("addresses: by slug, by id, by an older slug; an unknown one says so", true);

    // someone saves the note elsewhere (a direct call, as another tab would), then it is edited here
    await page.goto(`${app}/notes/${slug}`);
    await titleIs(firstTitle, 60_000);
    const note = await (await fetch(`${notesUrl}/api/notes/${id}`)).json();
    await fetch(`${notesUrl}/api/notes/${id}`, { method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify({ document: { ...note.document, title: "Zmienione gdzie indziej" }, baseRevision: note.revision }) });
    await setTitle(`${firstTitle} (tutaj)`);
    await page.getByRole("alert").waitFor({ timeout: 10_000 });
    await page.getByRole("alert").getByRole("button", { name: "Z serwera" }).click();
    await titleIs("Zmienione gdzie indziej");
    check("a conflict is shown and resolved by taking the server's version", (await page.getByRole("alert").count()) === 0);

    await home();
    const drugi = notesList.locator(`li[data-id="${second}"]`);
    await drugi.hover();
    await drugi.getByRole("button", { name: "Więcej" }).click();
    page.once("dialog", (d) => d.accept());
    await drugi.getByRole("menuitem", { name: "Usuń notatkę" }).click();
    await drugi.waitFor({ state: "detached", timeout: 10_000 });
    check("a note is deleted", (await fetch(`${notesUrl}/api/notes/${second}`)).status === 404);
  }

  check("no page errors", errors.length === 0);
  if (errors.length) console.log(errors);
  await browser.close();
} finally {
  process.kill(-server.pid);  // pnpm and the vite it started
  process.kill(-notes.pid);
}
process.exit(failed ? 1 : 0);
