// Under the board while it may run in time: start it, pause it, stop it, and how fast it goes.
import { useTranslation } from "react-i18next";
import { BoardButton } from "@/features/schematic";
import { Close, Play } from "@/shared/ui/icons";
import { si } from "./format";
import { SPEEDS, type Live } from "./useLive";

const Pause = () => (
  <svg viewBox="0 0 24 24" width={18} height={18} aria-hidden="true"><path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" /></svg>
);

export function LiveControls({ live }: { live: Live }) {
  const { t } = useTranslation("simulation");
  if (live.status === "off" || live.status === "starting")
    return (
      <BoardButton onClick={live.start} disabled={live.status === "starting"} title={t("controls.startTitle")}
                   className="px-2.5 font-medium">
        <Play /> {live.status === "starting" ? t("controls.starting") : t("controls.start")}
      </BoardButton>
    );
  const running = live.status === "running";
  return (
    <div className="flex items-center gap-1" role="group" aria-label={t("controls.label")}>
      <BoardButton icon onClick={running ? live.pause : live.resume} title={running ? t("controls.pause") : t("controls.resume")}
                   aria-label={running ? t("controls.pause") : t("controls.resume")}>
        {running ? <Pause /> : <Play />}
      </BoardButton>
      <BoardButton icon onClick={live.stop} title={t("controls.stop")} aria-label={t("controls.stop")}><Close /></BoardButton>
      <span className="min-w-24 px-1.5 font-mono text-[13px] tabular-nums" aria-live="off">
        {t("controls.time", { time: si(live.frame?.t ?? 0, "s") })}
      </span>
      <label className="flex items-center gap-1 text-[13px] text-muted" title={t("controls.speedTitle")}>
        {t("controls.speed")}
        <select className="rounded-md bg-hover px-1 py-0.5 text-fg" value={live.speed}
                onChange={(e) => live.setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => <option key={s} value={s}>{s}×</option>)}
        </select>
      </label>
      {live.frame?.behind && <span className="px-1 text-[12px] text-warn">{t("controls.behind")}</span>}
    </div>
  );
}
