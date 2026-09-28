// Notes as cards (like Figma's files): a thumbnail of the first page, as the PDF would show it,
// and the title under it.
import type { NotePreview } from "@electro/notes-api";
import { useCallback, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import type { SymbolLibrary } from "@/shared/model/types";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { More, Plus } from "@/shared/ui/icons";
import { PagePreview } from "./PagePreview";
import { cn } from "@/shared/lib/cn";

// the card is a link or a button: neither looks like one (legacy.css styles every button)
const open = "group/open grid content-start gap-0.5 p-0 border-0 rounded-none bg-transparent text-inherit text-left cursor-pointer no-underline";
// the page: A4's proportions, 212px wide
const thumb = "grid place-items-center w-53 aspect-[794/1123] overflow-hidden rounded-md mb-2 transition-[box-shadow,transform] duration-120 group-focus-visible/open:outline-2 group-focus-visible/open:outline-offset-2 group-focus-visible/open:outline-accent";
const title = "text-[15px] font-medium truncate max-w-53";

/** A card: a link to the note (or a button, for an example), with actions under "⋯". */
export function Card({ to, onClick, id, title: name, meta, preview, library, actions, index = 0 }: {
  index?: number; // its place in the list: the cards come in one after another
  to?: string;
  onClick?: () => void;
  id?: string;
  title: string;
  meta?: string;
  preview: NotePreview;
  library: SymbolLibrary;
  actions?: { label: string; danger?: boolean; run: () => void }[];
}) {
  const { t } = useTranslation("notes");
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLLIElement>(null);
  useClickOutside(ref, menu, useCallback(() => setMenu(false), []));
  const body: ReactNode = (
    <>
      <span className={cn(thumb, "bg-white shadow-island group-hover:shadow-lift")}>
        <PagePreview preview={preview} library={library} />
      </span>
      <span className={title}>{name}</span>
      {meta && <span className="text-[13px] text-muted">{meta}</span>}
    </>
  );
  return (
    <li className="appear group relative grid" data-id={id} ref={ref} style={{ "--i": Math.min(index, 12) } as CSSProperties}>
      {to ? <Link className={open} to={to}>{body}</Link> : <button className={open} onClick={onClick}>{body}</button>}
      {actions && actions.length > 0 && (
        <>
          <button onClick={() => setMenu(!menu)} title={t("more")} aria-label={t("more")} aria-expanded={menu}
                  className="absolute top-2 right-2 size-7.5 p-0 justify-center rounded-lg bg-island hover:bg-hover shadow-island text-fg
                             opacity-0 transition-opacity duration-120 group-hover:opacity-100 aria-expanded:opacity-100">
            <More />
          </button>
          {menu && (
            <div role="menu" className="absolute z-30 top-10.5 right-2 grid min-w-45 py-1.5 rounded-lg bg-paper shadow-menu">
              {actions.map((a) => (
                <button key={a.label} role="menuitem" onClick={() => { setMenu(false); a.run(); }}
                        className={cn("justify-start px-4 py-1.75 rounded-none text-left whitespace-nowrap", a.danger && "text-danger")}>
                  {a.label}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </li>
  );
}

/** The first card: a new, empty note. */
export function NewCard({ onClick }: { onClick: () => void }) {
  const { t } = useTranslation("notes");
  return (
    <li className="grid">
      <button className={cn("group", open)} onClick={onClick}>
        <span className={cn(thumb, "border-[1.5px] border-dashed border-faint text-muted group-hover:border-fg group-hover:text-fg [&_svg]:size-7")}>
          <Plus />
        </span>
        <span className={title}>{t("newNote")}</span>
      </button>
    </li>
  );
}
