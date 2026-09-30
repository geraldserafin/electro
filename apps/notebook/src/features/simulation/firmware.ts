// A program for a board given whole instead of as a sketch to compile: its text's first line names the
// file — "// firmware: /pico/doom.uf2" — a UF2 (as one drags onto a Pico in BOOTSEL mode) or a raw
// flash image (.bin), fetched from the page's server. For programs no sketch makes: Doom.

const FLASH = 0x10000000; // where the RP2040's flash is mapped (a UF2's addresses)
const UF2_MAGIC = [0x0a324655, 0x9e5d5157], UF2_END = 0x0ab16f30;

/** The file a board's text names, if it names one. */
export function firmwareFile(text: string): string | null {
  const first = text.split("\n").find((line) => line.trim()) ?? "";
  return /^\s*\/\/\s*firmware:\s*(\S+)\s*$/.exec(first)?.[1] ?? null;
}

/** A UF2's blocks → the flash they write (from its start, as far as the last byte written; the rest erased). */
export function uf2Flash(bytes: Uint8Array): Uint8Array {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const blocks: [number, Uint8Array][] = [];
  let end = 0;
  for (let at = 0; at + 512 <= bytes.length; at += 512) {
    if (view.getUint32(at, true) !== UF2_MAGIC[0] || view.getUint32(at + 4, true) !== UF2_MAGIC[1]
        || view.getUint32(at + 508, true) !== UF2_END) throw new Error(`not a UF2 block at byte ${at}`);
    if (view.getUint32(at + 8, true) & 1) continue; // "not main flash"
    const address = view.getUint32(at + 12, true) - FLASH, size = view.getUint32(at + 16, true);
    if (address < 0 || size > 476) throw new Error(`a UF2 block outside the flash at byte ${at}`);
    blocks.push([address, bytes.subarray(at + 32, at + 32 + size)]);
    end = Math.max(end, address + size);
  }
  const flash = new Uint8Array(end).fill(0xff);
  for (const [address, data] of blocks) flash.set(data, address);
  return flash;
}

/** The flash image in the file at ``url`` (a UF2, or else taken as a raw image). */
export async function fetchFirmware(url: string): Promise<Uint8Array> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  const uf2 = bytes.length >= 512 && new DataView(bytes.buffer).getUint32(0, true) === UF2_MAGIC[0];
  return uf2 ? uf2Flash(bytes) : bytes;
}
