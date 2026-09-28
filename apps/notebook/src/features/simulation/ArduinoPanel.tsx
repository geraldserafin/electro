// Under a schematic with an Arduino: its sketch (C++, kept in the element's text), uploaded to the
// emulated chip while the circuit runs, and what the chip writes to its serial port.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { CodeEditor } from "@/features/notebook/cells/CodeEditor";
import { editorFrame } from "@/features/notebook/cells/CodeCell";
import type { ElementData } from "@/shared/model/types";
import { Upload } from "@/shared/ui/icons";
import type { Live } from "./useLive";

export function ArduinoPanel({ element, live, onChange }: {
  element: ElementData;
  live: Live;
  onChange: (sketch: string) => void;
}) {
  const { t } = useTranslation("simulation");
  const [typed, setTyped] = useState("");
  const state = live.sketches[element.id];
  const running = live.status === "running" || live.status === "paused";
  const sketch = element.text ?? "";
  const changed = state?.kind === "running" && state.sketch !== sketch;
  const note =
    !running ? t("arduino.notRunning")
    : state === undefined ? ""
    : state.kind === "compiling" ? t("arduino.compiling")
    : state.kind === "running" ? (changed ? t("arduino.changed") : t("arduino.running"))
    : state.kind === "failed" ? t("arduino.failed")
    : t(`arduino.${state.kind}`);
  return (
    <section className="mt-2 grid gap-2 rounded-xl border border-line p-2.5" aria-label={t("arduino.title", { id: element.id })}>
      <header className="flex flex-wrap items-center gap-2">
        <h4 className="m-0 text-[13px] font-medium text-muted">{t("arduino.title", { id: element.id })}</h4>
        <span className="flex-1" />
        <span className="text-[13px] text-muted" aria-live="polite">{note}</span>
        <button className="inline-flex items-center gap-1.5 rounded-lg bg-hover px-2.5 py-1 text-[14px] hover:bg-selected disabled:opacity-45"
                disabled={!running || state?.kind === "compiling"} title={t("arduino.uploadTitle")}
                onClick={() => live.upload(element.id)}>
          <Upload /> {t("arduino.upload")}
        </button>
      </header>
      <div className={editorFrame}>
        <CodeEditor value={sketch} onChange={onChange} language="cpp" minHeight={120} />
      </div>
      {state?.kind === "failed" && (
        <pre className="m-0 max-h-48 overflow-auto rounded-lg bg-err-bg p-2 text-[13px] text-danger whitespace-pre-wrap">{state.output}</pre>
      )}
      {running && (
        <div className="grid gap-1">
          <div className="flex items-center gap-2">
            <h5 className="m-0 text-[12px] font-medium text-muted">{t("arduino.serial")}</h5>
            <span className="flex-1" />
            <button className="rounded-md px-1.5 text-[12px] text-muted hover:bg-hover" onClick={live.clearSerial}>{t("arduino.clear")}</button>
          </div>
          <pre className="m-0 h-28 overflow-auto rounded-lg bg-code-bg p-2 font-mono text-[13px] whitespace-pre-wrap"
               ref={(el) => { if (el) el.scrollTop = el.scrollHeight; }}>
            {live.serial || <span className="text-faint">{t("arduino.serialEmpty")}</span>}
          </pre>
          <form className="flex gap-1.5" onSubmit={(e) => { e.preventDefault(); live.sendSerial(`${typed}\n`); setTyped(""); }}>
            <input className="flex-1 rounded-lg bg-hover px-2.5 py-1 font-mono text-[13px] focus:bg-paper focus:outline-2 focus:outline-accent-soft"
                   value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={t("arduino.sendPlaceholder")}
                   aria-label={t("arduino.sendPlaceholder")} spellCheck={false} />
            <button className="rounded-lg bg-hover px-2.5 py-1 text-[13px] hover:bg-selected">{t("arduino.send")}</button>
          </form>
        </div>
      )}
    </section>
  );
}
