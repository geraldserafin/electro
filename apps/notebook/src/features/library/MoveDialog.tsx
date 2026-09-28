// "Move to…": the folders the user may put things into, as a tree; the item's own folder is marked,
// and a folder cannot go into itself or into a folder inside it. The top of the home screen is a
// place too, for what is the user's own.
import { Result, useAtomValue } from "@effect-atom/atom-react";
import type { Destination, ItemCard } from "@electro/notes-api";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { destinationsAtom } from "@/features/notes";
import { FolderIcon } from "@/shared/ui/icons";
import { cn } from "@/shared/lib/cn";

export function MoveDialog({ card, onChoose, onClose }: {
  card: ItemCard;
  onChoose: (parentId: string | null) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation("library");
  const destinations = useAtomValue(destinationsAtom);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onClose]);

  const rows = (all: readonly Destination[]) => {
    const out: { d: Destination; depth: number; off: boolean }[] = [];
    const walk = (parent: string | null, depth: number, off: boolean) => {
      for (const d of all.filter((x) => x.parentId === parent)) {
        const inside = off || d.id === card.id; // the folder itself and all in it: not a place for it
        out.push({ d, depth, off: inside });
        walk(d.id, depth + 1, inside);
      }
    };
    walk(null, 0, false);
    return out;
  };
  const place = "flex items-center gap-2 w-full px-3 py-2 rounded-lg text-left text-[15px] hover:bg-hover disabled:opacity-45 disabled:hover:bg-transparent";

  return (
    <div className="fixed inset-0 z-100 grid place-items-center bg-black/25 p-4" onClick={onClose}>
      <div role="dialog" aria-modal aria-label={t("moveDialog.title", { name: card.name || t("untitled") })}
           className="grid gap-2 w-full max-w-110 max-h-[80vh] p-4 rounded-xl border border-line bg-paper shadow-menu"
           onClick={(e) => e.stopPropagation()}>
        <h2 className="m-0 mb-1 text-[17px] font-medium">{t("moveDialog.title", { name: card.name || t("untitled") })}</h2>
        <div className="overflow-y-auto min-h-0">
          {card.owner === null && (
            <button className={place} disabled={card.parentId === null} onClick={() => onChoose(null)}>
              <FolderIcon /> <span className="flex-1">{t("moveDialog.top")}</span>
              {card.parentId === null && <span className="text-[13px] text-muted">{t("moveDialog.here")}</span>}
            </button>
          )}
          {Result.isSuccess(destinations) ? rows(destinations.value).map(({ d, depth, off }) => (
            <button key={d.id} className={place} style={{ paddingLeft: 12 + depth * 20 }}
                    disabled={off || d.id === card.parentId} onClick={() => onChoose(d.id)}>
              <FolderIcon /> <span className={cn("flex-1 truncate", !d.name && "text-muted")}>{d.name || t("untitled")}</span>
              {d.id === card.parentId && <span className="text-[13px] text-muted">{t("moveDialog.here")}</span>}
            </button>
          )) : <p className="m-3 text-muted">{t("moveDialog.loading")}</p>}
        </div>
        <div className="flex justify-end">
          <button className="px-3 py-1.5 rounded-lg hover:bg-hover" onClick={onClose}>{t("moveDialog.cancel")}</button>
        </div>
      </div>
    </div>
  );
}
