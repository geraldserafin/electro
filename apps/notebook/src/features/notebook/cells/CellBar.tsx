// Every cell is a block, like a small editor: one thin bar on top — its tabs on the left, on the
// right what it does (run) — and what it holds under it. The bar is there all the time (nothing
// moves), but until the cell is worked on only its run button shows; focused, the bar and its
// tabs come in around that button. The cell's own tools (drag it elsewhere, remove it) are in the
// margin beside the block (the frame's).
import { createContext, type ReactNode, useContext } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { Play } from "@/shared/ui/icons";

/** The block around a cell: its frame, lit while the cell is worked on. */
export const block =
  "flex flex-col overflow-hidden rounded-xl border border-line bg-code-bg transition-shadow duration-150 " +
  "group-data-focused/cell:shadow-raised";

/** A tab in a bar: chosen (the accent on top, the block's colour) or not. */
export const tabLook = (on: boolean) =>
  cn(
    "inline-flex items-center gap-1.5 px-3 border-r border-line text-[13px] whitespace-nowrap",
    on ? "bg-code-bg text-fg shadow-[inset_0_2px_0_var(--accent)]" : "text-muted hover:text-fg",
  );

/** A small square button in a bar (run, tools, compile, close). */
export const barButton =
  "inline-flex flex-none items-center justify-center size-7 rounded-md text-muted hover:bg-selected hover:text-fg disabled:opacity-40";

/** Whether the cell is the one worked on (the frame's; outside a cell: always, e.g. a pane full screen). */
export const CellFocusContext = createContext<boolean | null>(null);
export const useCellFocused = () => useContext(CellFocusContext) ?? true;

/** The bar: tabs; what is given for the end (with the tabs, while worked on); run, always, in the corner. */
export function CellBar({
  tabs,
  end,
  run,
  label,
  always,
}: {
  tabs: ReactNode;
  end?: ReactNode;
  run?: ReactNode;
  label: string;
  always?: boolean; // shown whether the cell is worked on or not (a pane full screen)
}) {
  const on = useCellFocused() || always;
  return (
    <div
      className={cn(
        "flex items-center gap-0.5 h-9 flex-none border-b pr-1 transition-colors duration-200",
        on ? "border-line bg-board" : "border-transparent bg-transparent",
      )}
    >
      <div
        role="tablist"
        aria-label={label}
        aria-hidden={!on || undefined}
        className={cn(
          "flex self-stretch min-w-0 overflow-x-auto [scrollbar-width:none] transition-[opacity,translate] duration-200 ease-out",
          on ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-1 pointer-events-none",
        )}
      >
        {tabs}
      </div>
      <span className="flex-1" />
      <span
        className={cn(
          "flex items-center gap-0.5 transition-opacity duration-200",
          !on && "opacity-0 pointer-events-none",
        )}
        aria-hidden={!on || undefined}
      >
        {end}
      </span>
      {run}
    </div>
  );
}

/**
 * Run, in a bar: lit (the app's yellow) while there is something to run; resting when nothing
 * changed since the last run; blinking while it runs. [n]: how many runs of the note ago it ran.
 */
export function RunButton({
  run,
  running,
  label,
  execution,
  done,
  eager,
  icon = <Play />,
  quiet,
}: {
  run: () => void;
  running: boolean;
  label: string;
  execution?: number;
  done?: boolean; // nothing changed since the last run: nothing to run, it rests
  eager?: boolean; // lit whenever there is something to run (a schematic), not only on the cell
  icon?: ReactNode;
  quiet?: boolean; // one of a few on the bar: never lit, plain like its other buttons
}) {
  const { t } = useTranslation("notebook");
  return (
    <span className="flex items-center gap-1">
      {execution !== undefined && !running && <span className="font-mono text-[12px] text-faint">[{execution}]</span>}
      <button
        onClick={run}
        disabled={running || done}
        title={done ? t("schematic.upToDate") : label}
        aria-label={label}
        className={cn(
          "inline-flex flex-none items-center justify-center size-7 rounded-md [&_svg]:size-4",
          done
            ? "text-faint opacity-60"
            : quiet
              ? "text-fg hover:bg-selected"
              : eager && !running
                ? "bg-primary text-on-primary hover:bg-primary-hover"
                : "text-muted hover:bg-primary hover:text-on-primary group-data-focused/cell:bg-primary group-data-focused/cell:text-on-primary",
          running && "animate-blink",
        )}
      >
        {icon}
      </button>
    </span>
  );
}
