// The element library, open while "Elementy" is on: a panel floating over the left of the board,
// like Excalidraw's (nothing moves to make room). A search, then a section per group — its label and
// a grid of tiles, three in a row, one per element: its symbol whole (as big as the tile lets it), its
// name under it, its key in the corner (as on the toolbar). Search by name, other names or group; Enter places the first one found.
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { PartDef, SymbolLibrary } from "@/shared/model/types";
import { Search, Trash } from "@/shared/ui/icons";
import { plain, useKinds } from "./kinds";
import { KINDS } from "./model";
import { Panel, PanelHead, Section, Tile } from "./Panel";
import { partBox, partKind, withParts } from "./parts";
import { SymbolIcon } from "./SymbolIcon";

/** 1–9, 0: the first ten kinds, in the library's order. */
export const shortcut = (kind: string) => {
  const i = KINDS.findIndex((k) => k.kind === kind);
  return i >= 0 && i < 10 ? String((i + 1) % 10) : "";
};

// a tile: the symbol filling its top, the name under it (two lines at most)
const tile = "w-full h-auto grid-rows-[44px_auto] content-start gap-1 px-1 pt-1.5 pb-1.5 [&_svg]:w-full [&_svg]:h-11";
const name = "w-full text-[11px] leading-tight text-center text-muted line-clamp-2 break-words hyphens-auto";

/** One of the user's own components, as the library offers it. */
export interface MyPart {
  id: string;
  def: PartDef;
}

export function LibraryPanel({
  library,
  chosen,
  onChoose,
  onClose,
  parts = [],
  partsLabel,
  removeLabel,
  onChoosePart,
  onRemovePart,
}: {
  library: SymbolLibrary;
  chosen?: string; // the kind being placed
  onChoose: (kind: string) => void;
  onClose: (backToBoard?: boolean) => void;
  parts?: MyPart[]; // the user's own components, first
  partsLabel?: string;
  removeLabel?: string;
  onChoosePart?: (part: MyPart) => void;
  onRemovePart?: (part: MyPart) => void;
}) {
  const { t } = useTranslation("schematic");
  const { search } = useKinds();
  const [query, setQuery] = useState("");
  const field = useRef<HTMLInputElement>(null);
  // the search takes the keyboard when the panel opens — without scrolling the page to it (not on a touch
  // screen: its keyboard would come up over the board)
  useEffect(() => {
    if (!matchMedia("(pointer: coarse)").matches) field.current?.focus({ preventScroll: true });
  }, []);
  const found = search(query);
  const groups = [...new Set(found.map((k) => k.groupName))];
  const mine = parts.filter((p) => plain(p.def.name).includes(plain(query.trim())));
  const partsLibrary = useMemo(
    () => withParts(library, Object.fromEntries(parts.map((p) => [p.id, p.def]))),
    [library, parts],
  );

  return (
    <Panel
      role="complementary"
      aria-label={t("library.label")}
      // (a phone: a sheet from the bottom, as an element's panel)
      className="top-15 left-3 bottom-16 z-6 w-80 max-w-[calc(100%-24px)] gap-3 animate-panel-in motion-reduce:animate-none
                 max-sm:top-auto max-sm:inset-x-0 max-sm:bottom-0 max-sm:w-auto max-sm:max-w-none max-sm:h-[75%] max-sm:pt-2
                 max-sm:rounded-b-none max-sm:shadow-[0_-4px_16px_rgb(0_0_0/0.12)] max-sm:animate-sheet-in"
    >
      <span aria-hidden className="hidden max-sm:block flex-none self-center w-9 h-1 rounded-full bg-line" />
      <PanelHead caption={t("library.title")} onClose={() => onClose()} closeLabel={t("library.closeTitle")} />
      <label
        className="flex flex-none items-center gap-2 px-2.5 h-9 rounded-lg bg-hover text-faint
                        focus-within:bg-paper focus-within:outline-2 focus-within:outline-accent-soft [&_svg]:size-4"
      >
        <Search />
        <input
          ref={field}
          value={query}
          placeholder={t("library.search")}
          className="flex-1 min-w-0 bg-transparent text-[14px] text-fg outline-none"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && mine[0] && onChoosePart) onChoosePart(mine[0]);
            else if (e.key === "Enter" && found[0]) onChoose(found[0].kind);
            if (e.key === "Escape") onClose(true);
          }}
        />
      </label>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden -mx-1 px-1 pb-1 grid content-start gap-4">
        {mine.length > 0 && onChoosePart && (
          <Section label={partsLabel}>
            <div className="grid grid-cols-4 gap-1">
              {mine.map((p) => {
                const G = library.grid;
                return (
                  <span key={p.id} className="relative group/part">
                    <Tile
                      on={chosen === partKind(p.id)}
                      title={p.def.name}
                      aria-label={p.def.name}
                      className={tile}
                      onClick={() => onChoosePart(p)}
                    >
                      <SymbolIcon kind={partKind(p.id)} library={partsLibrary} box={partBox(p.def, G)} />
                      <span className={name}>{p.def.name}</span>
                    </Tile>
                    {onRemovePart && (
                      <button
                        className="absolute -top-1 -right-1 hidden group-hover/part:grid place-items-center size-4.5 rounded-full bg-paper border border-line text-muted hover:text-danger [&_svg]:size-3"
                        title={`${removeLabel ?? ""}: ${p.def.name}`}
                        aria-label={p.def.name}
                        onClick={() => onRemovePart(p)}
                      >
                        <Trash />
                      </button>
                    )}
                  </span>
                );
              })}
            </div>
          </Section>
        )}
        {groups.map((group) => (
          <Section key={group} label={group}>
            <div className="grid grid-cols-4 gap-1">
              {found
                .filter((k) => k.groupName === group)
                .map((k) => (
                  <Tile
                    key={k.kind}
                    on={chosen === k.kind}
                    title={k.name}
                    aria-label={k.name}
                    className={tile}
                    onClick={() => onChoose(k.kind)}
                  >
                    <SymbolIcon kind={k.kind} library={library} />
                    <span className={name}>{k.name}</span>
                    {shortcut(k.kind) && (
                      <span className="absolute right-1.5 top-1 text-[10px] text-faint">{shortcut(k.kind)}</span>
                    )}
                  </Tile>
                ))}
            </div>
          </Section>
        ))}
        {!found.length && !mine.length && (
          <p className="m-0 text-[14px] text-muted">{t("library.nothing", { query })}</p>
        )}
      </div>
    </Panel>
  );
}
