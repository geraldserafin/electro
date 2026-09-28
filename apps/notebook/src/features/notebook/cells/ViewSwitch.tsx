import { useTranslation } from "react-i18next";
import type { SchematicView } from "@/shared/model/types";
import { CodeIcon, SchematicIcon } from "@/shared/ui/icons";
import { cn } from "@/shared/lib/cn";

/** Schemat | Kod: the two views of a schematic cell. */
export function ViewSwitch({ view, onSwitch, busy }: { view: SchematicView; onSwitch: (v: SchematicView) => void; busy: boolean }) {
  const { t } = useTranslation("notebook");
  const tab = (on: boolean) => cn("inline-flex items-center px-2.5 py-1 rounded-md border border-transparent text-muted disabled:opacity-45", on && "bg-paper text-fg shadow-[0_1px_2px_rgb(0_0_0/0.15)]");
  return (
    <div className="flex gap-0.5 p-0.5 rounded-lg bg-hover" role="tablist" aria-label={t("schematic.view")}>
      <button role="tab" aria-selected={view === "schematic"} className={tab(view === "schematic")}
              disabled={busy} onClick={() => onSwitch("schematic")} title={t("schematic.drawing")} aria-label={t("schematic.drawing")}>
        <SchematicIcon />
      </button>
      <button role="tab" aria-selected={view === "code"} className={tab(view === "code")}
              disabled={busy} onClick={() => onSwitch("code")} title={t("schematic.codeTitle")} aria-label={t("schematic.code")}>
        <CodeIcon />
      </button>
    </div>
  );
}
