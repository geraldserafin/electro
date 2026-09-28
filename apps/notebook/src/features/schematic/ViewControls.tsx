// The board's corners: zoom and history bottom left; full screen and the shortcuts bottom right.
import { useTranslation } from "react-i18next";
import { Expand, Help, Minus, Plus, Redo, Shrink, Undo } from "@/shared/ui/icons";
import { BoardButton, BoardIsland, Separator } from "./Board";

export function ZoomAndHistory({ zoom, onZoom, onFit, onUndo, onRedo }: {
  zoom: number; onZoom: (factor: number) => void; onFit: () => void; onUndo: () => void; onRedo: () => void;
}) {
  const { t } = useTranslation("schematic");
  return (
    <BoardIsland className="bottom-3 left-3">
      <BoardButton icon title={t("view.zoomOut")} aria-label={t("view.zoomOut")} onClick={() => onZoom(1 / 1.2)}><Minus /></BoardButton>
      <BoardButton className="min-w-13 justify-center tabular-nums" title={t("view.fitTitle")} aria-label={t("view.fit")} onClick={onFit}>
        {Math.round(zoom * 100)}%
      </BoardButton>
      <BoardButton icon title={t("view.zoomIn")} aria-label={t("view.zoomIn")} onClick={() => onZoom(1.2)}><Plus /></BoardButton>
      <Separator />
      <BoardButton icon title={t("view.undoTitle")} aria-label={t("view.undo")} onClick={onUndo}><Undo /></BoardButton>
      <BoardButton icon title={t("view.redoTitle")} aria-label={t("view.redo")} onClick={onRedo}><Redo /></BoardButton>
    </BoardIsland>
  );
}

export function ScreenAndHelp({ full, onFull, onHelp }: { full: boolean; onFull: () => void; onHelp: () => void }) {
  const { t } = useTranslation("schematic");
  return (
    <BoardIsland className="bottom-3 right-3">
      <BoardButton icon title={full ? t("view.exitFullscreen") : t("view.fullscreenTitle")} aria-label={t("view.fullscreen")} onClick={onFull}>
        {full ? <Shrink /> : <Expand />}
      </BoardButton>
      <BoardButton icon title={t("view.helpTitle")} aria-label={t("view.help")} onClick={onHelp}><Help /></BoardButton>
    </BoardIsland>
  );
}
