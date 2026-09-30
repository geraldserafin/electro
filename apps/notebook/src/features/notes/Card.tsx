// Notes as cards (like Figma's files): a thumbnail of the first page, as the PDF would show it,
// and the title under it. A folder's card shows its own picture (``thumb``) instead.
import type { NotePreview } from "@electro/notes-api";
import {
  type CSSProperties,
  type HTMLAttributes,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { useClickOutside } from "@/shared/hooks/useClickOutside";
import { cn } from "@/shared/lib/cn";
import type { SymbolLibrary } from "@/shared/model/types";
import { More, Plus } from "@/shared/ui/icons";
import { PagePreview } from "./PagePreview";

// the card: a link (a note) or a button (an example), alike
const open = "group/open grid content-start gap-0.5 text-left";
// the page: A4's proportions, 212px wide
const thumb =
  "grid place-items-center w-53 aspect-[794/1123] overflow-hidden rounded-md mb-2 transition-[box-shadow,transform] duration-120 group-focus-visible/open:outline-2 group-focus-visible/open:outline-offset-2 group-focus-visible/open:outline-accent";
const title = "text-[15px] font-medium truncate max-w-53";

/** A card: a link to the note (or a button, for an example), with actions under "⋯". */
export function Card({
  to,
  onClick,
  id,
  title: name,
  meta,
  preview,
  thumb: picture,
  library,
  actions,
  index = 0,
  drag,
  target = false,
}: {
  index?: number; // its place in the list: the cards come in one after another
  to?: string;
  onClick?: () => void;
  id?: string;
  title: string;
  meta?: string;
  preview?: NotePreview;
  thumb?: ReactNode; // instead of a page: a folder's picture
  library: SymbolLibrary;
  actions?: { label: string; danger?: boolean; run: () => void }[];
  drag?: HTMLAttributes<HTMLLIElement> & { draggable?: boolean }; // picked up, dropped onto (a folder)
  target?: boolean; // something is being dragged over it, and may go in
}) {
  const { t } = useTranslation("notes");
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLLIElement>(null);
  useClickOutside(
    ref,
    menu,
    useCallback(() => setMenu(false), []),
  );
  const body: ReactNode = (
    <>
      {picture ?? (
        <span className={cn(thumb, "bg-white shadow-island group-hover:shadow-lift")}>
          {preview && <PagePreview preview={preview} library={library} />}
        </span>
      )}
      <span className={title}>{name}</span>
      {meta && <span className="text-[13px] text-muted">{meta}</span>}
    </>
  );
  return (
    <li
      className={cn("appear group relative grid rounded-lg", target && "outline-2 outline-offset-4 outline-accent")}
      data-id={id}
      ref={ref}
      style={{ "--i": Math.min(index, 12) } as CSSProperties}
      {...drag}
    >
      {to ? (
        <Link className={open} to={to}>
          {body}
        </Link>
      ) : (
        <button className={open} onClick={onClick}>
          {body}
        </button>
      )}
      {actions && actions.length > 0 && (
        <>
          <button
            onClick={() => setMenu(!menu)}
            title={t("more")}
            aria-label={t("more")}
            aria-expanded={menu}
            className="absolute top-2 right-2 inline-flex size-7.5 items-center justify-center rounded-lg bg-island hover:bg-hover shadow-island text-fg
                             opacity-0 transition-opacity duration-120 group-hover:opacity-100 aria-expanded:opacity-100"
          >
            <More />
          </button>
          {menu && (
            <div
              role="menu"
              className="absolute z-30 top-10.5 right-2 grid min-w-45 py-1.5 rounded-lg bg-paper shadow-menu"
            >
              {actions.map((a) => (
                <button
                  key={a.label}
                  role="menuitem"
                  onClick={() => {
                    setMenu(false);
                    a.run();
                  }}
                  className={cn(
                    "px-4 py-1.75 border border-transparent text-[15px] text-left whitespace-nowrap hover:bg-hover",
                    a.danger && "text-danger",
                  )}
                >
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

/** The first card: something new — a new, empty note; or, with ``choices``, one of them, from a
 *  menu it opens (a note, a folder). */
export function NewCard({
  onClick,
  label,
  choices,
}: {
  onClick?: () => void;
  label?: string;
  choices?: { label: string; icon: ReactNode; run: () => void }[];
}) {
  const { t } = useTranslation("notes");
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLLIElement>(null);
  const close = useCallback(() => setMenu(false), []);
  useClickOutside(ref, menu, close);
  useEffect(() => {
    if (!menu) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [menu, close]);
  return (
    <li className="relative grid" ref={ref}>
      <button
        className={cn("group", open)}
        onClick={choices ? () => setMenu(!menu) : onClick}
        aria-haspopup={choices ? "menu" : undefined}
        aria-expanded={choices ? menu : undefined}
      >
        <span
          className={cn(
            thumb,
            "border-[1.5px] border-dashed border-faint text-muted group-hover:border-fg group-hover:text-fg",
            "group-aria-expanded:border-fg group-aria-expanded:text-fg [&_svg]:size-7",
          )}
        >
          <Plus />
        </span>
        <span className={title}>{label ?? t("newNote")}</span>
      </button>
      {menu && choices && (
        <div
          role="menu"
          aria-label={label}
          className="absolute z-30 top-[calc(50%-2.5rem)] left-1/2 -translate-x-1/2 grid min-w-45 py-1.5 rounded-xl border border-line bg-paper shadow-menu"
        >
          {choices.map((c) => (
            <button
              key={c.label}
              role="menuitem"
              onClick={() => {
                setMenu(false);
                c.run();
              }}
              className="flex items-center gap-2.5 px-4 py-1.75 text-[15px] text-left text-fg hover:bg-hover [&>svg]:flex-none [&>svg]:text-muted"
            >
              {c.icon}
              <span className="flex-1">{c.label}</span>
            </button>
          ))}
        </div>
      )}
    </li>
  );
}
