// "+ Kod  + Tekst  + Schemat", as in Colab: pills on the edge between cells. The row is a thin
// strip along the whole edge; the pills show only while the pointer (or the focus) is in it.
import { useTranslation } from "react-i18next";
import type { CellType } from "@/shared/model/types";
import { Plus } from "@/shared/ui/icons";
import { cn } from "@/shared/lib/cn";

export function AddRow({ onAdd, edge, shown }: {
  onAdd: (type: CellType) => void;
  edge?: boolean; // on a cell's bottom edge: from its padding, over the gap, to the next one's
  shown?: boolean; // always shown (an empty notebook)
}) {
  const { t } = useTranslation("notebook");
  const pill = "inline-flex items-center gap-1 py-1 pr-3.5 pl-2.5 rounded-full border border-faint bg-bg text-[15px] font-medium text-fg " +
    "hover:bg-hover hover:border-muted transition-opacity duration-120 " +
    (shown ? "" : "invisible opacity-0 group-hover/add:visible group-hover/add:opacity-100 group-focus-within/add:visible group-focus-within/add:opacity-100");
  return (
    <div role="group" aria-label={t("add.label")}
         className={cn("group/add flex h-7 items-center justify-center gap-2", edge && "absolute inset-x-0 -bottom-5 z-4")}>
      <button className={pill} onClick={() => onAdd("code")} title={t("add.codeTitle")}><Plus /> {t("add.code")}</button>
      <button className={pill} onClick={() => onAdd("markdown")} title={t("add.markdownTitle")}><Plus /> {t("add.markdown")}</button>
      <button className={pill} onClick={() => onAdd("schematic")} title={t("add.schematicTitle")}><Plus /> {t("add.schematic")}</button>
    </div>
  );
}
