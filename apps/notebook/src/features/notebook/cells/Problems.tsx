// A warning / error sign on the board; a click unfolds what is wrong (with the names in LaTeX).
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Problem } from "@/shared/model/types";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { Close, WarningIcon } from "@/shared/ui/icons";
import { Markdown } from "@/shared/ui/Markdown";
import { useSay } from "@/features/solution";
import { cn } from "@/shared/lib/cn";

export function Problems({ problems, below, onDismiss, compact }: {
  problems: Problem[];
  below?: boolean; // unfolds downwards (at the top of the code view), not upwards
  onDismiss: () => void; // away until the next run finds something
  compact?: boolean; // in the code editor's thin bar
}) {
  const { t } = useTranslation("notebook");
  const say = useSay();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useClickOutside(ref, open, useCallback(() => setOpen(false), []));
  const error = problems.some((p) => p.kind === "error");
  const title = error ? t("problems.error") : t("problems.warning");
  const color = error ? "text-danger" : "text-warn";
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} title={title} aria-label={title} aria-expanded={open}
              className={cn("grid place-items-center", compact ? "size-7 rounded-md [&_svg]:size-4" : "size-11 rounded-[10px] shadow-island", color, error ? "bg-err-bg" : "bg-warn-bg")}>
        <WarningIcon />
      </button>
      {open && (
        <div role="dialog" aria-label={title}
             className={cn("absolute -right-1 z-8 w-[min(420px,80vw)] max-h-80 overflow-y-auto px-3.5 py-3 rounded-[10px]",
                           "bg-island shadow-island text-[15px] whitespace-normal [&_.markdown_p]:my-1 [&_.katex]:whitespace-nowrap",
                           below ? "top-[calc(100%+12px)]" : "bottom-[calc(100%+12px)]")}>
          <div className="flex items-start gap-2">
            <h4 className={cn("flex-1 mt-0 mb-1.5 text-[12px] font-semibold uppercase tracking-[0.05em]", color)}>{title}</h4>
            <button className="-mt-1 -mr-1.5 inline-flex items-center justify-center size-7 rounded-md text-muted hover:bg-selected hover:text-fg [&_svg]:size-4"
                    onClick={onDismiss} title={t("problems.dismiss")} aria-label={t("problems.dismiss")}><Close /></button>
          </div>
          {problems.map((p, i) => <Markdown key={i} source={p.issue ? say.issue(p.issue) : p.text ?? ""} />)}
        </div>
      )}
    </div>
  );
}
