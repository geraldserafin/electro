// The tools, top centre: select, hand, wire — and the element library's switch.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { Grid, Hand, Pointer, WireIcon } from "@/shared/ui/icons";
import { BoardButton, BoardIsland, Separator } from "./Board";

export type Tool = { type: "select" } | { type: "hand" } | { type: "wire" } | { type: "place"; kind: string };

const tool = (on: boolean) => cn("relative flex-none w-10 h-9 p-0 justify-center text-fg", on && "bg-selected");
const Key = ({ children }: { children: ReactNode }) => <span className="absolute right-0.75 bottom-px text-[9px] text-faint">{children}</span>;

export function Toolbar({ current, onTool, libraryOpen, onLibrary }: {
  current: Tool; onTool: (tool: Tool) => void; libraryOpen: boolean; onLibrary: () => void;
}) {
  const { t } = useTranslation("schematic");
  const tools: { tool: Tool; label: string; key: string; icon: ReactNode }[] = [
    { tool: { type: "select" }, label: t("tools.select"), key: "V", icon: <Pointer /> },
    { tool: { type: "hand" }, label: t("tools.hand"), key: "H", icon: <Hand /> },
    { tool: { type: "wire" }, label: t("tools.wire"), key: "W", icon: <WireIcon /> },
  ];
  return (
    <BoardIsland role="toolbar" aria-label={t("tools.label")}
                 className="top-3 left-1/2 -translate-x-1/2 max-w-[calc(100%-24px)] overflow-x-auto [scrollbar-width:none]">
      {tools.map(({ tool: it, label, key, icon }) => (
        <BoardButton key={it.type} className={tool(it.type === current.type)} title={`${label} (${key})`} aria-label={label}
                     onClick={() => onTool(it)}>
          {icon}
          <Key>{key}</Key>
        </BoardButton>
      ))}
      <Separator />
      <BoardButton className={cn(tool(libraryOpen), "w-auto pl-2.5 pr-3 gap-1.5")} title={t("tools.libraryTitle")}
                   aria-label={t("tools.library")} onClick={onLibrary}>
        <Grid /> <span>{t("tools.library")}</span>
        <Key>K</Key>
      </BoardButton>
    </BoardIsland>
  );
}
