// On the right (drawings start top-left, so this side is usually free): the element selected — its
// label, value (or a meter's reading), a node label's name. A panel like Excalidraw's: sections
// under plain labels, tiles for choices and actions. (A wire or many things selected: no panel —
// the keys do what there is to do.)
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ElementData } from "@/shared/model/types";
import { cn } from "@/shared/lib/cn";
import { CodeIcon, Rotate, Trash } from "@/shared/ui/icons";
import { useKinds } from "./kinds";
import { LED_COLORS, hasValue, isComponent, isControlled, isWaveSource, kindInfo, wave, waveText } from "./model";
import { field, Panel, PanelHead, Section, Tile } from "./Panel";

export type Selection =
  | { type: "element"; id: string }
  | { type: "wire"; index: number }
  | { type: "group"; ids: string[]; wires: number[] } // shift + click, shift + drag
  | null;

const place = "top-15 right-3 w-66 max-h-[calc(100%-8rem)] overflow-y-auto text-[14px]";
const hint = "m-0 text-[12px] leading-[1.4] text-faint";

export function Inspector({ element, taken, onChange, onRename, onRotate, onRemove, icon, live, onSketch }: {
  element: ElementData | null;
  taken: string[];
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRotate: () => void;
  onRemove: () => void;
  icon: ReactNode;
  live?: boolean; // running: only what works as an input (a potentiometer's position, a sensor's reading)
  onSketch?: () => void; // an Arduino: open its sketch
}) {
  const { t } = useTranslation("schematic");
  const { name } = useKinds();
  const [id, setId] = useState(element?.id ?? "");
  const remove = (
    <Tile className="hover:bg-err-bg hover:text-danger" onClick={onRemove} title={t("inspector.removeTitle")} aria-label={t("inspector.remove")}><Trash /></Tile>
  );
  if (!element) return null;
  const info = kindInfo(element.kind);
  const valueName = info?.meter ? t("inspector.reading") : element.kind === "sine_source" ? t("inspector.amplitude")
    : element.kind === "square_source" ? t("inspector.high") : element.kind === "zener" ? t("inspector.zenerValue")
    : isControlled(element.kind) ? t("inspector.gain") : t("inspector.value");
  const { frequency, duty } = wave(element.text);
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <Panel className={place} role="group" aria-label={t("inspector.label")}>
      <PanelHead icon={icon} caption={name(element.kind)} title={isComponent(element.kind) && element.id} />
      {!live && isComponent(element.kind) && (
        <Section label={t("inspector.id")}>
          <input className={field} value={id} spellCheck={false} aria-label={t("inspector.id")} onChange={(e) => setId(e.target.value)}
                 onBlur={commitId} onKeyDown={(e) => e.key === "Enter" && commitId()} />
        </Section>
      )}
      {!live && hasValue(element.kind) && (
        <Section label={valueName}>
          <span className="relative block">
            <input className={cn(field, "pr-8.5")} value={element.value ?? ""} spellCheck={false}
                   aria-label={valueName}
                   placeholder={info?.meter ? t("inspector.noReading") : "?"}
                   onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })} />
            {info?.unit && <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">{info.unit}</span>}
          </span>
          <p className={hint}>{info?.meter ? t("inspector.readingHint") : t("inspector.valueHint")}</p>
        </Section>
      )}
      {!live && isWaveSource(element.kind) && (
        <Section label={t("inspector.frequency")}>
          <span className="relative block">
            <input className={cn(field, "pr-8.5")} value={frequency} spellCheck={false} aria-label={t("inspector.frequency")}
                   onChange={(e) => onChange({ text: waveText(e.target.value, duty) })} />
            {/\d$/.test(frequency) && <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">Hz</span>}
          </span>
          <p className={hint}>{t("inspector.frequencyHint")}</p>
        </Section>
      )}
      {!live && element.kind === "square_source" && (
        <Section label={t("inspector.duty", { percent: duty })}>
          <input type="range" min={1} max={99} step={1} value={duty} className="w-full accent-[var(--accent)]"
                 aria-label={t("inspector.duty", { percent: duty })}
                 onChange={(e) => onChange({ text: waveText(frequency, Number(e.target.value)) })} />
        </Section>
      )}
      {!live && element.kind === "led" && (
        <Section label={t("inspector.color")}>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.color")}>
            {(Object.entries(LED_COLORS) as [keyof typeof LED_COLORS, string][]).map(([color, css]) => (
              <button key={color} role="radio" aria-checked={(element.text ?? "red") === color} title={t(`inspector.colors.${color}`)}
                      aria-label={t(`inspector.colors.${color}`)} onClick={() => onChange({ text: color })}
                      className={cn("size-7 rounded-md border border-black/10",
                                    (element.text ?? "red") === color && "outline-2 outline-offset-2 outline-accent")}
                      style={{ background: css }} />
            ))}
          </div>
        </Section>
      )}
      {!live && element.kind === "switch" && (
        <Section label={t("inspector.state")}>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.state")}>
            {([null, "closed"] as const).map((state) => (
              <Tile key={state ?? "open"} role="radio" aria-checked={element.text === state} on={element.text === state}
                    className="w-auto px-3 text-[13px]" onClick={() => onChange({ text: state })}>
                {state ? t("inspector.closed") : t("inspector.opened")}
              </Tile>
            ))}
          </div>
          <p className={hint}>{t("inspector.switchHint")}</p>
        </Section>
      )}
      {!live && element.kind === "button" && <p className={hint}>{t("inspector.buttonHint")}</p>}
      {!live && isControlled(element.kind) && <p className={hint}>{t("inspector.controlledHint")}</p>}
      {element.kind === "potentiometer" && (
        <Section label={t("inspector.position", { percent: Math.round(Number(element.text ?? 0.5) * 100) })}>
          <input type="range" min={0} max={1} step={0.01} value={Number(element.text ?? 0.5)} className="w-full accent-[var(--accent)]"
                 aria-label={t("inspector.position", { percent: Math.round(Number(element.text ?? 0.5) * 100) })}
                 onChange={(e) => onChange({ text: e.target.value })} />
        </Section>
      )}
      {element.kind === "photoresistor" && (() => {
        const lux = Math.max(1, Number(element.text ?? 100) || 100);
        const shown = lux < 10 ? lux.toFixed(1) : String(Math.round(lux));
        return (
          <Section label={t("inspector.lux", { lux: shown })}>
            <input type="range" min={0} max={5} step={0.01} value={Math.log10(lux)} className="w-full accent-[var(--accent)]"
                   aria-label={t("inspector.lux", { lux: shown })}
                   onChange={(e) => { const v = 10 ** Number(e.target.value); onChange({ text: v < 10 ? v.toFixed(1) : String(Math.round(v)) }); }} />
            <p className={hint}>{t("inspector.luxHint")}</p>
          </Section>
        );
      })()}
      {element.kind === "thermistor" && (
        <Section label={t("inspector.temperature", { t: Number(element.text ?? 25) })}>
          <input type="range" min={-20} max={120} step={1} value={Number(element.text ?? 25)} className="w-full accent-[var(--accent)]"
                 aria-label={t("inspector.temperature", { t: Number(element.text ?? 25) })}
                 onChange={(e) => onChange({ text: e.target.value })} />
        </Section>
      )}
      {element.kind === "ultrasonic" && (() => {
        const cm = Number(element.text ?? 100) || 100;
        const label = cm > 400 ? t("inspector.farAway") : t("inspector.distance", { cm });
        return (
          <Section label={label}>
            <input type="range" min={2} max={450} step={1} value={cm} className="w-full accent-[var(--accent)]" aria-label={label}
                   onChange={(e) => onChange({ text: e.target.value })} />
            <p className={hint}>{t("inspector.distanceHint")}</p>
          </Section>
        );
      })()}
      {!live && element.kind === "lcd1602" && <p className={hint}>{t("inspector.lcdHint")}</p>}
      {!live && element.kind === "servo" && <p className={hint}>{t("inspector.servoHint")}</p>}
      {!live && (element.kind === "buzzer" || element.kind === "passive_buzzer") && <p className={hint}>{t(`inspector.${element.kind === "buzzer" ? "buzzerHint" : "passiveBuzzerHint"}`)}</p>}
      {element.kind === "arduino" && onSketch && (
        <Tile className="w-full h-9 gap-2 px-3 grid-flow-col text-[14px] font-medium" onClick={onSketch} title={t("inspector.sketchTitle")}>
          <CodeIcon /> {t("inspector.sketch")}
        </Tile>
      )}
      {!live && kindInfo(element.kind)?.live && element.kind !== "arduino" &&
        <p className={hint}>{t(isWaveSource(element.kind) ? "inspector.waveOnly" : "inspector.liveOnly")}</p>}
      {!live && element.kind === "label" && (
        <Section label={t("inspector.node")}>
          <input className={field} value={element.text ?? ""} spellCheck={false} aria-label={t("inspector.node")}
                 onChange={(e) => onChange({ text: e.target.value })} />
        </Section>
      )}
      {!live && (
        <Section label={t("inspector.actions")}>
          <div className="flex gap-1.5">
            <Tile onClick={onRotate} title={t("inspector.rotateTitle")} aria-label={t("inspector.rotate")}><Rotate /></Tile>
            {remove}
          </div>
        </Section>
      )}
    </Panel>
  );
}
