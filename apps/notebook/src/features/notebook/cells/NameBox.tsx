// A schematic's name ("Układ 1", on its tab) is a variable in code: układ1.

/** Mirrors kernel.variable(): "Układ 1" → układ1. */
export function variableName(name: string): string {
  const v = name.toLowerCase().replace(/[^\p{L}\p{N}_]/gu, "");
  if (!v) return "uklad";
  return /^\p{N}/u.test(v) ? `_${v}` : v;
}
