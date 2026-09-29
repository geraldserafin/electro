// An I²C module's text on the drawing: its address, then — an LCD's — its contrast trimmer in per
// cent ("0x27 70%"). The schematic edits it, the simulation reads it.

export const TRIMMER = 0.7; // as a module comes: VDD − V0 ≈ 4.25 V, where it shows best

export function i2cParts(text: string | null | undefined): { address: string; trimmer: number } {
  const [address = "", trim] = (text ?? "").trim().split(/\s+/);
  const value = trim?.endsWith("%") ? Number(trim.slice(0, -1)) / 100 : NaN;
  return { address, trimmer: Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : TRIMMER };
}

export const i2cText = (address: string, trimmer: number) => `${address} ${Math.round(trimmer * 100)}%`;
