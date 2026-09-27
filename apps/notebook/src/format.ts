// The notebook file (*.electro.json): the same format as Python's electro_notes (format.py there
// describes it in full). Reading migrates older versions and checks the shape, with messages
// that say where a file is broken; keys this version does not know are kept.
import type { Cell, Notebook } from "./types";

export const FORMAT = "electro-notebook";
export const VERSION = 2;

export class FormatError extends Error {}

export const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
export const newNotebookId = () => crypto.randomUUID().replaceAll("-", "");

/** A new, empty notebook. */
export function blank(title = ""): Notebook {
  const stamp = now();
  return { format: FORMAT, version: VERSION, id: newNotebookId(), title, created: stamp, modified: stamp,
           settings: { codeInPdf: true }, cells: [] };
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
    throw new FormatError(`To nie jest JSON: ${(error as Error).message}`);
  }
  return fromData(data);
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
  if (!isObj(input) || !Array.isArray(input.cells)) throw new FormatError("To nie jest plik notatnika: brak listy „cells”.");
  let data = structuredClone(input) as Obj;
  if ((data.format ?? FORMAT) !== FORMAT) throw new FormatError(`To plik „${data.format}”, a nie notatnik electro.`);
  if (data.version === 1) {
    // before the file had a name, an id and settings; schematic cells had a measurements field
    // and a Markdown table of results — both went away
    const stamp = now();
    data = {
      format: FORMAT, version: 2, id: newNotebookId(), title: data.title ?? "", created: stamp, modified: stamp,
      settings: { codeInPdf: data.codeInPdf ?? true },
      cells: (data.cells as Obj[]).map((c) => {
        if (!isObj(c) || c.type !== "schematic") return c;
        const { data: _measurements, outputs: _table, ...rest } = c;
        return rest;
      }),
    };
  }
  if (typeof data.version !== "number") throw new FormatError("W pliku nie ma wersji formatu („version”).");
  if (data.version > VERSION)
    throw new FormatError(`Plik jest w nowszej wersji formatu (${data.version}); ta aplikacja zna ${VERSION}.`);
  return data as unknown as Notebook;
}

function check(nb: Notebook) {
  for (const key of ["id", "title", "created", "modified"] as const)
    if (typeof nb[key] !== "string") throw new FormatError(`${key}: brak albo zły typ (oczekiwano tekstu).`);
  if (!isObj(nb.settings)) throw new FormatError("settings: oczekiwano obiektu.");
  const ids = new Set<string>();
  const names = new Set<string>();
  nb.cells.forEach((c: Cell, i) => {
    const where = `cells[${i}]`;
    if (!isObj(c)) throw new FormatError(`${where}: oczekiwano obiektu.`);
    if (typeof c.id !== "string" || !c.id) throw new FormatError(`${where}.id: brak identyfikatora komórki.`);
    if (ids.has(c.id)) throw new FormatError(`${where}.id: identyfikator „${c.id}” się powtarza.`);
    ids.add(c.id);
    if (!["markdown", "code", "schematic"].includes(c.type))
      throw new FormatError(`${where}.type: nieznany rodzaj komórki „${(c as { type: unknown }).type}”.`);
    if (c.type !== "schematic" && typeof c.source !== "string") throw new FormatError(`${where}.source: oczekiwano tekstu.`);
    if (c.type === "code" && !Array.isArray(c.outputs)) c.outputs = [];
    if (c.type === "schematic") {
      if (typeof c.name !== "string" || !c.name.trim()) throw new FormatError(`${where}.name: schemat bez nazwy.`);
      if (names.has(c.name)) throw new FormatError(`${where}.name: dwa schematy nazywają się „${c.name}”.`);
      names.add(c.name);
      if (!isObj(c.schematic) || !Array.isArray(c.schematic.elements) || !Array.isArray(c.schematic.wires))
        throw new FormatError(`${where}.schematic: oczekiwano {"elements": [...], "wires": [...]}.`);
    }
  });
}
