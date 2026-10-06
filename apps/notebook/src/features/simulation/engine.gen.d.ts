// What engine.gen.js (electro/numeric/engine.py printed by scripts/engine_js.py) gives.
export const Machine: new (program: object, system: unknown, update: unknown) => unknown;
export const System: new (shape: object, jconst: unknown, jdyn: unknown) => unknown;
export class NoConvergence extends Error {
  time: number;
}
export function limited_exp(x: number): number;
export function limited_exp_slope(x: number): number;
