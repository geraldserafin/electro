// A note in a link, with no server: the note (without what runs left in it — the reader runs it)
// compressed into the address's fragment, which the browser never sends anywhere. /s#… opens it to
// read (and copy), /embed#… is the same without the app around it, for an <iframe>.
import { deserialize, serialize } from "@/shared/model/format";
import type { Cell, Notebook } from "@/shared/model/types";

/** The note as the reader gets it: the document, not the outputs, results or plots. */
function bare(notebook: Notebook): Notebook {
  const cells = notebook.cells.map((c): Cell => {
    if (c.type === "code") return { ...c, outputs: [], execution: undefined };
    if (c.type === "schematic")
      return {
        ...c,
        results: undefined,
        problems: undefined,
        stale: undefined,
        frequency: undefined,
        sweep: undefined,
        spread: undefined,
      };
    return c;
  });
  return { ...notebook, cells };
}

async function pipe(bytes: Uint8Array<ArrayBuffer>, stream: CompressionStream | DecompressionStream) {
  const out = new Blob([bytes]).stream().pipeThrough(stream);
  return new Uint8Array(await new Response(out).arrayBuffer());
}

const toBase64Url = (bytes: Uint8Array) => {
  let text = "";
  for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
};

const fromBase64Url = (text: string) =>
  Uint8Array.from(atob(text.replaceAll("-", "+").replaceAll("_", "/")), (c) => c.charCodeAt(0));

/** The fragment for a note (after the #). */
export async function encodeNote(notebook: Notebook): Promise<string> {
  const json = new TextEncoder().encode(serialize(bare(notebook), { stamp: false }));
  return toBase64Url(await pipe(json, new CompressionStream("deflate-raw")));
}

/** A fragment back into a note; throws for one that is not (cut short, changed by hand). */
export async function decodeNote(fragment: string): Promise<Notebook> {
  const json = await pipe(fromBase64Url(fragment.replace(/^#/, "")), new DecompressionStream("deflate-raw"));
  return deserialize(new TextDecoder().decode(json));
}

/** The addresses for a note: to read it, and to embed it. */
export async function linksTo(notebook: Notebook): Promise<{ read: string; embed: string }> {
  const fragment = await encodeNote(notebook);
  const root = new URL(import.meta.env.BASE_URL, location.origin).href;
  return { read: `${root}s#${fragment}`, embed: `${root}embed#${fragment}` };
}
