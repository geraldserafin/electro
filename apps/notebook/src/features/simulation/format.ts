// Numbers as the board shows them: three significant digits and an SI prefix ("12.4 mA").
const PREFIXES: [number, string][] = [[1e6, "M"], [1e3, "k"], [1, ""], [1e-3, "m"], [1e-6, "µ"], [1e-9, "n"], [1e-12, "p"]];

export function si(value: number, unit: string): string {
  if (!Number.isFinite(value)) return `– ${unit}`;
  const size = Math.abs(value);
  if (size < 1e-12) return `0 ${unit}`;
  const [factor, prefix] = PREFIXES.find(([f]) => size >= f * 0.9995) ?? PREFIXES[PREFIXES.length - 1];
  return `${Number((value / factor).toPrecision(3))} ${prefix}${unit}`;
}
