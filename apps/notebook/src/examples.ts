// The example notebooks: each can be started as a new note (/examples/:name).
import { copyOf } from "./format";
import { example } from "./storage";
import type { Notebook } from "./types";

const files = import.meta.glob<Notebook>("../examples/*.electro.json", { eager: true, import: "default" });

export const EXAMPLES: { name: string; notebook: Notebook }[] = [
  { name: "mostek", notebook: example() },
  ...Object.entries(files).map(([path, notebook]) => ({
    name: path.slice(path.lastIndexOf("/") + 1).replace(".electro.json", ""),
    notebook,
  })),
];

/** A new note from an example: the same content, its own identity. */
export const fromExample = (name: string): Notebook | null => {
  const found = EXAMPLES.find((e) => e.name === name);
  return found ? copyOf(found.notebook) : null;
};
