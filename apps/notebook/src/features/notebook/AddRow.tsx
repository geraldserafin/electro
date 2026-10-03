// "+ Nowy blok" on the edge between cells (the pill shows while the pointer, or the focus, is on that
// edge; always in an empty note): a menu of what may come there — text, code, a drawing. Chapters are
// added in the outline (Parts: AddPart).
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { cn } from "@/shared/lib/cn";
import type { CellType } from "@/shared/model/types";
import { CodeIcon, PageIcon, Plus, SchematicIcon } from "@/shared/ui/icons";

/** The choices as a menu (under the pill, or a cell's +). */
export function BlockMenu({ onAdd, className }: { onAdd: (type: CellType) => void; className?: string }) {
  const { t } = useTranslation("notebook", { keyPrefix: "add" });
  const blocks = [
    { type: "markdown", label: t("markdown"), icon: <PageIcon /> },
    { type: "code", label: t("code"), icon: <CodeIcon /> },
    { type: "schematic", label: t("schematic"), icon: <SchematicIcon /> },
  ] as const;
  return (
    <span
      role="menu"
      aria-label={t("label")}
      className={cn("z-30 grid w-56 p-1.5 rounded-xl border border-line bg-paper shadow-menu", className)}
    >
      {blocks.map((b) => (
        <button
          key={b.type}
          role="menuitem"
          className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-[15px] text-fg hover:bg-hover [&_svg]:size-4 [&_svg]:text-muted"
          onClick={() => onAdd(b.type)}
        >
          {b.icon}
          {b.label}
        </button>
      ))}
    </span>
  );
}

export function AddRow({
  onAdd,
  edge,
  shown,
}: {
  onAdd: (type: CellType) => void;
  edge?: boolean; // on a cell's bottom edge: from its padding, over the gap, to the next one's
  shown?: boolean; // always shown (an empty notebook)
}) {
  const { t } = useTranslation("notebook");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, open, close);
  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, close]);
  const pill =
    "inline-flex items-center gap-1 py-1 pr-3.5 pl-2.5 rounded-full border border-faint bg-bg text-[15px] font-medium text-fg " +
    "hover:bg-hover hover:border-muted transition-opacity duration-120 " +
    (shown || open
      ? ""
      : "invisible opacity-0 group-hover/add:visible group-hover/add:opacity-100 group-focus-within/add:visible group-focus-within/add:opacity-100");
  return (
    <div
      ref={ref}
      role="group"
      aria-label={t("add.label")}
      data-add-row
      className={cn(
        "group/add relative flex h-7 items-center justify-center",
        open && "z-30",
        // (a touch screen: none on the edge, the cell's tools add one)
        edge && "absolute inset-x-0 -bottom-5 z-4 pointer-coarse:hidden",
      )}
    >
      <button className={pill} onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}>
        <Plus /> {t("add.block")}
      </button>
      {open && (
        <BlockMenu
          className="absolute top-full left-1/2 -translate-x-1/2 mt-1.5"
          onAdd={(type) => {
            close();
            onAdd(type);
          }}
        />
      )}
    </div>
  );
}
