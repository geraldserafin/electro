// Colab-style gutter on a cell's left: a round run button, and [n] once the cell has run.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Play } from "@/shared/ui/icons";
import { cn } from "@/shared/lib/cn";

export const gutter = "w-10 max-[760px]:w-8 flex-none grid justify-items-center gap-0.5 pt-0.5";

const lit = "text-on-primary bg-primary border-primary";
const onCell = "group-hover/cell:text-on-primary group-hover/cell:bg-primary group-hover/cell:border-primary " +
  "group-data-focused/cell:text-on-primary group-data-focused/cell:bg-primary group-data-focused/cell:border-primary";

export function RunButton({ run, running, label, execution, done, eager, icon = <Play /> }: {
  run: () => void; running: boolean; label: string; execution?: number;
  done?: boolean; // nothing changed since the last run: nothing to run, it rests
  eager?: boolean; // lit whenever there is something to run (a schematic), not only on the cell
  icon?: ReactNode;
}) {
  const { t } = useTranslation("notebook");
  const look = done ? "text-faint bg-transparent border-line opacity-60"
    : eager && !running ? lit
    : `text-muted border-line ${onCell}`;
  return (
    <div className={gutter}>
      <button onClick={run} disabled={running || done} title={done ? t("schematic.upToDate") : label} aria-label={label}
              className={cn("inline-flex size-7.5 items-center justify-center rounded-full border hover:enabled:bg-primary-hover hover:enabled:border-primary-hover",
                             look, running && "animate-blink")}>
        {icon}
      </button>
      {execution !== undefined && !running && <span className="font-mono text-[13px] text-faint">[{execution}]</span>}
    </div>
  );
}
