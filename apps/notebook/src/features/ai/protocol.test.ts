import { describe, expect, it } from "vitest";
import { jsonOf } from "./protocol";

describe("a model's JSON read", () => {
  it("without what comes after it", () => {
    expect(jsonOf<{ a: string[] }>('```json\n{"a": ["}{"]}\n]}\n"\n}]}')).toEqual({ a: ["}{"] });
  });

  it("keeps its LaTeX", () => {
    const raw = String.raw`{"s": "$U\frac{R_1}{R_2}\,\Omega$ \text{V} \underline{\qquad}\nNowa linia \\beta \"q\" é"}`;
    expect(jsonOf<{ s: string }>(raw).s).toBe(
      `${String.raw`$U\frac{R_1}{R_2}\,\Omega$ \text{V} \underline{\qquad}`}\nNowa linia \\beta "q" é`,
    );
  });
});
