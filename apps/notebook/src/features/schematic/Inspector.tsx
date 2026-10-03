// On the right (drawings start top-left, so this side is usually free): the element selected — its
// label, value (or a meter's reading), a node label's name. A panel like Excalidraw's: sections
// under plain labels, tiles for choices and actions. (A wire or many things selected: no panel — the
// keys, or the bin beside, do what there is to do.)
import { type ReactNode, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { i2cParts, i2cText } from "@/shared/model/i2c";
import type { ElementData, PartDef } from "@/shared/model/types";
import { CodeIcon, PageIcon, Rotate, Trash } from "@/shared/ui/icons";
import { Adjusters, isAdjustable } from "./Adjusters";
import { useKinds } from "./kinds";
import {
  arrowLength,
  hasValue,
  I2C_ADDRESSES,
  isArrow,
  isBoard,
  isComponent,
  isControlled,
  isWaveSource,
  keyLabel,
  keyName,
  kindInfo,
  LED_COLORS,
  wave,
  waveText,
} from "./model";
import { field, Panel, PanelHead, Section, Tile } from "./Panel";

export type Selection =
  | { type: "element"; id: string }
  | { type: "wire"; index: number }
  | { type: "group"; ids: string[]; wires: number[] } // shift + click, shift + drag
  | null;

const place = "top-15 right-3 w-66 max-h-[calc(100%-8rem)] overflow-y-auto text-[14px]";
const hint = "m-0 text-[12px] leading-[1.4] text-faint";

// the board's buttons (a sketch to edit, a program file to load): the icon and the words together, centred
const wide = "flex w-full h-9 gap-2 px-3 items-center justify-center text-[14px] font-medium";

const PREFIXES = ["p", "n", "µ", "m", "k", "M"];

/** An amount (4.7k, 100n): a touch screen's number keys for it, its SI prefixes as buttons under it —
 *  and "abc" for the letters' keys (a value may be a symbol). */
function Amount({
  value,
  onChange,
  unit,
  label,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  unit?: string;
  label: string;
  placeholder?: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [letters, setLetters] = useState(false);
  const touch = matchMedia("(pointer: coarse)").matches;
  /** The prefix after the number set (that one again: taken off). */
  const prefix = (p: string) => {
    const m = /^(.*\d)\s*([pnuµmkM]?)$/.exec(value.trim());
    if (m) onChange(m[1] + (m[2] === p ? "" : p));
  };
  const chip = "h-7 min-w-8 px-2 rounded-md bg-hover text-[13px] text-muted hover:text-fg";
  return (
    <>
      <span className="relative block">
        <input
          ref={input}
          className={cn(field, unit && "pr-8.5")}
          value={value}
          inputMode={letters ? "text" : "decimal"}
          spellCheck={false}
          aria-label={label}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
        {unit && (
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">{unit}</span>
        )}
      </span>
      {touch && (
        // (pressed, the field keeps the keyboard)
        <span className="flex flex-wrap gap-1" onPointerDown={(e) => e.preventDefault()}>
          {PREFIXES.map((p) => (
            <button key={p} type="button" className={chip} onClick={() => prefix(p)}>
              {p}
            </button>
          ))}
          <button
            type="button"
            className={cn(chip, letters && "bg-selected text-fg")}
            aria-pressed={letters}
            onClick={() => {
              setLetters(!letters);
              // (the keyboard changes once the field is taken up again)
              input.current?.blur();
              requestAnimationFrame(() => input.current?.focus());
            }}
          >
            abc
          </button>
        </span>
      )}
    </>
  );
}

export function Inspector({
  element,
  taken,
  components,
  onChange,
  onRename,
  onRotate,
  onRemove,
  icon,
  live,
  onSketch,
  onFirmware,
  part,
  models,
  onSweep,
}: {
  part?: PartDef; // one's own component: its definition
  models?: string[]; // real parts it can be (a 1N4148, an LM358): the element's ``text``, none a generic one
  onSweep?: (lo: string, hi: string) => void; // plot the outputs as its value goes from lo to hi (empty: around it)
  element: ElementData | null;
  taken: string[];
  components: string[]; // the drawing's elements an arrow may be of (their ids)
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRotate: () => void;
  onRemove: () => void;
  icon: ReactNode;
  live?: boolean; // running: only what works as an input (a potentiometer's position, a sensor's reading)
  onSketch?: () => void; // a board: open its sketch
  onFirmware?: (file: File) => void; // a Pico: run a program file (.uf2, .bin) on it
}) {
  const { t } = useTranslation("schematic");
  const { name } = useKinds();
  const [id, setId] = useState(element?.id ?? "");
  const [range, setRange] = useState({ lo: "", hi: "" }); // the sweep's, as typed
  const remove = (
    <Tile
      className="hover:bg-err-bg hover:text-danger"
      onClick={onRemove}
      title={t("inspector.removeTitle")}
      aria-label={t("inspector.remove")}
    >
      <Trash />
    </Tile>
  );
  if (!element) return null;
  const info = kindInfo(element.kind);
  const valueName = info?.meter
    ? t("inspector.reading")
    : element.kind === "sine_source"
      ? t("inspector.amplitude")
      : element.kind === "square_source"
        ? t("inspector.high")
        : element.kind === "zener"
          ? t("inspector.zenerValue")
          : isControlled(element.kind)
            ? t("inspector.gain")
            : element.kind === "transformer"
              ? t("inspector.ratio")
              : t("inspector.value");
  const { frequency, duty, phase } = wave(element.text);
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <Panel className={place} role="group" aria-label={t("inspector.label")}>
      <PanelHead
        icon={icon}
        caption={element.kind === "part" ? (part?.name ?? t("inspector.part")) : name(element.kind)}
        title={isComponent(element.kind) && element.id}
      />
      {!live && isComponent(element.kind) && (
        <Section label={t("inspector.id")}>
          <input
            className={field}
            value={id}
            spellCheck={false}
            aria-label={t("inspector.id")}
            onChange={(e) => setId(e.target.value)}
            onBlur={commitId}
            onKeyDown={(e) => e.key === "Enter" && commitId()}
          />
        </Section>
      )}
      {!live && hasValue(element.kind) && (
        <Section label={valueName}>
          <Amount
            value={element.value ?? ""}
            unit={info?.unit}
            label={valueName}
            placeholder={info?.meter ? t("inspector.noReading") : "?"}
            onChange={(v) => onChange({ value: v.trim() === "" ? null : v })}
          />
          <p className={hint}>{info?.meter ? t("inspector.readingHint") : t("inspector.valueHint")}</p>
        </Section>
      )}
      {!live && isWaveSource(element.kind) && (
        <Section label={t("inspector.frequency")}>
          <Amount
            value={frequency}
            unit={/\d$/.test(frequency) ? "Hz" : undefined}
            label={t("inspector.frequency")}
            onChange={(v) => onChange({ text: waveText(v, duty, phase) })}
          />
          <p className={hint}>{t("inspector.frequencyHint")}</p>
        </Section>
      )}
      {!live && onSweep && hasValue(element.kind) && !kindInfo(element.kind)?.meter && (
        <Section label={t("inspector.sweep")}>
          <span className="flex items-center gap-1.5">
            <input
              className={field}
              value={range.lo}
              inputMode="decimal"
              placeholder={t("inspector.sweepFrom")}
              aria-label={t("inspector.sweepFrom")}
              onChange={(e) => setRange({ ...range, lo: e.target.value })}
            />
            –
            <input
              className={field}
              value={range.hi}
              inputMode="decimal"
              placeholder={t("inspector.sweepTo")}
              aria-label={t("inspector.sweepTo")}
              onChange={(e) => setRange({ ...range, hi: e.target.value })}
            />
            <button
              type="button"
              className="h-8.5 flex-none px-3 rounded-lg bg-primary text-on-primary text-[13px] font-medium hover:bg-primary-hover"
              onClick={() => onSweep(range.lo, range.hi)}
            >
              {t("inspector.sweepRun")}
            </button>
          </span>
          <p className={hint}>{t("inspector.sweepHint")}</p>
        </Section>
      )}
      {!live && models && (
        <Section label={t("inspector.model")}>
          <select
            className={field}
            value={element.text ?? ""}
            aria-label={t("inspector.model")}
            onChange={(e) => onChange({ text: e.target.value || null })}
          >
            <option value="">{t(element.kind === "opamp" ? "inspector.ideal" : "inspector.generic")}</option>
            {models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          {element.kind === "opamp" && <p className={hint}>{t("inspector.opampModelHint")}</p>}
        </Section>
      )}
      {!live && element.kind === "sine_source" && (
        <Section label={t("inspector.phase")}>
          <span className="relative block">
            <input
              className={cn(field, "pr-6")}
              type="number"
              step={1}
              value={phase}
              aria-label={t("inspector.phase")}
              onChange={(e) => onChange({ text: waveText(frequency, duty, Number(e.target.value) || 0) })}
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">°</span>
          </span>
          <p className={hint}>{t("inspector.phaseHint")}</p>
        </Section>
      )}
      {!live && element.kind === "square_source" && (
        <Section label={t("inspector.duty", { percent: duty })}>
          <input
            type="range"
            min={1}
            max={99}
            step={1}
            value={duty}
            className="w-full accent-[var(--accent)]"
            aria-label={t("inspector.duty", { percent: duty })}
            onChange={(e) => onChange({ text: waveText(frequency, Number(e.target.value)) })}
          />
        </Section>
      )}
      {!live && element.kind === "lamp" && (
        <Section label={t("inspector.rated")}>
          <span className="relative block">
            <input
              className={field}
              value={element.text ?? ""}
              inputMode="decimal"
              spellCheck={false}
              aria-label={t("inspector.rated")}
              onChange={(e) => onChange({ text: e.target.value })}
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">W</span>
          </span>
          <p className={hint}>{t("inspector.ratedHint")}</p>
        </Section>
      )}
      {!live && element.kind === "motor" && <p className={hint}>{t("inspector.motorHint")}</p>}
      {!live && element.kind === "part" && (
        <p className={hint}>
          {t("inspector.part")}
          {part && `: ${part.pins.map((p) => p.name).join(", ")}. `}
          {t("inspector.partHint")}
        </p>
      )}
      {!live && element.kind === "relay" && <p className={hint}>{t("inspector.relayHint")}</p>}
      {!live && element.kind.endsWith("_gate") && <p className={hint}>{t("inspector.gateHint")}</p>}
      {!live && element.kind === "led" && (
        <Section label={t("inspector.color")}>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.color")}>
            {(Object.entries(LED_COLORS) as [keyof typeof LED_COLORS, string][]).map(([color, css]) => (
              <button
                key={color}
                role="radio"
                aria-checked={(element.text ?? "red") === color}
                title={t(`inspector.colors.${color}`)}
                aria-label={t(`inspector.colors.${color}`)}
                onClick={() => onChange({ text: color })}
                className={cn(
                  "size-7 rounded-md border border-black/10",
                  (element.text ?? "red") === color && "outline-2 outline-offset-2 outline-accent",
                )}
                style={{ background: css }}
              />
            ))}
          </div>
        </Section>
      )}
      {!live && element.kind === "switch" && (
        <Section label={t("inspector.state")}>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.state")}>
            {([null, "closed"] as const).map((state) => (
              <Tile
                key={state ?? "open"}
                role="radio"
                aria-checked={element.text === state}
                on={element.text === state}
                className="w-auto px-3 text-[13px]"
                onClick={() => onChange({ text: state })}
              >
                {state ? t("inspector.closed") : t("inspector.opened")}
              </Tile>
            ))}
          </div>
          <p className={hint}>{t("inspector.switchHint")}</p>
        </Section>
      )}
      {!live && element.kind === "button" && (
        <Section label={t("inspector.key")}>
          {/* press the key to give it; Backspace takes it away */}
          <input
            className={field}
            readOnly
            value={element.text ? keyLabel(element.text) : ""}
            placeholder={t("inspector.noKey")}
            aria-label={t("inspector.key")}
            onKeyDown={(e) => {
              if (e.key === "Tab") return;
              e.preventDefault();
              onChange({ text: e.key === "Backspace" || e.key === "Delete" ? null : keyName(e.key) });
            }}
          />
          <p className={hint}>{t("inspector.buttonHint")}</p>
        </Section>
      )}
      {!live && isControlled(element.kind) && <p className={hint}>{t("inspector.controlledHint")}</p>}
      {isAdjustable(element.kind) && (
        <Section label={t("inspector.adjust")}>
          <Adjusters element={element} onChange={onChange} />
        </Section>
      )}
      {!live && element.kind === "lcd1602" && <p className={hint}>{t("inspector.lcdHint")}</p>}
      {!live && I2C_ADDRESSES[element.kind] && (
        <Section label={t("inspector.address")}>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.address")}>
            {I2C_ADDRESSES[element.kind].map((a) => (
              <Tile
                key={a}
                role="radio"
                aria-checked={(i2cParts(element.text).address || I2C_ADDRESSES[element.kind][0]) === a}
                on={(i2cParts(element.text).address || I2C_ADDRESSES[element.kind][0]) === a}
                className="w-auto px-3 font-mono text-[13px]"
                onClick={() =>
                  onChange({ text: element.kind === "lcd1602_i2c" ? i2cText(a, i2cParts(element.text).trimmer) : a })
                }
              >
                {a}
              </Tile>
            ))}
          </div>
        </Section>
      )}
      {!live && ["lcd1602_i2c", "ssd1306", "ds1307"].includes(element.kind) && (
        <p className={hint}>{t("inspector.i2cHint")}</p>
      )}
      {!live && element.kind === "ili9341" && <p className={hint}>{t("inspector.spiHint")}</p>}
      {!live && element.kind === "ds1307" && <p className={hint}>{t("inspector.clockHint")}</p>}
      {!live && element.kind === "servo" && <p className={hint}>{t("inspector.servoHint")}</p>}
      {!live && (element.kind === "buzzer" || element.kind === "passive_buzzer") && (
        <p className={hint}>{t(`inspector.${element.kind === "buzzer" ? "buzzerHint" : "passiveBuzzerHint"}`)}</p>
      )}
      {isBoard(element.kind) && onSketch && (
        <Tile className={wide} onClick={onSketch} title={t("inspector.sketchTitle")}>
          <CodeIcon /> {t("inspector.sketch")}
        </Tile>
      )}
      {element.kind === "pico" && onFirmware && <FirmwareTile onFile={onFirmware} />}
      {!live && kindInfo(element.kind)?.live && !isBoard(element.kind) && (
        <p className={hint}>{t(isWaveSource(element.kind) ? "inspector.waveOnly" : "inspector.liveOnly")}</p>
      )}
      {!live && (element.kind === "label" || element.kind === "port") && (
        <Section label={t(element.kind === "port" ? "inspector.port" : "inspector.node")}>
          <input
            className={field}
            value={element.text ?? ""}
            spellCheck={false}
            aria-label={t(element.kind === "port" ? "inspector.port" : "inspector.node")}
            onChange={(e) => onChange({ text: e.target.value })}
          />
          {element.kind === "port" && <p className={hint}>{t("inspector.portHint")}</p>}
        </Section>
      )}
      {!live && isArrow(element.kind) && (
        <Section label={t("inspector.arrowName")}>
          <input
            className={field}
            value={element.text ?? ""}
            spellCheck={false}
            aria-label={t("inspector.arrowName")}
            onChange={(e) => onChange({ text: e.target.value })}
          />
        </Section>
      )}
      {!live && isArrow(element.kind) && (
        <Section label={t("inspector.arrowOf")}>
          <select
            className={field}
            value={element.of ?? ""}
            aria-label={t("inspector.arrowOf")}
            onChange={(e) => onChange({ of: e.target.value || null })}
          >
            <option value="">{t("inspector.arrowOfNone")}</option>
            {components.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
          {element.of && (
            <Amount
              value={element.value ?? ""}
              unit={element.kind === "current_arrow" ? "A" : "V"}
              label={t("inspector.arrowValue")}
              placeholder="?"
              onChange={(v) => onChange({ value: v.trim() === "" ? null : v })}
            />
          )}
          <p className={hint}>{t(element.of ? "inspector.arrowGivenHint" : "inspector.arrowHint")}</p>
        </Section>
      )}
      {!live && element.kind === "voltage_arrow" && (
        <Section label={t("inspector.arrowLength")}>
          <input
            className={field}
            type="number"
            min={1}
            max={40}
            value={arrowLength(element)}
            aria-label={t("inspector.arrowLength")}
            onChange={(e) => onChange({ span: Math.trunc(Number(e.target.value)) || null })}
          />
        </Section>
      )}
      {!live && (
        <Section label={t("inspector.actions")}>
          <div className="flex gap-1.5">
            <Tile onClick={onRotate} title={t("inspector.rotateTitle")} aria-label={t("inspector.rotate")}>
              <Rotate />
            </Tile>
            {remove}
          </div>
        </Section>
      )}
    </Panel>
  );
}

/** A Pico's program from a file: picked here (dropped on the board, it goes the same way). */
function FirmwareTile({ onFile }: { onFile: (file: File) => void }) {
  const { t } = useTranslation("schematic");
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <Tile className={wide} onClick={() => input.current?.click()} title={t("inspector.firmwareTitle")}>
        <PageIcon /> {t("inspector.firmware")}
      </Tile>
      <input
        ref={input}
        type="file"
        accept=".uf2,.bin"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) onFile(file);
        }}
      />
    </>
  );
}
