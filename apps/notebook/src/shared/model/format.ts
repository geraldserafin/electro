// The notebook file (*.electro.json): the same format as Python's electro_notes (format.py there
// describes it in full). Reading migrates older versions and checks the shape — a broken file is a
// FormatError with what and where (the types of electro_notes.issues); keys this version does not
// know are kept.
import type { Cell, Notebook } from "./types";

export const FORMAT = "electro-notebook";
export const VERSION = 2;

/** What is wrong with a file; `where`: the place in it, e.g. `cells[2].id`. */
export type FileIssue =
  | { type: "NotJson"; reason: string } // (the parser's own words)
  | { type: "NotANotebook" | "NoVersion" }
  | { type: "OtherFormat"; format: string }
  | { type: "NewerVersion"; version: number; known: number }
  | { type: "NotText" | "NotAnObject" | "NoCellId" | "UnnamedSchematic" | "NotADrawing"; where: string }
  | { type: "RepeatedCellId"; where: string; id: string }
  | { type: "UnknownCellType"; where: string; found: string }
  | { type: "RepeatedSchematicName"; where: string; name: string };

export class FormatError extends Error {
  constructor(readonly issue: FileIssue) {
    super(issue.type);
  }
}

const broken = (issue: FileIssue) => new FormatError(issue);

export const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
export const newNotebookId = () => crypto.randomUUID().replaceAll("-", "");

/** A new, empty notebook. */
export function blank(title = ""): Notebook {
  const stamp = now();
  return {
    format: FORMAT,
    version: VERSION,
    id: newNotebookId(),
    title,
    created: stamp,
    modified: stamp,
    settings: { codeInPdf: true },
    cells: [],
  };
}

/** The notebook as a file (stamped with the time it is written). */
export function serialize(notebook: Notebook, { stamp = true } = {}): string {
  return JSON.stringify(stamp ? { ...notebook, modified: now() } : notebook, null, 2);
}

/** A file's text → a notebook in the current version, or a FormatError saying what is wrong. */
export function deserialize(text: string): Notebook {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch (error) {
    throw broken({ type: "NotJson", reason: (error as Error).message });
  }
  return fromData(data);
}

/** A notebook from a file the user picked. */
export async function upload(file: File): Promise<Notebook> {
  return deserialize(await file.text());
}

export function fromData(data: unknown): Notebook {
  const notebook = migrate(data);
  check(notebook);
  return notebook;
}

/** A notebook to start from (an example): the same content, a new identity. */
export function copyOf(notebook: unknown): Notebook {
  const stamp = now();
  return { ...fromData(notebook), id: newNotebookId(), created: stamp, modified: stamp };
}

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => typeof x === "object" && x !== null && !Array.isArray(x);

/** Any known version → the current one (a copy; the input is left alone). */
export function migrate(input: unknown): Notebook {
  if (!isObj(input) || !Array.isArray(input.cells)) throw broken({ type: "NotANotebook" });
  let data = structuredClone(input) as Obj;
  if ((data.format ?? FORMAT) !== FORMAT) throw broken({ type: "OtherFormat", format: String(data.format) });
  if (data.version === 1) {
    // before the file had a name, an id and settings; schematic cells had a measurements field
    // and a Markdown table of results — both went away
    const stamp = now();
    data = {
      format: FORMAT,
      version: 2,
      id: newNotebookId(),
      title: data.title ?? "",
      created: stamp,
      modified: stamp,
      settings: { codeInPdf: data.codeInPdf ?? true },
      cells: (data.cells as Obj[]).map((c) => {
        if (!isObj(c) || c.type !== "schematic") return c;
        const { data: _measurements, outputs: _table, ...rest } = c;
        return rest;
      }),
    };
  }
  if (typeof data.version !== "number") throw broken({ type: "NoVersion" });
  if (data.version > VERSION) throw broken({ type: "NewerVersion", version: data.version, known: VERSION });
  return data as unknown as Notebook;
}

function check(nb: Notebook) {
  for (const key of ["id", "title", "created", "modified"] as const)
    if (typeof nb[key] !== "string") throw broken({ type: "NotText", where: key });
  if (!isObj(nb.settings)) throw broken({ type: "NotAnObject", where: "settings" });
  const ids = new Set<string>();
  const names = new Set<string>();
  nb.cells.forEach((c: Cell, i) => {
    const where = `cells[${i}]`;
    if (!isObj(c)) throw broken({ type: "NotAnObject", where });
    if (typeof c.id !== "string" || !c.id) throw broken({ type: "NoCellId", where: `${where}.id` });
    if (ids.has(c.id)) throw broken({ type: "RepeatedCellId", where: `${where}.id`, id: c.id });
    ids.add(c.id);
    if (!["markdown", "code", "schematic"].includes(c.type))
      throw broken({ type: "UnknownCellType", where: `${where}.type`, found: String((c as { type: unknown }).type) });
    if (c.type !== "schematic" && typeof c.source !== "string")
      throw broken({ type: "NotText", where: `${where}.source` });
    if (c.type === "code" && !Array.isArray(c.outputs)) c.outputs = [];
    if (c.type === "schematic") {
      if (typeof c.name !== "string" || !c.name.trim())
        throw broken({ type: "UnnamedSchematic", where: `${where}.name` });
      if (names.has(c.name)) throw broken({ type: "RepeatedSchematicName", where: `${where}.name`, name: c.name });
      names.add(c.name);
      if (!isObj(c.schematic) || !Array.isArray(c.schematic.elements) || !Array.isArray(c.schematic.wires))
        throw broken({ type: "NotADrawing", where: `${where}.schematic` });
    }
  });
}
