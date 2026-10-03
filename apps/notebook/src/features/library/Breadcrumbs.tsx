// The way up to where the user is: the home screen, the folders above (not this one: its name is the
// title under them). Something being dragged may be dropped onto a folder above (to move it up there).
import type { Crumb, ItemCard } from "@electro/notes-api";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { folderUrl } from "@/features/notes";
import { cn } from "@/shared/lib/cn";
import { dragging } from "./drag";

export function Breadcrumbs({
  path,
  onDrop,
}: {
  path: readonly Crumb[]; // from the top down (the home screen is always first)
  onDrop?: (card: ItemCard, into: string | null) => void;
}) {
  const { t } = useTranslation("library");
  const [over, setOver] = useState<string | null | undefined>(undefined);
  const crumbs: { id: string | null; name: string; to: string }[] = [
    { id: null, name: t("home"), to: "/" },
    ...path.map((c) => ({ id: c.id, name: c.name || t("untitled"), to: folderUrl(c.id, c.name) })),
  ];
  return (
    <nav aria-label={t("folder.path")} className="flex flex-wrap items-center gap-1 mb-1 text-[14px] text-muted">
      {crumbs.map((c, i) => (
        <span key={c.id ?? "home"} className="flex items-center gap-1">
          <Link
            to={c.to}
            className={cn(
              "px-1.5 py-0.5 rounded-md no-underline text-muted hover:bg-hover hover:text-fg",
              over === c.id && "bg-accent-soft text-fg",
            )}
            onDragOver={(e) => {
              const card = dragging.get();
              if (!onDrop || !card || (c.id === null && card.owner !== null)) return;
              e.preventDefault();
              setOver(c.id);
            }}
            onDragLeave={() => setOver(undefined)}
            onDrop={(e) => {
              e.preventDefault();
              setOver(undefined);
              const card = dragging.get();
              if (card && onDrop) onDrop(card, c.id);
            }}
          >
            {c.name}
          </Link>
          {i < crumbs.length - 1 && <span aria-hidden>›</span>}
        </span>
      ))}
    </nav>
  );
}
