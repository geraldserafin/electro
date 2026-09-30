// An Arduino's sketch (C++, kept in the element's text): the editor, and uploading it to the
// emulated chip while the circuit runs. It sits in the cell's code view (a tab of its own) or,
// full screen, beside the board like a file in an IDE; how it compiled and what the chip writes
// to its serial port are in the console.
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { CodeEditor } from "@/features/notebook/cells/CodeEditor";
import { cn } from "@/shared/lib/cn";
import type { ElementData } from "@/shared/model/types";
import { Upload } from "@/shared/ui/icons";
import { compiler } from "./compiler";
import { isPrebuilt } from "./compiler/prebuilt";
import { firmwareFile } from "./firmware";
import type { Live, SketchState } from "./useLive";

/** What the sketch is doing, in words ("" when there is nothing to say). */
export function useSketchNote(state: SketchState | undefined, running: boolean, changed: boolean): string {
  const { t } = useTranslation("simulation");
  return !running
    ? t("arduino.notRunning")
    : state === undefined
      ? ""
      : state.kind === "compiling"
        ? t("arduino.compiling")
        : state.kind === "running"
          ? changed
            ? t("arduino.changed")
            : t("arduino.running")
          : state.kind === "failed"
            ? t("arduino.failed")
            : state.kind === "tooBig"
              ? t("arduino.tooBig", { size: state.size, flash: state.flash })
              : t(`arduino.${state.kind}`);
}

/** Compile and upload, an icon; lit when the sketch changed since it went to the chip. Its title says how it is. */
export function UploadButton({
  element,
  live,
  className,
}: {
  element: ElementData;
  live: Live;
  className?: string; // on an island: its size
}) {
  const { t } = useTranslation("simulation");
  const state = live.sketches[element.id];
  const running = live.status === "running" || live.status === "paused";
  const changed = state?.kind === "running" && state.sketch !== (element.text ?? "");
  const note = useSketchNote(state, running, changed);
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center size-7 rounded-md text-muted hover:bg-selected hover:text-fg disabled:opacity-40",
        changed && "text-primary",
        state?.kind === "compiling" && "animate-blink",
        className,
      )}
      disabled={!running || state?.kind === "compiling"}
      onClick={() => live.upload(element.id)}
      title={`${t("arduino.uploadTitle")}${note ? ` — ${note}` : ""}`}
      aria-label={t("arduino.upload")}
    >
      <Upload />
    </button>
  );
}

export function SketchEditor({
  element,
  live,
  onChange,
  fill,
}: {
  element: ElementData;
  live: Live;
  onChange: (sketch: string) => void;
  fill?: boolean; // as tall as its parent (the side pane, full screen), edge to edge
}) {
  // the page's compiler for the board starts loading now, so the first upload does not wait for it (not for a
  // program given whole, nor for a sketch compiled ahead: an example's, as it is there)
  const given = firmwareFile(element.text ?? "") !== null;
  const opened = useRef(element.text ?? "");
  useEffect(() => {
    const board = element.kind === "pico" ? "pico" : "uno";
    if (!given)
      void isPrebuilt(board, opened.current).then((ahead) => {
        if (!ahead) compiler.load(board).catch(() => {});
      });
  }, [element.kind, given]);
  const state = live.sketches[element.id];
  return (
    <section className={cn("flex flex-col", fill && "h-full min-h-0")}>
      <div className={cn(fill && "flex-1 min-h-0 overflow-hidden")}>
        <CodeEditor
          value={element.text ?? ""}
          onChange={onChange}
          language="cpp"
          minHeight={fill ? undefined : 120}
          fill={fill}
        />
      </div>
      {state?.kind === "failed" && (
        <pre className="m-0 max-h-48 flex-none overflow-auto border-t border-line bg-err-bg p-2 text-[13px] text-danger whitespace-pre-wrap">
          {state.output}
        </pre>
      )}
    </section>
  );
}
