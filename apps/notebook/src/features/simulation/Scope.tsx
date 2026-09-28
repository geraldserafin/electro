// The scope: the chosen quantities over the last moments, one row each (a voltage and a current
// never share an axis), on one time axis. Hovering shows the values at that moment.
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Close } from "@/shared/ui/icons";
import { si } from "./format";
import type { Live } from "./useLive";

const W = 640, ROW = 64, LEFT = 8, RIGHT = 96;
const unit = (name: string) => (name.startsWith("I_") ? "A" : "V");

function Name({ name }: { name: string }) {
  const [head, ...rest] = name.split("_");
  return <>{head}{rest.length > 0 && <sub>{rest.join("_")}</sub>}</>;
}

export function Scope({ live }: { live: Live }) {
  const { t } = useTranslation("simulation");
  const [hover, setHover] = useState<number | null>(null); // x in the chart
  const traces = live.traces;
  const t1 = Math.max(0, ...traces.map((tr) => tr.t[tr.t.length - 1] ?? 0));
  const span = Math.max(1e-4, live.speed * 2);
  const t0 = t1 - span;
  const w = W - LEFT - RIGHT;
  const x = (s: number) => LEFT + ((s - t0) / span) * w;
  const at = hover === null ? null : t0 + ((hover - LEFT) / w) * span;
  const choices = live.quantities().filter((n) => !live.scope.includes(n));

  return (
    <section className="mt-2 rounded-xl border border-line p-2.5" aria-label={t("scope.title")}>
      <header className="flex flex-wrap items-center gap-1.5 text-[13px]">
        <h4 className="m-0 mr-1 text-[13px] font-medium text-muted">{t("scope.title")}</h4>
        {live.scope.map((name, k) => (
          <span key={name} className="inline-flex items-center gap-1.5 rounded-md bg-hover py-0.5 pl-2 pr-0.5">
            <span className="h-0.75 w-3.5 rounded-full" style={{ background: `var(--series-${(k % 4) + 1})` }} />
            <Name name={name} />
            <button className="rounded p-0.5 text-muted hover:bg-selected" aria-label={t("scope.remove", { name })}
                    title={t("scope.remove", { name })} onClick={() => live.setScope(live.scope.filter((n) => n !== name))}>
              <Close />
            </button>
          </span>
        ))}
        {live.scope.length < 4 && choices.length > 0 && (
          <select className="rounded-md bg-hover px-1.5 py-1 text-[13px]" value="" aria-label={t("scope.add")}
                  onChange={(e) => e.target.value && live.setScope([...live.scope, e.target.value])}>
            <option value="">{t("scope.add")}</option>
            {choices.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        )}
        <span className="flex-1" />
        <span className="text-[12px] text-faint">{t("scope.window", { time: si(span, "s") })}</span>
      </header>
      {!traces.length ? <p className="m-1 text-[13px] text-muted">{t("scope.empty")}</p> : (
        <svg viewBox={`0 0 ${W} ${traces.length * ROW + 4}`} className="mt-1 block w-full"
             onPointerMove={(e) => {
               const box = e.currentTarget.getBoundingClientRect();
               const px = ((e.clientX - box.left) / box.width) * W;
               setHover(px >= LEFT && px <= LEFT + w ? px : null);
             }}
             onPointerLeave={() => setHover(null)}>
          {traces.map((tr, k) => {
            const top = k * ROW + 6, h = ROW - 16;
            const lo = Math.min(0, ...tr.v), hi = Math.max(lo + 1e-9, ...tr.v);
            const y = (v: number) => top + h - ((v - lo) / (hi - lo)) * h;
            const points = tr.t.map((s, i) => `${x(s).toFixed(1)},${y(tr.v[i]).toFixed(1)}`).join(" ");
            const i = at === null ? tr.v.length - 1 : Math.max(0, tr.t.findIndex((s) => s >= at));
            const value = tr.v[i] ?? 0;
            return (
              <g key={tr.name}>
                <line x1={LEFT} x2={LEFT + w} y1={y(0)} y2={y(0)} stroke="currentColor" strokeOpacity={0.15} />
                <polyline points={points} fill="none" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
                          style={{ stroke: `var(--series-${(k % 4) + 1})` }} />
                <text x={LEFT + w + 10} y={top + h / 2 + 4} fontSize={13} fill="currentColor" className="tabular-nums">
                  {si(value, unit(tr.name))}
                </text>
                <text x={LEFT + w + 10} y={top + h / 2 - 12} fontSize={11} fill="currentColor" opacity={0.6}>{tr.name}</text>
              </g>
            );
          })}
          {hover !== null && <line x1={hover} x2={hover} y1={0} y2={traces.length * ROW} stroke="currentColor" strokeOpacity={0.35} />}
        </svg>
      )}
    </section>
  );
}
