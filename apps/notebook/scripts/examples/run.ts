// The example notebooks (examples/*/*.electro.json, as lib.py wrote them) run as "Run all" runs them, so each
// opens with its results, and their drawings checked: a circuit laid out from its code (`_code`), every
// marked code cell run (`_run`), a drawing solved on paper (`_solve`), and each hand-placed drawing whole
// (`_checks`: it runs in time if `live`, the pins `joined` are one point, each routed net one point of its
// own, every label on something, no pin left hanging). The markers are taken out as it goes.
// Run by make.py; or: pnpm python && tsx scripts/examples/run.ts examples/1-elektronika/01-*.json.
// --check (pnpm test:examples): every example run again as it is, nothing written — the kernel still runs them.
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { given, shown } from "../../src/features/python/outputs";
import { drawingFromCode, type FromCode } from "../../src/features/schematic/fromCode";
import { library } from "../../src/features/schematic/library";
import { isBoard, isComponent, key, pins } from "../../src/features/schematic/model";
import { netlist } from "../../src/features/schematic/netlist";
import { withParts } from "../../src/features/schematic/parts";
import { elementsOf, solveData } from "../../src/features/schematic/problem";
import type { Point, SchematicData } from "../../src/shared/model/types";
import { loadKernel } from "../kernel.mjs";

type Pin = [string, number];
type Checks = { live: boolean; joined: Pin[][]; nets: Record<string, Pin[]> };
type Cell = Record<string, unknown> & { type: string; name?: string; schematic?: SchematicData; source?: string };

const kernel = await loadKernel();
const examples = new URL("../../examples/", import.meta.url);

function fail(where: string, what: unknown): never {
  throw new Error(`${where}: ${typeof what === "string" ? what : JSON.stringify(what)}`);
}

/** The drawing's hand-placed checks (lib.py's Drawing.finish used to make them). */
function check(where: string, sch: SchematicData, { live, joined, nets }: Checks) {
  const lib = withParts(library, sch.parts);
  const { names } = netlist(sch, library);
  const at = new Map(sch.elements.map((e) => [e.id, pins(e, lib)]));
  const node = ([id, k]: Pin) => names.get(key(at.get(id)![k])) ?? null;
  const onOne = (group: Pin[]) => {
    const nodes = new Set(group.map(node));
    if (nodes.size !== 1 || nodes.has(null)) fail(where, { group, nodes: [...nodes] });
    return [...nodes][0];
  };
  for (const group of joined) onOne(group);
  const found = Object.values(nets).map(onOne); // each routed net on a node of its own: no crossing joined it
  if (new Set(found).size !== found.length) fail(where, { nets: Object.keys(nets), found });
  const ends = new Set(sch.wires.flatMap((w) => [key(w.points[0]), key(w.points[w.points.length - 1])]));
  const marks = ["label", "ground", "port"];
  const pinPoints = new Set(sch.elements.filter((e) => !marks.includes(e.kind)).flatMap((e) => at.get(e.id)!.map(key)));
  for (const e of sch.elements)
    if (marks.includes(e.kind) && !ends.has(key(at.get(e.id)![0])) && !pinPoints.has(key(at.get(e.id)![0])))
      fail(where, `${e.id} (${e.text}) joins nothing`);
  const count = new Map<string, number>();
  for (const p of sch.elements.flatMap((e) => at.get(e.id)!)) count.set(key(p), (count.get(key(p)) ?? 0) + 1);
  for (const e of sch.elements) {
    if (e.kind === "part" || !isComponent(e.kind) || isBoard(e.kind)) continue;
    for (const p of at.get(e.id)! as Point[])
      if (!ends.has(key(p)) && count.get(key(p))! < 2) fail(where, `${e.id}: pin ${p} not connected`);
  }
  if (live) {
    const compiled = JSON.parse(kernel.live(JSON.stringify({ elements: elementsOf(sch, library).elements })));
    if ("error" in compiled) fail(where, compiled.error);
  }
}

async function run(path: URL) {
  const notebook = JSON.parse(readFileSync(path, "utf8"));
  const cells: Cell[] = notebook.cells;
  const errorsOk = Boolean(notebook._errors_ok);
  delete notebook._errors_ok;
  const where = (c: Cell) => `${path.pathname.split("/examples/")[1]}: ${c.name ?? c.source}`;
  for (const c of cells.filter((c) => c._code)) {
    const back = JSON.parse(kernel.from_code(c._code, c.name)) as FromCode | { error: unknown };
    if ("error" in back) fail(where(c), back.error);
    const drawn = drawingFromCode(back, c.schematic!, library);
    if ("error" in drawn) fail(where(c), drawn.error);
    c.schematic = drawn.schematic;
    delete c._code;
  }
  kernel.reset();
  const drawings = Object.fromEntries(cells.filter((c) => c.type === "schematic").map((c) => [c.name, c.schematic!]));
  const { problems, units } = given(drawings, library);
  for (const c of cells) {
    if (c.type === "code" && (checking ? (c.outputs as unknown[]).length > 0 : c._run)) {
      c.outputs = await shown(JSON.parse(kernel.run(c.source, problems, units)), library);
      const bad = (c.outputs as { type: string; data?: string }[]).filter((o) => o.type === "error");
      if (bad.length && !errorsOk)
        fail(
          where(c),
          bad.map((o) => o.data),
        );
    }
    if (c.type === "schematic" && c._checks) check(where(c), c.schematic!, c._checks as Checks);
    if (c.type === "schematic" && (checking ? c.results : c._solve)) {
      const solved = JSON.parse(kernel.solve(JSON.stringify(solveData(c.schematic!, library))));
      const bad = solved.problems.filter((p: { kind: string }) => p.kind === "error");
      if (bad.length) fail(where(c), bad);
      Object.assign(c, solved, { stale: false });
    }
    for (const marker of ["_run", "_solve", "_checks"]) delete c[marker];
  }
  if (!checking) writeFileSync(path, `${JSON.stringify(notebook, null, 2)}\n`);
}

const checking = process.argv.includes("--check");
const named = process.argv
  .slice(2)
  .filter((a) => a !== "--check")
  .map((p) => new URL(p, `file://${process.cwd()}/`));
const all = readdirSync(examples, { withFileTypes: true })
  .filter((d) => d.isDirectory())
  .flatMap((d) =>
    readdirSync(new URL(`${d.name}/`, examples))
      .filter((f) => f.endsWith(".electro.json"))
      .map((f) => new URL(`${d.name}/${f}`, examples)),
  );
for (const path of named.length ? named : all) await run(path);
