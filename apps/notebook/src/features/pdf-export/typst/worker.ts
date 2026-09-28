// Typst, compiled in the browser (typst.ts: the compiler and a renderer, as WebAssembly), off the
// page's thread. One document in, the PDF and its pages as SVG out — the preview is the same
// layout as the file. The fonts and mitex (LaTeX formulas) come with the app (public/typst).
import initCompiler, { TypstCompilerBuilder, type TypstCompiler } from "@myriaddreamin/typst-ts-web-compiler";
import compilerWasm from "@myriaddreamin/typst-ts-web-compiler/wasm?url";
import initRenderer, { TypstRendererBuilder, type TypstRenderer } from "@myriaddreamin/typst-ts-renderer";
import rendererWasm from "@myriaddreamin/typst-ts-renderer/wasm?url";
import template from "./electro.typ?raw";
import type { Reply, Request } from "./protocol";

const ASSETS = `${import.meta.env.BASE_URL}typst/`;
const FONTS = [
  "NewCM10-Regular.otf", "NewCM10-Bold.otf", "NewCM10-Italic.otf", "NewCM10-BoldItalic.otf", "NewCMMath-Regular.otf",
  "Inter-Regular.ttf", "Inter-Italic.ttf", "Inter-SemiBold.ttf", "Inter-SemiBoldItalic.ttf", "Inter-Bold.ttf",
  "LibertinusSerif-Regular.otf", "LibertinusSerif-Bold.otf", "LibertinusSerif-Italic.otf", "LibertinusSerif-BoldItalic.otf",
  "DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf",
];
const MITEX = ["lib.typ", "mitex.typ", "mitex.wasm", "specs/mod.typ", "specs/prelude.typ", "specs/latex/standard.typ"];

const bytes = async (path: string) => {
  const response = await fetch(ASSETS + path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
};

let tools: Promise<{ compiler: TypstCompiler; renderer: TypstRenderer; mitex: Uint8Array[] }> | null = null;
const setup = () =>
  (tools ??= (async () => {
    const [fonts, mitex] = await Promise.all([
      Promise.all(FONTS.map((f) => bytes(`fonts/${f}`))),
      Promise.all(MITEX.map((f) => bytes(`mitex/${f}`))),
      initCompiler({ module_or_path: compilerWasm }),
      initRenderer({ module_or_path: rendererWasm }),
    ]);
    const builder = new TypstCompilerBuilder();
    builder.set_dummy_access_model();
    for (const font of fonts) await builder.add_raw_font(font);
    const compiler = await builder.build();
    const renderer = await new TypstRendererBuilder().build();
    return { compiler, renderer, mitex };
  })());

interface Diagnostic { path: string; range: string; severity: string; message: string }

/** The formulas a failed compile points at, in main.typ ("while calling m" at `m(3)`). */
function formulasIn(diagnostics: Diagnostic[], main: string): number[] {
  const lines = main.split("\n");
  const found = new Set<number>();
  for (const d of diagnostics) {
    if (d.path !== "/main.typ") continue;
    const [line, column] = d.range.split("-")[0].split(":").map(Number);
    const calls = [...(lines[line] ?? "").matchAll(/#[mM]\((\d+)\)/g)];
    // the call nearest the position (columns may count differently than JS strings)
    const nearest = calls.sort((a, b) => Math.abs(a.index - column) - Math.abs(b.index - column))[0];
    if (nearest) found.add(Number(nearest[1]));
  }
  return [...found];
}

/** The files every document needs: the theme and mitex (after a reset of the last document's). */
function prepare(compiler: TypstCompiler, mitex: Uint8Array[]) {
  compiler.reset_shadow();
  MITEX.forEach((f, i) => compiler.map_shadow(`/mitex/${f}`, mitex[i]));
  compiler.add_source("/electro.typ", template);
}

/**
 * Loaded ahead (while the note is open, before anyone exports): the compiler, the fonts, and one
 * small document through them — each font and mitex's plugin are read on first use, not on load.
 */
let warmed: Promise<void> | null = null;
const warm = () =>
  (warmed ??= setup().then(({ compiler, mitex }) => {
    prepare(compiler, mitex);
    compiler.add_source("/warm.typ", `#import "mitex/lib.typ": mi
#text(font: "New Computer Modern")[Aa *Aa* _Aa_] #text(font: "Inter")[Aa *Aa* _Aa_]
#text(font: "Libertinus Serif")[Aa *Aa* _Aa_ #smallcaps[Aa]] #raw("Aa") #mi("\\\\frac{x^2}{R_1}")`);
    try {
      compiler.compile("/warm.typ", null, "vector", 3);
    } catch {
      // only a warm-up
    }
  }).catch(() => { tools = null; warmed = null; }));

const post = (reply: Reply, transfer: Transferable[] = []) => (self as unknown as Worker).postMessage(reply, transfer);

self.onmessage = async ({ data }: MessageEvent<Request>) => {
  if (data.type === "warm") return void warm();
  const { id, document } = data;
  try {
    const { compiler, renderer, mitex } = await setup();
    await warmed; // (a warm-up still running: after it)
    prepare(compiler, mitex);
    const encoder = new TextEncoder();
    for (const [path, svg] of Object.entries(document.files)) compiler.map_shadow(`/${path}`, encoder.encode(svg));
    compiler.add_source("/main.typ", document.main);

    // formulas mitex cannot read are shown as written; find them, one failed compile at a time
    const bad: number[] = [];
    for (let attempt = 0; ; attempt++) {
      compiler.add_source("/config.typ", document.config.replace("__BAD__", bad.map((i) => `${i},`).join(" ")));
      const pdf = compiler.compile("/main.typ", null, "pdf", 3) as { result?: Uint8Array; diagnostics?: Diagnostic[] };
      if (pdf.result) {
        const vector = compiler.compile("/main.typ", null, "vector", 3) as { result: Uint8Array };
        const session = renderer.create_session();
        renderer.manipulate_data(session, "reset", vector.result);
        const svg = renderer.svg_data(session);
        session.free();
        post({ id, ok: true, pdf: pdf.result, svg, bad }, [pdf.result.buffer]);
        return;
      }
      const diagnostics = pdf.diagnostics ?? [];
      const more = formulasIn(diagnostics, document.main).filter((i) => !bad.includes(i));
      if (!more.length || attempt > 50) {
        const error = diagnostics.find((d) => d.severity === "error");
        post({ id, ok: false, error: error?.message ?? "" });
        return;
      }
      bad.push(...more);
    }
  } catch (error) {
    post({ id, ok: false, error: String((error as Error).message ?? error) });
  }
};
