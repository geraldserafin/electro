// The simulation panel's controls tab: everything on the board that can be turned, flipped or held
// while it runs, in one place — sliders (potentiometers, sensors' readings, an LCD's contrast), the
// switches and buttons — and what the meters read, as they read it.
import { useTranslation } from "react-i18next";
import { Adjusters, isAdjustable, useKinds } from "@/features/schematic";
import { cn } from "@/shared/lib/cn";
import type { ElementData } from "@/shared/model/types";
import type { Live } from "./useLive";

const card = "flex flex-col gap-2 min-w-52 flex-1 max-w-80 rounded-lg border border-line bg-board p-2.5";
const toggle = "h-7 px-3 rounded-md border border-line text-[13px]";

/** What the tab has something for: an element to turn, flip or hold, or a meter to read. */
export const controlled = (e: ElementData) =>
  isAdjustable(e.kind) || ["switch", "button", "voltmeter", "ammeter"].includes(e.kind);

export function Controls({
  live,
  elements,
  pressed,
  onElement,
  onPress,
  full,
}: {
  live: Live;
  elements: ElementData[];
  pressed: string[]; // buttons held down
  onElement: (id: string, patch: Partial<ElementData>) => void;
  onPress: (id: string, down: boolean) => void;
  full?: boolean;
}) {
  const { t } = useTranslation("simulation");
  const { name } = useKinds();
  const inputs = elements.filter((e) => controlled(e) && !["voltmeter", "ammeter"].includes(e.kind));
  const meters = elements.filter((e) => e.kind === "voltmeter" || e.kind === "ammeter");
  const head = (e: ElementData) => (
    <span className="flex items-baseline gap-1.5 text-[13px]">
      <span className="font-mono text-fg">{e.id}</span>
      <span className="text-faint truncate">{name(e.kind)}</span>
    </span>
  );
  return (
    <div className={cn("flex flex-col gap-3 overflow-auto p-2.5", full ? "flex-1 min-h-0" : "max-h-72")}>
      {inputs.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("controls.inputs")}>
          {inputs.map((e) => (
            <div key={e.id} className={card}>
              {head(e)}
              {isAdjustable(e.kind) && (
                <Adjusters element={e} onChange={(patch) => onElement(e.id, patch)} hints={false} />
              )}
              {e.kind === "switch" && (
                <button
                  className={cn(toggle, e.text === "closed" ? "bg-accent-soft text-fg" : "text-muted hover:bg-hover")}
                  aria-pressed={e.text === "closed"}
                  onClick={() => onElement(e.id, { text: e.text === "closed" ? null : "closed" })}
                >
                  {e.text === "closed" ? t("controls.closed") : t("controls.open")}
                </button>
              )}
              {e.kind === "button" && (
                <button
                  className={cn(
                    toggle,
                    pressed.includes(e.id) ? "bg-accent-soft text-fg" : "text-muted hover:bg-hover",
                  )}
                  onPointerDown={(ev) => {
                    ev.currentTarget.setPointerCapture(ev.pointerId);
                    onPress(e.id, true);
                  }}
                  onPointerUp={() => onPress(e.id, false)}
                  onPointerCancel={() => onPress(e.id, false)}
                >
                  {t("controls.hold")}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      {meters.length > 0 && (
        <div className="flex flex-wrap gap-2" role="group" aria-label={t("controls.meters")}>
          {meters.map((e) => {
            const r = live.frame?.results[e.id];
            const reading = e.kind === "voltmeter" ? r?.U : r?.I;
            return (
              <div key={e.id} className={cn(card, "min-w-36 max-w-52")}>
                {head(e)}
                <span className="font-mono text-[20px] tabular-nums text-fg">{reading ?? "—"}</span>
              </div>
            );
          })}
        </div>
      )}
      {!inputs.length && !meters.length && <p className="m-0 text-[13px] text-faint">{t("controls.nothing")}</p>}
    </div>
  );
}
