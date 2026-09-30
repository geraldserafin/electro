// What of an element can be turned while the circuit runs — a potentiometer's wiper, the light on a
// photoresistor, a thermistor's temperature, how far an HC-SR04's obstacle is, an I²C LCD's contrast
// trimmer — as sliders: in its panel (Inspector) and in the simulation's own tab. Each writes the
// element's text, as the drawing keeps it.
import { useTranslation } from "react-i18next";
import { i2cParts, i2cText } from "@/shared/model/i2c";
import type { ElementData } from "@/shared/model/types";

/** One slider: its position (in its own units), and the element's text for a position. */
interface Adjuster {
  label: "position" | "lux" | "temperature" | "distance" | "trimmer"; // under inspector. in messages.ts
  params: (v: number) => Record<string, string | number>;
  min: number;
  max: number;
  step: number;
  value: number;
  text: (v: number) => string;
  hint?: "luxHint" | "distanceHint" | "trimmerHint";
}

const percent = (v: number) => Math.round(v * 100);

export function adjustersOf(e: ElementData): Adjuster[] {
  const n = (fallback: number) => Number(e.text ?? fallback);
  switch (e.kind) {
    case "potentiometer":
      return [
        {
          label: "position",
          params: (v) => ({ percent: percent(v) }),
          min: 0,
          max: 1,
          step: 0.01,
          value: n(0.5),
          text: String,
        },
      ];
    case "photoresistor": {
      // a log scale: 1 lx (night) to 100 000 lx (sunlight)
      const lux = Math.max(1, n(100) || 100);
      const shown = (v: number) => (10 ** v < 10 ? (10 ** v).toFixed(1) : String(Math.round(10 ** v)));
      return [
        {
          label: "lux",
          params: (v) => ({ lux: shown(v) }),
          min: 0,
          max: 5,
          step: 0.01,
          value: Math.log10(lux),
          text: shown,
          hint: "luxHint",
        },
      ];
    }
    case "thermistor":
      return [
        { label: "temperature", params: (v) => ({ t: v }), min: -20, max: 120, step: 1, value: n(25), text: String },
      ];
    case "ultrasonic":
      return [
        {
          label: "distance",
          params: (v) => ({ cm: v }),
          min: 2,
          max: 450,
          step: 1,
          value: n(100) || 100,
          text: String,
          hint: "distanceHint",
        },
      ];
    case "lcd1602_i2c": {
      const { address, trimmer } = i2cParts(e.text);
      return [
        {
          label: "trimmer",
          params: (v) => ({ percent: percent(v) }),
          min: 0,
          max: 1,
          step: 0.01,
          value: trimmer,
          text: (v) => i2cText(address || "0x27", v),
          hint: "trimmerHint",
        },
      ];
    }
    default:
      return [];
  }
}

/** Set while it runs, from its panel or the simulation's tab. */
export const isAdjustable = (kind: string) =>
  adjustersOf({ id: "", kind, at: [0, 0], rotation: 0, value: null, text: null }).length > 0;

export function Adjusters({
  element,
  onChange,
  hints = true,
  className,
}: {
  element: ElementData;
  onChange: (patch: Partial<ElementData>) => void;
  hints?: boolean;
  className?: string;
}) {
  const { t } = useTranslation("schematic");
  return adjustersOf(element).map((a) => {
    const label =
      element.kind === "ultrasonic" && a.value > 400
        ? t("inspector.farAway")
        : t(`inspector.${a.label}`, a.params(a.value));
    return (
      <label key={a.label} className={className ?? "flex flex-col gap-1.5"}>
        <span className="text-[12px] text-muted">{label}</span>
        <input
          type="range"
          min={a.min}
          max={a.max}
          step={a.step}
          value={a.value}
          className="w-full accent-[var(--accent)]"
          aria-label={label}
          onChange={(ev) => onChange({ text: a.text(Number(ev.target.value)) })}
        />
        {hints && a.hint && <span className="text-[12px] leading-[1.4] text-faint">{t(`inspector.${a.hint}`)}</span>}
      </label>
    );
  });
}
