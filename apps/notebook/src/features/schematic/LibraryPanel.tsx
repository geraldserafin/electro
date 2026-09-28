// The element library: a side panel on the left (like Excalidraw's), open while "Elementy" is on.
// Search by name, other names or group; Enter places the first one found.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { SymbolLibrary } from "@/shared/model/types";
import { cn } from "@/shared/lib/cn";
import { Search } from "@/shared/ui/icons";
import { BoardButton, BoardIsland } from "./Board";
import { useKinds } from "./kinds";
import { KINDS } from "./model";
import { SymbolIcon } from "./SymbolIcon";

const caption = "text-[11px] font-semibold uppercase tracking-[0.05em] text-muted";

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
    <BoardIsland role="complementary" aria-label={t("library.label")}
                 className="top-15 left-3 bottom-16 z-6 w-59 flex-col items-stretch gap-2 p-2.5 overflow-hidden">
      <div className="flex items-center justify-between pr-0.5 pb-1 pl-1">
        <h4 className={cn(caption, "m-0 text-[12px]")}>{t("library.title")}</h4>
        <BoardButton icon className="text-[18px] leading-none text-muted" onClick={() => onClose()}
                     title={t("library.closeTitle")} aria-label={t("library.close")}>×</BoardButton>
      </div>
      <label className="flex flex-none items-center gap-1.5 px-2 border border-line rounded-lg text-faint focus-within:border-accent">
        <Search />
        <input ref={field} value={query} placeholder={t("library.search")}
               className="flex-1 min-w-0 py-1.75 outline-none"
               onChange={(e) => setQuery(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter" && found[0]) onChoose(found[0].kind);
                 if (e.key === "Escape") onClose(true);
               }} />
      </label>
      <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden -mx-1.5 px-1.5">
        {groups.map((group) => (
          <section key={group}>
            <h5 className={cn(caption, "mt-2 mx-1 mb-0.5")}>{group}</h5>
            <div className="grid grid-cols-1 gap-px">
              {found.filter((k) => k.groupName === group).map((k) => (
                <BoardButton key={k.kind} title={k.name} onClick={() => onChoose(k.kind)}
                             className={cn("w-full min-w-0 justify-start gap-2.5 text-left", chosen === k.kind && "bg-selected hover:bg-selected text-fg")}>
                  <SymbolIcon kind={k.kind} library={library} />
                  <span className="flex-1 min-w-0 truncate">{k.name}</span>
                  {shortcut(k.kind) && <kbd className="px-1 border border-line rounded font-mono text-[11px] text-faint">{shortcut(k.kind)}</kbd>}
                </BoardButton>
              ))}
            </div>
          </section>
        ))}
        {!found.length && <p className="my-4.5 text-muted">{t("library.nothing", { query })}</p>}
      </div>
    </BoardIsland>
  );
}
