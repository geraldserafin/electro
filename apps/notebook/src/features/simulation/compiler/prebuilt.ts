// The examples' sketches compiled ahead (scripts/prebuild-sketches.ts): public/arduino/built/, each
// under its key — the board and the sketch hashed. A sketch as an example has it runs without the
// compiler (a hundred MB, and more memory than a phone gives a page); one changed is compiled here.
import type { Firmware } from "../runner";
import keys from "./prebuilt.json";
import type { Board } from "./toolchain";

const known = new Set<string>(keys);

/** The key a board's sketch is kept under: its SHA-256, the first 16 hex digits. */
export async function keyOf(board: Board, sketch: string): Promise<string> {
  if (!crypto.subtle) return ""; // (only in a secure context: on a plain http address, nothing is known)
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${board}\n${sketch}`));
  return [...new Uint8Array(digest).slice(0, 8)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** The file a key's program is in: an Uno's Intel HEX, a Pico's flash image. */
export const fileOf = (board: Board, key: string) => `${key}.${board === "uno" ? "hex" : "bin"}`;

/** Whether ``sketch`` was compiled ahead (then the compiler need not be fetched for it). */
export async function isPrebuilt(board: Board, sketch: string): Promise<boolean> {
  return known.has(await keyOf(board, sketch));
}

/** The program compiled ahead for ``sketch``, or null: it was not (or it could not be fetched). */
export async function prebuilt(board: Board, sketch: string): Promise<Firmware | null> {
  const key = await keyOf(board, sketch);
  if (!known.has(key)) return null;
  const response = await fetch(`${import.meta.env.BASE_URL}arduino/built/${fileOf(board, key)}`).catch(() => null);
  if (!response?.ok) return null;
  return board === "uno"
    ? { board, hex: await response.text() }
    : { board, image: new Uint8Array(await response.arrayBuffer()) };
}
