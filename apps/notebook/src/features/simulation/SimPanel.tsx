// One panel under the board, like an IDE's: while the circuit runs, its controls (pause, stop, time,
// speed) and its tabs — the chart (the scope), the controls (what can be turned, flipped or held, and
// what the meters read) and the console (what the Arduinos write to their serial ports, and how their
// sketches compiled); beside them what the cell made of it otherwise (the solver's table, the plots:
// ``more``). Folded to its bar by the chevron, a tab opens it again. Dressed like the board's islands.
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { ElementData } from "@/shared/model/types";
import { Controls, controlled } from "./Controls";
import { si } from "./format";
import { LiveControls } from "./LiveControls";
import { Scope, ScopeChoice } from "./Scope";
import { useSketchNote } from "./SketchEditor";
import type { Live } from "./useLive";

const Icon = ({ d }: { d: string }) => (
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
    <path d={d} />
  </svg>
);
const ChartIcon = () => <Icon d="M4 19h16M4 15l4.5-5 4 3L20 6" />;
const ConsoleIcon = () => <Icon d="M4 5h16v14H4zM7.5 9.5l2.5 2.5-2.5 2.5M12.5 15h4" />;
const SlidersIcon = () => <Icon d="M5 6h9M18 6h1M5 12h3M12 12h7M5 18h11M20 18h-1M16 4v4M10 10v4M18 16v4" />;

type Tab = string; // "chart" | "controls" | "console", or one of ``more``

/** A tab of the cell's own: its name, its icon, what it shows. */
export type PanelTab = { id: string; label: string; icon?: ReactNode; body: ReactNode };

const Fold = ({ open }: { open: boolean }) => <Icon d={open ? "M6 9l6 6 6-6" : "M6 15l6-6 6 6"} />;

export function SimPanel({
  live,
  arduinos,
  elements,
  pressed,
  onElement,
  onPress,
  full,
  height,
  running = true,
  more = [],
  tab: chosen,
  onTab,
  open = true,
  onOpen,
}: {
  live: Live;
  running?: boolean; // the simulation's tabs (else only ``more``)
  more?: PanelTab[];
  tab?: Tab | null; // the tab shown, when the cell picks it (a run: its results)
  onTab?: (tab: Tab) => void;
  open?: boolean; // its body shown (else only its bar)
  onOpen?: (open: boolean) => void;
  arduinos: ElementData[]; // the console is theirs
  elements: ElementData[]; // the board's: the controls tab's
  pressed: string[]; // buttons held down
  onElement: (id: string, patch: Partial<ElementData>) => void; // a control turned: the drawing changes
  onPress: (id: string, down: boolean) => void;
  full?: boolean; // a pane of the cell's editor (under its groups, as tall as dragged), the chart filling it
  height?: number; // that pane's height, px
}) {
  const { t } = useTranslation("simulation");
  const hasControls = elements.some(controlled);
  const [spectral, setSpectral] = useState(false); // the scope by frequency (FFT)
  // on a touch screen (no keys to press): the controls first, where there are buttons or switches to hold
  const [own, setOwn] = useState<Tab>(() =>
    matchMedia("(pointer: coarse)").matches && elements.some((e) => e.kind === "button" || e.kind === "switch")
      ? "controls"
      : "chart",
  );
  const tab = chosen ?? own;
  const setTab = (next: Tab) => {
    setOwn(next);
    onTab?.(next);
    onOpen?.(true);
  };
  const tabs: { id: Tab; label: string; icon?: ReactNode }[] = [
    ...(running
      ? [
          { id: "chart", label: t("panel.chart"), icon: <ChartIcon /> },
          ...(hasControls ? [{ id: "controls", label: t("panel.controls"), icon: <SlidersIcon /> }] : []),
          ...(arduinos.length ? [{ id: "console", label: t("panel.console"), icon: <ConsoleIcon /> }] : []),
        ]
      : []),
    ...more,
  ];
  const shown: Tab = tabs.some((x) => x.id === tab) ? tab : (tabs[0]?.id ?? "chart");
  const extra = more.find((m) => m.id === shown);
  return (
    <section
      aria-label={t("panel.label")}
      style={full && height && open ? { height } : undefined}
      className={cn(
        "flex flex-col bg-code-bg overflow-hidden",
        full ? (open ? "h-[38%] min-h-40 flex-none" : "flex-none") : "rounded-b-xl border border-t-0 border-line",
      )}
    >
      {/* like the code editor's: one thin bar, the tabs on the left, the controls on the right */}
      <header
        // (a phone: off its rounded corners)
        className="flex items-center h-9 flex-none border-b border-line bg-board pr-1 max-sm:px-3"
      >
        <div role="tablist" aria-label={t("panel.label")} className="flex self-stretch">
          {tabs.map(({ id, label, icon }) => (
            <button
              key={id}
              role="tab"
              aria-selected={shown === id}
              onClick={() => setTab(id)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 border-r border-line text-[13px] whitespace-nowrap",
                shown === id ? "bg-code-bg text-fg shadow-[inset_0_2px_0_var(--accent)]" : "text-muted hover:text-fg",
              )}
            >
              {icon} {label}
              {id === "console" && live.serial && shown !== "console" && (
                <span className="size-1.5 rounded-full bg-accent" />
              )}
            </button>
          ))}
        </div>
        <span className="flex-1" />
        {running && <LiveControls live={live} />}
        {onOpen && (
          <button
            className="inline-grid place-items-center size-7 rounded-md text-muted hover:bg-hover hover:text-fg"
            onClick={() => onOpen(!open)}
            aria-expanded={open}
            title={open ? t("panel.fold") : t("panel.unfold")}
            aria-label={open ? t("panel.fold") : t("panel.unfold")}
          >
            <Fold open={open} />
          </button>
        )}
      </header>
      {!open ? null : extra ? (
        <div className={cn("overflow-auto", full && height ? "flex-1 min-h-0" : "max-h-80")}>{extra.body}</div>
      ) : shown === "chart" ? (
        <div className={cn("flex flex-col gap-1 px-2.5 pt-1.5 pb-1", full && "flex-1 min-h-0")}>
          <div className="flex items-center gap-2">
            <ScopeChoice live={live} />
            <span className="flex-1" />
            <button
              className={cn(
                "rounded px-1.5 py-0.5 font-mono text-[11px] hover:bg-hover",
                spectral ? "bg-selected text-fg" : "text-muted",
              )}
              aria-pressed={spectral}
              title={t("scope.spectrumTitle")}
              onClick={() => setSpectral(!spectral)}
            >
              FFT
            </button>
            <span className="font-mono text-[11px] text-faint">
              {t("scope.window", { time: si(Math.max(1e-4, live.speed * 2), "s") })}
            </span>
          </div>
          <div className={cn(full && "flex-1 min-h-0")}>
            <Scope live={live} fill={full} spectral={spectral} />
          </div>
        </div>
      ) : shown === "controls" ? (
        <Controls
          live={live}
          elements={elements}
          pressed={pressed}
          onElement={onElement}
          onPress={onPress}
          full={full}
        />
      ) : (
        <Console live={live} arduinos={arduinos} full={full} />
      )}
    </section>
  );
}

