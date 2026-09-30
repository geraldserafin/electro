// A task's answer, checked as electro.task checks it: where the value falls on a logarithmic scale
// with steps of ``tol``, hashed with the quantity's name, against the hashes the task keeps.

const PREFIX: Record<string, number> = { p: 1e-12, n: 1e-9, u: 1e-6, µ: 1e-6, m: 1e-3, k: 1e3, M: 1e6, G: 1e9 };

/** "0,4", "400m", "400 mA", "-2.5e-3 V" → a number; null if it is not one. */
export function parseAnswer(text: string): number | null {
  const m = /^\s*([+-]?\d+(?:[.,]\d+)?(?:e[+-]?\d+)?)\s*([pnuµmkMG])?\s*(?:[A-Za-zΩ°]{0,2})\s*$/.exec(text);
  if (!m) return null;
  const value = Number(m[1].replace(",", ".")) * (m[2] ? PREFIX[m[2]] : 1);
  return Number.isFinite(value) ? value : null;
}

function bucket(value: number, tol: number): string {
  if (Math.abs(value) < 1e-15) return "0";
  return `${value < 0 ? "-" : "+"}${Math.round(Math.log(Math.abs(value)) / Math.log1p(tol))}`;
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Is ``value`` the answer (within about ``tol``)? */
export async function isRight(quantity: string, value: number, tol: number, hashes: string[]): Promise<boolean> {
  return hashes.includes(await sha256(`${quantity}|${bucket(value, tol)}`));
}
