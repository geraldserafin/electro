// A note's files: kept as a board's uploaded program is (by their SHA-256, in the vault: @electro/notes-api's
// Firmware.ts), the note naming each (Notebook.files) — in its Python's working directory under that name.

import { apiFetch } from "@/features/vault";
import type { NoteFile } from "@/shared/model/types";

/** Where a file is kept (its id), under its name. */
export const urlOf = (f: NoteFile) => `/api/firmware/${f.id}/${encodeURIComponent(f.name.replace(/\s+/g, "_"))}`;

/** A file's bytes. */
export async function bytesOf(f: NoteFile): Promise<Uint8Array> {
  const response = await apiFetch(new URL(urlOf(f), location.origin));
  if (!response.ok) throw new Error(`${f.name}: HTTP ${response.status}`);
  return new Uint8Array(await response.arrayBuffer());
}

/** A name for a file as Python opens it: no folders, no leading dot; one taken already gets " (2)", " (3)"… */
export function nameFor(wanted: string, taken: readonly NoteFile[]): string {
  const base = wanted.replace(/[/\\]/g, "_").replace(/^\.+/, "") || "plik";
  const dot = base.lastIndexOf(".");
  const [stem, ext] = dot > 0 ? [base.slice(0, dot), base.slice(dot)] : [base, ""];
  let name = base;
  for (let k = 2; taken.some((f) => f.name === name); k++) name = `${stem} (${k})${ext}`;
  return name;
}

/** A size as people read it: 12 kB, 3.4 MB. */
export const sizeOf = (bytes: number) =>
  bytes < 1024
    ? `${bytes} B`
    : bytes < 1024 * 1024
      ? `${Math.round(bytes / 1024)} kB`
      : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