/** A line per sketch (compiled, running, or why not), what the chips wrote, and a line to send them. */
function Console({ live, arduinos, full }: { live: Live; arduinos: ElementData[]; full?: boolean }) {
  const { t } = useTranslation("simulation");
  const [typed, setTyped] = useState("");
  return (
    <div className={cn("flex flex-col gap-1.5 p-2.5", full && "flex-1 min-h-0")}>
      {arduinos.map((e) => (
        <SketchLine key={e.id} element={e} live={live} />
      ))}
      <pre
        className={cn(
          "m-0 overflow-auto rounded-lg border border-line bg-board p-2 font-mono text-[13px] whitespace-pre-wrap",
          full ? "flex-1 min-h-0" : "h-40",
        )}
        ref={(el) => {
          if (el) el.scrollTop = el.scrollHeight;
        }}
        aria-label={t("arduino.serial")}
      >
        {live.serial || <span className="text-faint">{t("arduino.serialEmpty")}</span>}
      </pre>
      <form
        className="flex gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          live.sendSerial(`${typed}\n`);
          setTyped("");
        }}
      >
        <input
          className="flex-1 rounded-lg bg-hover px-2.5 py-1 font-mono text-[13px] focus:bg-paper focus:outline-2 focus:outline-accent-soft"
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder={t("arduino.sendPlaceholder")}
          aria-label={t("arduino.sendPlaceholder")}
          spellCheck={false}
        />
        <button className="rounded-lg bg-hover px-2.5 py-1 text-[13px] hover:bg-selected">{t("arduino.send")}</button>
        <button
          type="button"
          className="rounded-lg px-2.5 py-1 text-[13px] text-muted hover:bg-hover"
          onClick={live.clearSerial}
        >
          {t("arduino.clear")}
        </button>
      </form>
    </div>
  );
}

function SketchLine({ element, live }: { element: ElementData; live: Live }) {
  const state = live.sketches[element.id];
  const changed = state?.kind === "running" && state.sketch !== (element.text ?? "");
  const note = useSketchNote(state, true, changed);
  if (!note) return null;
  const bad = state?.kind === "failed" || state?.kind === "tooBig" || changed;
  return (
    <div className="grid gap-1 text-[13px]">
      <p className={cn("m-0 font-mono", bad ? "text-warn" : "text-muted")}>
        {element.id}: {note}
      </p>
      {state?.kind === "failed" && (
        <pre className="m-0 max-h-32 overflow-auto rounded-lg bg-err-bg p-2 text-danger whitespace-pre-wrap">
          {state.output}
        </pre>
      )}
    </div>
  );
}
