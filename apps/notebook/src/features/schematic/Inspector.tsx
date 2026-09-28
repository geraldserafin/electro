// On the right (drawings start top-left, so this side is usually free): what is selected — an
// element's label, value (or a meter's reading), a node label's name; or a wire, or a group.
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ElementData } from "@/shared/model/types";
import { cn } from "@/shared/lib/cn";
import { Rotate, Trash } from "@/shared/ui/icons";
import { BoardButton, BoardIsland } from "./Board";
import { useKinds } from "./kinds";
import { LED_COLORS, hasValue, isComponent, kindInfo } from "./model";

export type Selection =
  | { type: "element"; id: string }
  | { type: "wire"; index: number }
  | { type: "group"; ids: string[]; wires: number[] } // from shift + drag
  | null;

const island = "top-16 right-3 w-62 flex-col items-stretch gap-3 p-3 text-[14px]";
const caption = "text-[12px] font-medium text-muted";
const input = "w-full px-2.5 py-1.75 rounded-lg border border-transparent bg-hover text-[15px] focus:bg-paper focus:outline-2 focus:outline-accent-soft";

function Header({ icon, title, subtitle, children }: { icon?: ReactNode; title: string; subtitle?: ReactNode; children: ReactNode }) {
  return (
    <header className="flex items-center gap-2.5">
      {icon && <span className="grid place-items-center flex-none size-10 rounded-[10px] bg-hover text-fg">{icon}</span>}
      <div className="grid flex-1 min-w-0">
        <h4 className={cn(caption, "m-0 truncate")}>{title}</h4>
        {subtitle && <span className="text-[16px] font-semibold">{subtitle}</span>}
      </div>
      <div className="flex gap-0.5">{children}</div>
    </header>
  );
}

export function Inspector({ selection, element, taken, onChange, onRename, onRotate, onRemove, icon }: {
  selection: Selection;
  element: ElementData | null;
  taken: string[];
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRotate: () => void;
  onRemove: () => void;
  icon: ReactNode;
}) {
  const { t } = useTranslation("schematic");
  const { name } = useKinds();
  const [id, setId] = useState(element?.id ?? "");
  const remove = (
    <BoardButton icon className="text-danger hover:bg-err-bg" onClick={onRemove} title={t("inspector.removeTitle")}
                 aria-label={t("inspector.remove")}><Trash /></BoardButton>
  );
  if (selection?.type === "group" || selection?.type === "wire")
    return (
      <BoardIsland className={island} role="group" aria-label={t("inspector.label")}>
        <Header title={selection.type === "group" ? t("inspector.selection") : t("inspector.wire")}
                subtitle={selection.type === "group" && t("inspector.count", { elements: selection.ids.length, wires: selection.wires.length })}>
          {remove}
        </Header>
        {selection.type === "group" && <p className="m-0 text-[13px] text-muted">{t("inspector.dragAll")}</p>}
      </BoardIsland>
    );
  if (!element) return null;
  const info = kindInfo(element.kind);
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <BoardIsland className={island} role="group" aria-label={t("inspector.label")}>
      <Header icon={icon} title={name(element.kind)} subtitle={isComponent(element.kind) && element.id}>
        <BoardButton icon onClick={onRotate} title={t("inspector.rotateTitle")} aria-label={t("inspector.rotate")}><Rotate /></BoardButton>
        {remove}
      </Header>
      {isComponent(element.kind) && (
        <label className="grid gap-1">
          <span className={caption}>{t("inspector.id")}</span>
          <input className={input} value={id} spellCheck={false} onChange={(e) => setId(e.target.value)} onBlur={commitId}
                 onKeyDown={(e) => e.key === "Enter" && commitId()} />
        </label>
      )}
      {hasValue(element.kind) && (
        <label className="grid gap-1">
          <span className={caption}>{info?.meter ? t("inspector.reading") : t("inspector.value")}</span>
          <span className="relative block">
            <input className={cn(input, "pr-8.5")} value={element.value ?? ""} spellCheck={false}
                   placeholder={info?.meter ? t("inspector.noReading") : "?"}
                   onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })} />
            {info?.unit && <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none">{info.unit}</span>}
          </span>
          <small className="text-[12px] leading-[1.35] text-faint">{info?.meter ? t("inspector.readingHint") : t("inspector.valueHint")}</small>
        </label>
      )}
      {element.kind === "led" && (
        <div className="grid gap-1">
          <span className={caption}>{t("inspector.color")}</span>
          <div className="flex gap-1.5" role="radiogroup" aria-label={t("inspector.color")}>
            {(Object.entries(LED_COLORS) as [keyof typeof LED_COLORS, string][]).map(([color, css]) => (
              <button key={color} role="radio" aria-checked={(element.text ?? "red") === color} title={t(`inspector.colors.${color}`)}
                      aria-label={t(`inspector.colors.${color}`)} onClick={() => onChange({ text: color })}
                      className={cn("size-6 rounded-full border border-line", (element.text ?? "red") === color && "outline-2 outline-offset-2 outline-accent")}
                      style={{ background: css }} />
            ))}
          </div>
        </div>
      )}
      {element.kind === "switch" && (
        <label className="flex items-center gap-2 text-[14px]">
          <input type="checkbox" checked={element.text === "closed"} onChange={(e) => onChange({ text: e.target.checked ? "closed" : null })} />
          {t("inspector.closed")}
        </label>
      )}
      {(element.kind === "switch" || element.kind === "button") && (
        <small className="text-[12px] leading-[1.35] text-faint">{t(`inspector.${element.kind}Hint`)}</small>
      )}
      {element.kind === "potentiometer" && (
        <label className="grid gap-1">
          <span className={caption}>{t("inspector.position", { percent: Math.round(Number(element.text ?? 0.5) * 100) })}</span>
          <input type="range" min={0} max={1} step={0.01} value={Number(element.text ?? 0.5)}
                 onChange={(e) => onChange({ text: e.target.value })} />
        </label>
      )}
      {element.kind === "arduino" && <p className="m-0 text-[13px] text-muted">{t("inspector.sketchHint")}</p>}
      {kindInfo(element.kind)?.live && element.kind !== "arduino" && (
        <p className="m-0 text-[13px] text-muted">{t("inspector.liveOnly")}</p>
      )}
      {element.kind === "label" && (
        <label className="grid gap-1">
          <span className={caption}>{t("inspector.node")}</span>
          <input className={input} value={element.text ?? ""} spellCheck={false} onChange={(e) => onChange({ text: e.target.value })} />
        </label>
      )}
    </BoardIsland>
  );
}
