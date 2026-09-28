// Messages between the page and the Typst worker.
import type { TypstDocument } from "./document";

export type Request =
  | { type: "warm" } // load the compiler and the fonts now (the note is open, or the dialog)
  | { type: "compile"; id: number; document: TypstDocument };

export type Reply =
  | { id: number; ok: true; pdf: Uint8Array; svg: string; unreadable: number } // unreadable: formulas shown as written
  | { id: number; ok: false; error: string };
