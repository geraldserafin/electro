// "Save as a component": a drawing becomes one of the user's components. Its ports (the "Port"
// element) are the pins. The dialog is the component itself, large, on the board's grid: drag a pin
// anywhere around the box — to another side, between others — and drag the box's corner to give it
// more room; the name is typed over it. (With the keyboard: pick a pin, then the arrows move it.)
// Saved under a name already taken, it replaces that component (asked first).
import { type PointerEvent as ReactPointerEvent, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { arrange, firstSides, partSvg } from "@/features/schematic";
import { cn } from "@/shared/lib/cn";
import type { PartDef, PartPin, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { Dialog } from "@/shared/ui/Dialog";
import { saveComponent, useComponents } from "./store";

type Side = PartPin["side"];
type Pin = { name: string; side: Side };
// what cannot be inside a component: a board runs its own program, which a box hides
const NOT_INSIDE = new Set(["arduino", "pico"]);
const SCALE = 1.6; // the preview, a size up from the board's
const PAD = 3; // grid squares around the box in the preview

const primary =
  "h-9 px-4 rounded-lg bg-primary text-on-primary text-[14px] font-medium hover:bg-primary-hover disabled:opacity-50";
const quiet = "h-9 px-3.5 rounded-lg text-[14px] hover:bg-hover";

/** ``pins`` with ``name`` moved to ``side``, before the ``index``-th of the others there. */
function moved(pins: Pin[], name: string, side: Side, index: number): Pin[] {
  const rest = pins.filter((p) => p.name !== name);
  const there = rest.map((p, i) => (p.side === side ? i : -1)).filter((i) => i >= 0);
  const at = index < there.length ? there[index] : there.length ? there[there.length - 1] + 1 : rest.length;
  return [...rest.slice(0, at), { name, side }, ...rest.slice(at)];
}

export function SaveComponentDialog({
  schematic,
  name: first,
  library,
  onClose,
}: {
  schematic: SchematicData;
  name: string;
  library: SymbolLibrary;
  onClose: () => void;
}) {
  const { t } = useTranslation("components");
  const mine = useComponents();
  const [name, setName] = useState(first);
  const [pins, setPins] = useState<Pin[]>(() => firstSides(schematic));
  const [more, setMore] = useState<[number, number]>([0, 0]);
  const [picked, setPicked] = useState<string | null>(null);
  const [drag, setDrag] = useState<
    { kind: "pin"; name: string } | { kind: "size"; from: [number, number]; start: [number, number] } | null
  >(null);
  const [state, setState] = useState<"editing" | "saving" | "saved" | "failed">("editing");
  const svg = useRef<SVGSVGElement>(null);
  const boards = schematic.elements.filter((e) => NOT_INSIDE.has(e.kind)).map((e) => e.id);
  const box = useMemo(() => arrange(pins, name.trim() || "?", more), [pins, name, more]);
  const def: PartDef = {
    name: name.trim(),
    ...box,
    schematic: {
      elements: schematic.elements,
      wires: schematic.wires,
      ...(schematic.parts && { parts: schematic.parts }),
    },
    prefix: "U",
  };
  const G = library.grid;
  const [w, h] = box.size;
  const taken = mine.find((c) => c.def.name.toLowerCase() === def.name.toLowerCase());

  /** Where the pointer is, in grid squares from the box's top left corner. */
  const at = (e: { clientX: number; clientY: number }): [number, number] => {
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.current!.getScreenCTM()!.inverse());
    return [p.x / G, p.y / G];
  };

  const onMove = (e: ReactPointerEvent) => {
    if (!drag) return;
    const [x, y] = at(e);
    if (drag.kind === "size") {
      const dx = Math.round((x - drag.from[0]) / 2) * 2;
      const dy = Math.round((y - drag.from[1]) / 2) * 2;
      const next: [number, number] = [Math.max(0, drag.start[0] + dx), Math.max(0, drag.start[1] + dy)];
      if (next[0] !== more[0] || next[1] !== more[1]) setMore(next);
      return;
    }
    // the side nearest the pointer, and where along it among the other pins there
    const distance: Record<Side, number> = {
      left: Math.abs(x) + (y < 0 || y > h ? 2 : 0),
      right: Math.abs(x - w) + (y < 0 || y > h ? 2 : 0),
      top: Math.abs(y) + (x < 0 || x > w ? 2 : 0),
      bottom: Math.abs(y - h) + (x < 0 || x > w ? 2 : 0),
    };
    const side = (Object.keys(distance) as Side[]).reduce((a, b) => (distance[b] < distance[a] ? b : a));
    const along = side === "left" || side === "right" ? y : x;
    const others = box.pins.filter((p) => p.side === side && p.name !== drag.name);
    const index = others.filter((p) => p.at < along).length;
    const next = moved(pins, drag.name, side, index);
    if (next.some((p, i) => p.name !== pins[i].name || p.side !== pins[i].side)) setPins(next);
  };

  /** The keyboard: the arrows move the picked pin — along its side, or round the corner to the next. */
  const onKey = (e: React.KeyboardEvent) => {
    if (!picked || !["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) return;
    e.preventDefault();
    const pin = pins.find((p) => p.name === picked)!;
    const same = box.pins.filter((p) => p.side === pin.side).map((p) => p.name);
    const i = same.indexOf(picked);
    const vertical = pin.side === "left" || pin.side === "right";
    const along: Record<string, number> = vertical ? { ArrowUp: -1, ArrowDown: 1 } : { ArrowLeft: -1, ArrowRight: 1 };
    const step = along[e.key];
    if (step) {
      const to = Math.max(0, Math.min(same.length - 1, i + step));
      setPins(moved(pins, picked, pin.side, to));
      return;
    }
    const side: Side = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "top", ArrowDown: "bottom" }[
      e.key as "ArrowLeft"
    ] as Side;
    setPins(moved(pins, picked, side, Infinity));
  };

  const save = async () => {
    if (taken && !confirm(t("replace", { name: taken.def.name }))) return;
    setState("saving");
    try {
      await saveComponent(def, taken?.id);
      setState("saved");
    } catch (e) {
      console.warn("The component could not be saved", e);
      setState("failed");
    }
  };

  if (!pins.length || boards.length || state === "saved")
    return (
      <Dialog label={t("title")} onClose={onClose}>
        <h2 className="m-0 mb-1 text-[17px] font-medium">{t("title")}</h2>
        <p className="m-0 text-[14px] leading-relaxed">
          {state === "saved"
            ? t("saved", { name: def.name })
            : boards.length
              ? t("noBoards", { ids: boards.join(", ") })
              : t("noPorts")}
        </p>
        <div className="flex justify-end">
          <button className={state === "saved" ? primary : quiet} onClick={onClose}>
            {state === "saved" ? t("done") : t("close")}
          </button>
        </div>
      </Dialog>
    );

  const view = [-PAD * G, -PAD * G, (w + 2 * PAD) * G, (h + 2 * PAD) * G];
  const offsets = box.pins.map((p) =>
    p.side === "left" ? [-1, p.at] : p.side === "right" ? [w + 1, p.at] : p.side === "top" ? [p.at, -1] : [p.at, h + 1],
  );

  return (
    <Dialog label={t("title")} onClose={onClose} className="max-w-190 gap-4 p-5">
      <div className="grid gap-1">
        <h2 className="m-0 text-[17px] font-medium">{t("title")}</h2>
        <p className="m-0 text-[13px] text-muted leading-relaxed">{t("intro")}</p>
      </div>

      <div className="grid grid-cols-[1fr_200px] gap-5 min-h-0">
        {/* the component, large, on the board's grid: drag its pins and its corner */}
        <div
          className="relative grid place-items-center min-h-72 max-h-[52vh] overflow-auto rounded-xl border border-line bg-board outline-none focus-visible:outline-2 focus-visible:outline-accent"
          style={{
            backgroundImage: "radial-gradient(circle, var(--faint) 1px, transparent 1.2px)",
            backgroundSize: `${G * SCALE}px ${G * SCALE}px`,
          }}
          tabIndex={0}
          onKeyDown={onKey}
          aria-label={t("preview")}
        >
          <svg
            ref={svg}
            viewBox={view.join(" ")}
            width={view[2] * SCALE}
            height={view[3] * SCALE}
            className={cn("text-fg touch-none select-none", drag && "cursor-grabbing")}
            onPointerMove={onMove}
            onPointerUp={() => setDrag(null)}
            onPointerLeave={() => setDrag(null)}
          >
            <style>{library.style}</style>
            <g className="w" dangerouslySetInnerHTML={{ __html: partSvg({ ...def, name: def.name || "?" }, G) }} />
            {box.pins.map((p, i) => {
              const [x, y] = offsets[i];
              const on = picked === p.name || (drag?.kind === "pin" && drag.name === p.name);
              return (
                <g
                  key={p.name}
                  className="cursor-grab"
                  onPointerDown={(e) => {
                    e.currentTarget.ownerSVGElement?.setPointerCapture?.(e.pointerId);
                    setPicked(p.name);
                    setDrag({ kind: "pin", name: p.name });
                  }}
                >
                  <circle cx={x * G} cy={y * G} r={9} fill="transparent" />
                  <circle
                    cx={x * G}
                    cy={y * G}
                    r={on ? 5 : 3.5}
                    className={on ? "fill-accent" : "fill-paper"}
                    stroke="currentColor"
                    strokeWidth={1.5}
                  />
                </g>
              );
            })}
            {/* the corner: more room */}
            <g
              className="cursor-nwse-resize"
              onPointerDown={(e) => {
                e.currentTarget.ownerSVGElement?.setPointerCapture?.(e.pointerId);
                setDrag({ kind: "size", from: at(e), start: more });
              }}
            >
              <rect x={w * G - 7} y={h * G - 7} width={14} height={14} fill="transparent" />
              <path
                d={`M${w * G - 8} ${h * G - 2}L${w * G - 2} ${h * G - 8}M${w * G - 4} ${h * G - 2}L${w * G - 2} ${h * G - 4}`}
                className="stroke-muted"
                strokeWidth={1.5}
                fill="none"
              />
            </g>
          </svg>
          <span className="absolute left-3 bottom-2 text-[12px] text-faint pointer-events-none">{t("dragHint")}</span>
        </div>

        <div className="grid content-start gap-4">
          <label className="grid gap-1.5 text-[12px] font-medium text-muted uppercase tracking-wide">
            {t("name")}
            <input
              className="h-9 px-3 rounded-lg border border-line bg-paper text-[15px] font-normal normal-case tracking-normal text-fg outline-none focus:border-accent"
              value={name}
              maxLength={40}
              autoFocus
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && def.name && void save()}
            />
            {taken && <span className="font-normal normal-case tracking-normal text-warn">{t("willReplace")}</span>}
          </label>
          <div className="grid gap-1.5">
            <span className="text-[12px] font-medium text-muted uppercase tracking-wide">{t("pins")}</span>
            <div className="flex flex-wrap gap-1.5">
              {pins.map((p) => (
                <button
                  key={p.name}
                  className={cn(
                    "px-2 h-7 rounded-md border font-mono text-[12px]",
                    picked === p.name ? "border-accent bg-accent-soft text-fg" : "border-line hover:border-fg",
                  )}
                  title={t(`sides.${p.side}`)}
                  onClick={() => setPicked(picked === p.name ? null : p.name)}
                  onKeyDown={onKey}
                >
                  {p.name}
                </button>
              ))}
            </div>
            <span className="text-[12px] text-faint leading-snug">{t("keysHint")}</span>
          </div>
          <div className="grid gap-1 text-[12px] text-faint">
            <span>
              {t("size")}:{" "}
              <span className="font-mono text-muted">
                {w} × {h}
              </span>
            </span>
            {(more[0] > 0 || more[1] > 0) && (
              <button className="w-fit text-accent hover:underline" onClick={() => setMore([0, 0])}>
                {t("fit")}
              </button>
            )}
          </div>
        </div>
      </div>

      {state === "failed" && <p className="m-0 text-[13px] text-danger">{t("failed")}</p>}
      <div className="flex justify-end gap-2">
        <button className={quiet} onClick={onClose}>
          {t("cancel")}
        </button>
        <button className={primary} disabled={!def.name || state === "saving"} onClick={() => void save()}>
          {state === "saving" ? t("saving") : taken ? t("replaceButton") : t("save")}
        </button>
      </div>
    </Dialog>
  );
}
