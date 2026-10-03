// On the right (drawings start top-left, so this side is usually free): the element selected — its
// label, its value (or a meter's reading), what to do with it. Running: only what works as an input (a
// potentiometer's position, a sensor's reading). (A wire or many things selected: no panel — the keys,
// or the bin beside, do what there is to do.)
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { ElementData } from "@/shared/model/types";
import { Rotate, Trash } from "@/shared/ui/icons";
import { Adjusters, isAdjustable } from "./Adjusters";
import { useKinds } from "./kinds";
import { hasValue, isArrow, isComponent, isControlled, kindInfo } from "./model";
import { field, Panel, Section, Tile } from "./Panel";

export type Selection =
  | { type: "element"; id: string }
  | { type: "wire"; index: number }
  | { type: "group"; ids: string[]; wires: number[] } // shift + click, shift + drag
  | null;

// (a phone: a sheet from the bottom, the drawing above it in view)
const place =
  "top-15 right-3 w-66 max-h-[calc(100%-8rem)] overflow-y-auto text-[14px] animate-panel-in motion-reduce:animate-none " +
  "max-sm:top-auto max-sm:inset-x-0 max-sm:bottom-0 max-sm:z-6 max-sm:w-auto max-sm:max-h-[45%] max-sm:rounded-b-none max-sm:pt-2 max-sm:shadow-[0_-4px_16px_rgb(0_0_0/0.12)] max-sm:animate-sheet-in";

export function Inspector({
  element,
  taken,
  onChange,
  onRename,
  onRotate,
  onRemove,
  live,
}: {
  element: ElementData | null;
  taken: string[];
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRotate: () => void;
  onRemove: () => void;
  live?: boolean; // running: only what works as an input
}) {
  const { t } = useTranslation("schematic");
  const { name } = useKinds();
  const [id, setId] = useState(element?.id ?? "");
  useEffect(() => setId(element?.id ?? ""), [element?.id]); // (another one picked: the panel stays, its label anew)
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
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <Panel className={place} role="group" aria-label={t("inspector.label")}>
      <span aria-hidden className="hidden max-sm:block flex-none self-center w-9 h-1 rounded-full bg-line" />
      {/* what it is */}
      <h3 className="m-0 text-[15px] font-semibold">
        {element.kind === "part" ? t("inspector.part") : name(element.kind)}
      </h3>
      {!live && isComponent(element.kind) && (
        <Section label={t("inspector.id")}>
          <span className="relative block">
            <input
              className={cn(field, "pr-10")}
              value={id}
              spellCheck={false}
              aria-label={t("inspector.id")}
              onChange={(e) => setId(e.target.value)}
              onBlur={commitId}
              onKeyDown={(e) => e.key === "Enter" && commitId()}
            />
            {/* its label on the other side of it */}
            <button
              type="button"
              className={cn(
                "absolute right-1 top-1/2 -translate-y-1/2 grid place-items-center size-7 rounded-md text-muted hover:bg-selected hover:text-fg",
                element.flip && "text-accent",
              )}
              aria-pressed={!!element.flip}
              title={t("inspector.flipLabel")}
              aria-label={t("inspector.flipLabel")}
              onClick={() => onChange({ flip: element.flip ? null : true })}
            >
              <svg
                viewBox="0 0 24 24"
                width={16}
                height={16}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M7 4v16M7 4L4 7M7 4l3 3M17 20V4M17 20l-3-3M17 20l3-3" />
              </svg>
            </button>
          </span>
        </Section>
      )}
      {!live && hasValue(element.kind) && (
        <Section label={valueName}>
          <span className="relative block">
            <input
              className={cn(field, info?.unit && "pr-8.5")}
              value={element.value ?? ""}
              inputMode="decimal"
              spellCheck={false}
              aria-label={valueName}
              placeholder={info?.meter ? t("inspector.noReading") : "?"}
              onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })}
            />
            {info?.unit && (
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
                {info.unit}
              </span>
            )}
          </span>
        </Section>
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
        </Section>
      )}
      {/* an arrow: its name (U, I_2), the amount it is — given (the solver's), or empty: what it comes to */}
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
        <Section label={t("inspector.arrowValue")}>
          <span className="relative block">
            <input
              className={cn(field, "pr-8.5")}
              value={element.value ?? ""}
              inputMode="decimal"
              spellCheck={false}
              placeholder="?"
              aria-label={t("inspector.arrowValue")}
              onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })}
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
              {element.kind === "current_arrow" ? "A" : "V"}
            </span>
          </span>
        </Section>
      )}
      {/* a net label: its node's potential, against ground — given (the solver's), or empty */}
      {!live && element.kind === "label" && (
        <Section label={t("inspector.potential")}>
          <span className="relative block">
            <input
              className={cn(field, "pr-8.5")}
              value={element.value ?? ""}
              inputMode="decimal"
              spellCheck={false}
              placeholder="?"
              aria-label={t("inspector.potential")}
              onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })}
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">V</span>
          </span>
        </Section>
      )}
      {isAdjustable(element.kind) && (
        <Section label={t("inspector.adjust")}>
          <Adjusters element={element} onChange={onChange} />
        </Section>
      )}
      {!live && (
        <Section label={t("inspector.actions")}>
          <div className="flex gap-1.5">
            <Tile onClick={onRotate} title={t("inspector.rotateTitle")} aria-label={t("inspector.rotate")}>
              <Rotate />
            </Tile>
            <Tile
              className="hover:bg-err-bg hover:text-danger"
              onClick={onRemove}
              title={t("inspector.removeTitle")}
              aria-label={t("inspector.remove")}
            >
              <Trash />
            </Tile>
          </div>
        </Section>
      )}
    </Panel>
  );
}
