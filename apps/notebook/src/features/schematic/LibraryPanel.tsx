// The element library, open while "Elementy" is on: a panel floating over the left of the board,
// like Excalidraw's (nothing moves to make room). A search, then a section per group — its label and
// a grid of tiles, one per element: its symbol, its name on hover, its key in the corner (as on the
// toolbar). Search by name, other names or group; Enter places the first one found.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { SymbolLibrary } from "@/shared/model/types";
import { Search } from "@/shared/ui/icons";
import { useKinds } from "./kinds";
import { KINDS } from "./model";
import { Panel, PanelHead, Section, Tile } from "./Panel";
import { SymbolIcon } from "./SymbolIcon";

/** 1–9, 0: the first ten kinds, in the library's order. */
export const shortcut = (kind: string) => {
  const i = KINDS.findIndex((k) => k.kind === kind);
  return i >= 0 && i < 10 ? String((i + 1) % 10) : "";
};

export function LibraryPanel({ library, chosen, onChoose, onClose }: {
  library: SymbolLibrary;
  chosen?: string; // the kind being placed
  onChoose: (kind: string) => void;
  onClose: (backToBoard?: boolean) => void;
}) {
  const { t } = useTranslation("schematic");
  const { search } = useKinds();
  const [query, setQuery] = useState("");
  const field = useRef<HTMLInputElement>(null);
  // the search takes the keyboard when the panel opens — without scrolling the page to it
  useEffect(() => field.current?.focus({ preventScroll: true }), []);
  const found = search(query);
  const groups = [...new Set(found.map((k) => k.groupName))];

  return (
    <Panel role="complementary" aria-label={t("library.label")} className="top-15 left-3 bottom-16 z-6 w-66 gap-3">
      <PanelHead caption={t("library.title")} onClose={() => onClose()} closeLabel={t("library.closeTitle")} />
      <label className="flex flex-none items-center gap-2 px-2.5 h-9 rounded-lg bg-hover text-faint
                        focus-within:bg-paper focus-within:outline-2 focus-within:outline-accent-soft [&_svg]:size-4">
        <Search />
        <input ref={field} value={query} placeholder={t("library.search")}
               className="flex-1 min-w-0 bg-transparent text-[14px] text-fg outline-none"
               onChange={(e) => setQuery(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter" && found[0]) onChoose(found[0].kind);
                 if (e.key === "Escape") onClose(true);
               }} />
      </label>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden -mx-1 px-1 pb-1 grid content-start gap-4">
        {groups.map((group) => (
          <Section key={group} label={group}>
            <div className="grid grid-cols-5 gap-1.5">
              {found.filter((k) => k.groupName === group).map((k) => (
                <Tile key={k.kind} on={chosen === k.kind} title={k.name} aria-label={k.name}
                      className="w-full h-11 [&_svg]:size-auto" onClick={() => onChoose(k.kind)}>
                  <SymbolIcon kind={k.kind} library={library} />
                  {shortcut(k.kind) && <span className="absolute right-1 bottom-0.5 text-[9px] text-faint">{shortcut(k.kind)}</span>}
                </Tile>
              ))}
            </div>
          </Section>
        ))}
        {!found.length && <p className="m-0 text-[14px] text-muted">{t("library.nothing", { query })}</p>}
      </div>
    </Panel>
  );
}
