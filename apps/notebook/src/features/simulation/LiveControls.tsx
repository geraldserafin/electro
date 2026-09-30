// Running in time: start it (a button on the board), and while it runs — in the simulation
// panel's bar — the time with a light for running / paused, the speed, pause and stop.
import { useTranslation } from "react-i18next";
import { BoardButton } from "@/features/schematic";
import { cn } from "@/shared/lib/cn";
import { Play, WarningIcon } from "@/shared/ui/icons";
import { type Live, SPEEDS } from "./useLive";

const Pause = () => (
  <svg viewBox="0 0 24 24" width={16} height={16} aria-hidden="true">
    <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />
  </svg>
);
const Stop = () => (
  <svg viewBox="0 0 24 24" width={14} height={14} aria-hidden="true">
    <rect x="5" y="5" width="14" height="14" rx="2.5" fill="currentColor" />
  </svg>
);

/**
 * The time, steady: always in seconds, as many decimals as the speed makes worth seeing (1×: 0.01 s,
 * 0.001×: 0.00001 s), padded so the digits never move as it counts (unlike si()'s changing prefixes).
 */
const clock = (t: number, speed: number) => {
  const decimals = 2 + Math.max(0, Math.round(-Math.log10(speed)));
  return `${t.toFixed(decimals).padStart(decimals + 4, " ")} s`;
};

const Speaker = ({ muted }: { muted: boolean }) => (
  <svg
    viewBox="0 0 24 24"
    width={16}
    height={16}
    aria-hidden="true"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
  >
    <path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z" fill="currentColor" stroke="none" />
    {muted ? <path d="M16 9.5l5 5M21 9.5l-5 5" /> : <path d="M15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11" />}
  </svg>
);

const icon = "inline-flex items-center justify-center size-7 rounded-md text-muted hover:bg-selected hover:text-fg";

export function LiveControls({ live }: { live: Live }) {
  const { t } = useTranslation("simulation");
  if (live.status === "off" || live.status === "starting")
    return (
      <BoardButton
        onClick={() => live.start()}
        disabled={live.status === "starting"}
        title={t("controls.startTitle")}
        className="h-9 px-3 font-medium"
      >
        <Play /> {live.status === "starting" ? t("controls.starting") : t("controls.start")}
      </BoardButton>
    );
  const running = live.status === "running";
  return (
    <div className="flex items-center gap-0.5" role="group" aria-label={t("controls.label")}>
      {/* its place is kept whether shown or not: it comes and goes from frame to frame, the bar stays still */}
      <span
        className={cn("inline-flex items-center px-1 text-warn [&_svg]:size-4", !live.frame?.behind && "invisible")}
        title={t("controls.behind")}
        aria-label={live.frame?.behind ? t("controls.behind") : undefined}
      >
        <WarningIcon />
      </span>
      <span
        className="inline-flex items-center gap-1.5 h-7 px-2 font-mono text-[12px] tabular-nums text-fg whitespace-pre"
        aria-live="off"
        title={running ? t("controls.running") : t("controls.paused")}
      >
        <span className={cn("size-1.5 rounded-full", running ? "bg-ok animate-pulse" : "bg-warn")} />
        {clock(live.frame?.t ?? 0, live.speed)}
      </span>
      <select
        className="h-7 rounded-md bg-transparent px-1.5 font-mono text-[12px] text-muted hover:bg-selected hover:text-fg cursor-pointer"
        value={live.speed}
        title={t("controls.speedTitle")}
        aria-label={t("controls.speed")}
        onChange={(e) => live.setSpeed(Number(e.target.value))}
      >
        {SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}×
          </option>
        ))}
      </select>
      <span className="w-px h-4 mx-1 bg-line" />
      <button
        className={icon}
        onClick={running ? live.pause : live.resume}
        title={running ? t("controls.pause") : t("controls.resume")}
        aria-label={running ? t("controls.pause") : t("controls.resume")}
      >
        {running ? <Pause /> : <Play />}
      </button>
      {live.hasSound && (
        <button
          className={icon}
          onClick={() => live.setMuted(!live.muted)}
          aria-pressed={live.muted}
          title={live.muted ? t("controls.unmute") : t("controls.mute")}
          aria-label={live.muted ? t("controls.unmute") : t("controls.mute")}
        >
          <Speaker muted={live.muted} />
        </button>
      )}
      <button
        className={cn(icon, "hover:text-danger")}
        onClick={live.stop}
        title={t("controls.stop")}
        aria-label={t("controls.stop")}
      >
        <Stop />
      </button>
    </div>
  );
}
