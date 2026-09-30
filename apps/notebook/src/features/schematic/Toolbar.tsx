// The tools, top centre: select, hand; the wire and the elements drawn most (a resistor, a voltage
// source, ground), each a key away; the element library for the rest.
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { SymbolLibrary } from "@/shared/model/types";
import { Hand, Pointer, WireIcon } from "@/shared/ui/icons";
import { BoardButton, BoardIsland, islandButton, Separator } from "./Board";
import { useKinds } from "./kinds";
import { shortcut } from "./LibraryPanel";
import { SymbolIcon } from "./SymbolIcon";

/** On the toolbar itself, beside the wire (the rest is in the library). */
const QUICK = ["resistor", "voltage_source", "ground"];

/** The library: a grid of shapes, one of them a plus — more elements. */
const Library = () => (
  <svg
    viewBox="0 0 24 24"
    width={18}
    height={18}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="4" y="4" width="6.5" height="6.5" rx="1.5" />
    <circle cx="17.25" cy="7.25" r="3.25" />
    <path d="M7.25 13.5l3.25 5.5H4z" />
    <path d="M17.25 14v6.5M14 17.25h6.5" />
  </svg>
);

export type Tool = { type: "select" } | { type: "hand" } | { type: "wire" } | { type: "place"; kind: string };

const tool = (on: boolean) => cn(islandButton(on), "w-10");
const Key = ({ children }: { children: ReactNode }) => (
  <span className="absolute right-0.75 bottom-px text-[9px] text-faint">{children}</span>
);

export function Toolbar({
  current,
  onTool,
  libraryOpen,
  onLibrary,
  library,
  className,
}: {
  current: Tool;
  onTool: (tool: Tool) => void;
  libraryOpen: boolean;
  onLibrary: () => void;
  library: SymbolLibrary;
  className?: string;
}) {
  const { t } = useTranslation("schematic");
  const { kinds } = useKinds();
  const tools: { tool: Tool; label: string; key: string; icon: ReactNode }[] = [
    { tool: { type: "select" }, label: t("tools.select"), key: "V", icon: <Pointer /> },
    { tool: { type: "hand" }, label: t("tools.hand"), key: "H", icon: <Hand /> },
  ];
  const drawing: { tool: Tool; label: string; key: string; icon: ReactNode; on: boolean }[] = [
    { tool: { type: "wire" }, label: t("tools.wire"), key: "W", icon: <WireIcon />, on: current.type === "wire" },
    ...QUICK.map((kind) => ({
      tool: { type: "place", kind } as Tool,
      label: kinds.find((k) => k.kind === kind)?.name ?? kind,
      key: shortcut(kind),
      icon: (
        <span className="inline-flex [&_svg]:w-7 [&_svg]:h-5">
          <SymbolIcon kind={kind} library={library} />
        </span>
      ),
      on: current.type === "place" && current.kind === kind,
    })),
  ];
  return (
    <BoardIsland
      role="toolbar"
      aria-label={t("tools.label")}
      className={cn(
        "top-[calc(var(--board-top,0px)+0.75rem)] left-1/2 -translate-x-1/2 max-w-[calc(100%-24px)] overflow-x-auto [scrollbar-width:none]",
        className,
      )}
    >
      {tools.map(({ tool: it, label, key, icon }) => (
        <BoardButton
          key={it.type}
          className={tool(it.type === current.type)}
          title={`${label} (${key})`}
          aria-label={label}
          onClick={() => onTool(it)}
        >
          {icon}
          <Key>{key}</Key>
        </BoardButton>
      ))}
      <Separator />
      {drawing.map(({ tool: it, label, key, icon, on }) => (
        <BoardButton
          key={it.type === "place" ? it.kind : it.type}
          className={tool(on)}
          title={`${label} (${key})`}
          aria-label={label}
          aria-pressed={on}
          onClick={() => onTool(it)}
        >
          {icon}
          <Key>{key}</Key>
        </BoardButton>
      ))}
      <Separator />
      <BoardButton
        className={tool(libraryOpen)}
        title={t("tools.libraryTitle")}
        aria-label={t("tools.library")}
        aria-pressed={libraryOpen}
        onClick={onLibrary}
      >
        <Library />
        <Key>K</Key>
      </BoardButton>
    </BoardIsland>
  );
}

export type LiveTool = "interact" | "probe" | "hand";

const Tap = () => (
  <svg
    viewBox="0 0 24 24"
    width={18}
    height={18}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M9 11V5.5a1.5 1.5 0 013 0V11m0-1.5a1.5 1.5 0 013 0V11m0-.5a1.5 1.5 0 013 0V15c0 3.5-2.5 6-6 6-2.6 0-4-1.3-5.3-3.5L5 14.6a1.5 1.5 0 012.5-1.6L9 15" />
    <path d="M6 5.5a4.5 4.5 0 016-4" />
  </svg>
);
const Meter = () => (
  <svg
    viewBox="0 0 24 24"
    width={18}
    height={18}
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <rect x="5" y="2.5" width="14" height="19" rx="2.5" />
    <path d="M8 6h8v5H8z" />
    <circle cx="12" cy="16" r="2.2" />
    <path d="M12 16l1.4-1.4" />
  </svg>
);

/** While the circuit runs: its own tools, in the same place — interact, the meter, the hand. */
export function LiveToolbar({ current, onTool }: { current: LiveTool; onTool: (tool: LiveTool) => void }) {
  const { t } = useTranslation("schematic");
  const tools: { tool: LiveTool; label: string; key: string; icon: ReactNode }[] = [
    { tool: "interact", label: t("tools.interact"), key: "V", icon: <Tap /> },
    { tool: "probe", label: t("tools.probe"), key: "M", icon: <Meter /> },
    { tool: "hand", label: t("tools.hand"), key: "H", icon: <Hand /> },
  ];
  return (
    <BoardIsland role="toolbar" aria-label={t("tools.liveLabel")} className="top-3 left-1/2 -translate-x-1/2">
      {tools.map(({ tool: it, label, key, icon }) => (
        <BoardButton
          key={it}
          className={tool(it === current)}
          title={`${label} (${key})`}
          aria-label={label}
          aria-pressed={it === current}
          onClick={() => onTool(it)}
        >
          {icon}
          <Key>{key}</Key>
        </BoardButton>
      ))}
    </BoardIsland>
  );
}
