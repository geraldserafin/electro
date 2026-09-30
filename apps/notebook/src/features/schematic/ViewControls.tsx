// The board's corners: zoom and history bottom left; full screen and the shortcuts bottom right.
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { Expand, Help, Minus, Plus, Redo, Shrink, Undo } from "@/shared/ui/icons";
import { BoardButton, BoardIsland, islandButton, Separator } from "./Board";

export function ZoomAndHistory({
  zoom,
  onZoom,
  onFit,
  onUndo,
  onRedo,
  history = true,
}: {
  zoom: number;
  onZoom: (factor: number) => void;
  onFit: () => void;
  onUndo: () => void;
  onRedo: () => void;
  history?: boolean; // undo / redo (not while the circuit runs)
}) {
  const { t } = useTranslation("schematic");
  return (
    <BoardIsland className="bottom-3 left-3">
      <BoardButton
        className={islandButton()}
        title={t("view.zoomOut")}
        aria-label={t("view.zoomOut")}
        onClick={() => onZoom(1 / 1.2)}
      >
        <Minus />
      </BoardButton>
      <BoardButton
        className={cn(islandButton(), "min-w-14 px-1.5 tabular-nums")}
        title={t("view.fitTitle")}
        aria-label={t("view.fit")}
        onClick={onFit}
      >
        {Math.round(zoom * 100)}%
      </BoardButton>
      <BoardButton
        className={islandButton()}
        title={t("view.zoomIn")}
        aria-label={t("view.zoomIn")}
        onClick={() => onZoom(1.2)}
      >
        <Plus />
      </BoardButton>
      {history && (
        <>
          <Separator />
          <BoardButton
            className={islandButton()}
            title={t("view.undoTitle")}
            aria-label={t("view.undo")}
            onClick={onUndo}
          >
            <Undo />
          </BoardButton>
          <BoardButton
            className={islandButton()}
            title={t("view.redoTitle")}
            aria-label={t("view.redo")}
            onClick={onRedo}
          >
            <Redo />
          </BoardButton>
        </>
      )}
    </BoardIsland>
  );
}

export function ScreenAndHelp({
  full,
  onFull,
  onHelp,
  help = true,
  screen = true,
  className,
}: {
  full: boolean;
  onFull: () => void;
  onHelp: () => void;
  help?: boolean; // the shortcuts (not while the circuit runs: nothing to edit)
  screen?: boolean; // the full screen button (not when the cell's bar has it)
  className?: string; // where it sits (by default: the bottom right corner)
}) {
  const { t } = useTranslation("schematic");
  if (!screen && !help) return null;
  return (
    <BoardIsland className={className ?? "bottom-3 right-3"}>
      {screen && (
        <BoardButton
          className={islandButton()}
          title={full ? t("view.exitFullscreen") : t("view.fullscreenTitle")}
          aria-label={t("view.fullscreen")}
          onClick={onFull}
        >
          {full ? <Shrink /> : <Expand />}
        </BoardButton>
      )}
      {help && (
        <BoardButton
          className={islandButton()}
          title={t("view.helpTitle")}
          aria-label={t("view.help")}
          onClick={onHelp}
        >
          <Help />
        </BoardButton>
      )}
    </BoardIsland>
  );
}
