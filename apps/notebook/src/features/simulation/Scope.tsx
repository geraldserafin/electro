// The scope: the chosen quantities over the last moments, one lane each (a voltage and a current
// never share an axis), on one time axis. Drawn at the size it is on screen (not a scaled
// picture), so text and lines stay crisp at any width; hovering shows the values at that moment.
import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import { Close, Plus } from "@/shared/ui/icons";
import { si } from "./format";
import type { Live } from "./useLive";

const LEFT = 52, RIGHT = 112, AXIS = 22, LANE = 84;
const unit = (name: string) => (name.startsWith("I_") ? "A" : "V");
const series = (k: number) => `var(--series-${(k % 4) + 1})`;

function Name({ name }: { name: string }) {
  const [head, ...rest] = name.split("_");
  return <>{head}{rest.length > 0 && <sub>{rest.join("_")}</sub>}</>;
}

/** Round numbers for a lane's grid: 0 and about two more, within lo…hi. */
function ticks(lo: number, hi: number): number[] {
  const span = hi - lo || 1;
  const step = 10 ** Math.floor(Math.log10(span / 2));
  const nice = [1, 2, 5, 10].map((m) => m * step).find((s) => span / s <= 3) ?? step * 10;
  const out: number[] = [];
  for (let v = Math.ceil(lo / nice) * nice; v <= hi + nice * 1e-9; v += nice) out.push(Number(v.toPrecision(6)));
  return out;
}

/** The quantities on the scope (chips) and what can be added. */
export function ScopeChoice({ live }: { live: Live }) {
  const { t } = useTranslation("simulation");
  const choices = live.quantities().filter((n) => !live.scope.includes(n));
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[13px]">
      {live.scope.map((name, k) => (
        <span key={name} className="inline-flex items-center gap-1.5 rounded-md border border-line bg-board py-0.5 pl-2 pr-0.5">
          <span className="h-0.75 w-3.5 rounded-full" style={{ background: series(k) }} />
          <Name name={name} />
          <button className="rounded p-0.5 text-muted hover:bg-selected [&_svg]:size-3.5" aria-label={t("scope.remove", { name })}
                  title={t("scope.remove", { name })} onClick={() => live.setScope(live.scope.filter((n) => n !== name))}>
            <Close />
          </button>
        </span>
      ))}
      {live.scope.length < 4 && choices.length > 0 && (
        <label className="relative inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-muted hover:bg-hover [&_svg]:size-3.5">
          <Plus /> {t("scope.add")}
          <select className="absolute inset-0 cursor-pointer opacity-0" value="" aria-label={t("scope.add")}
                  onChange={(e) => e.target.value && live.setScope([...live.scope, e.target.value])}>
            <option value="" disabled>{t("scope.add")}</option>
            {choices.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      )}
    </div>
  );
}

export function Scope({ live, fill }: {
  live: Live;
  fill?: boolean; // as tall as its parent (full screen); else a lane per quantity
}) {
  const { t } = useTranslation("simulation");
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 640, h: 200 });
  const [hover, setHover] = useState<number | null>(null); // x on the chart, px
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const traces = live.traces;
  const span = Math.max(1e-4, live.speed * 2);
  const t1 = Math.max(span, ...traces.map((tr) => tr.t[tr.t.length - 1] ?? 0));
  const t0 = t1 - span;
  const w = Math.max(40, size.w - LEFT - RIGHT);
  const lane = fill ? Math.max(48, (size.h - AXIS) / Math.max(1, traces.length)) : LANE;
  const height = fill ? size.h : traces.length * LANE + AXIS;
  const x = (s: number) => LEFT + ((s - t0) / span) * w;
  const at = hover === null ? null : t0 + ((hover - LEFT) / w) * span;
  // the time axis: 0 is now, the ticks go back from it
  const back = ticks(0, span).filter((v) => v <= span);

  return (
    <div ref={box} className={cn("relative select-none", fill ? "h-full min-h-0" : "")} style={fill ? undefined : { height }}>
      {!traces.length ? <p className="m-3 text-[13px] text-muted">{t("scope.empty")}</p> : (
        <svg width={size.w} height={height} className="block text-fg"
             onPointerMove={(e) => {
               const px = e.clientX - e.currentTarget.getBoundingClientRect().left;
               const scale = e.currentTarget.getBoundingClientRect().width / size.w || 1; // the page's zoom
               const p = px / scale;
               setHover(p >= LEFT && p <= LEFT + w ? p : null);
             }}
             onPointerLeave={() => setHover(null)}>
          {traces.map((tr, k) => {
            const top = k * lane + 8, h = lane - 18;
            let lo = Math.min(0, ...tr.v), hi = Math.max(0, ...tr.v);
            if (hi - lo < 1e-12) hi = lo + 1;
            const pad = (hi - lo) * 0.08;
            lo -= lo < 0 ? pad : 0;
            hi += pad;
            const y = (v: number) => top + h - ((v - lo) / (hi - lo)) * h;
            const points = tr.t.map((s, i) => `${x(s).toFixed(1)},${y(tr.v[i]).toFixed(1)}`).join(" ");
            const i = at === null ? tr.v.length - 1 : Math.max(0, tr.t.findIndex((s) => s >= at));
            const value = tr.v[i] ?? 0;
            return (
              <g key={tr.name}>
                {ticks(lo, hi).map((v) => (
                  <g key={v}>
                    <line x1={LEFT} x2={LEFT + w} y1={y(v)} y2={y(v)} stroke="currentColor" strokeOpacity={v === 0 ? 0.28 : 0.08} />
                    <text x={LEFT - 6} y={y(v) + 3.5} fontSize={10} textAnchor="end" fill="currentColor" opacity={0.55}
                          className="tabular-nums">{si(v, unit(tr.name))}</text>
                  </g>
                ))}
                <polyline points={points} fill="none" strokeWidth={1.8} strokeLinejoin="round" strokeLinecap="round"
                          style={{ stroke: series(k) }} />
                {at !== null && tr.t[i] !== undefined && (
                  <circle cx={x(tr.t[i])} cy={y(value)} r={3.5} style={{ fill: series(k) }} stroke="var(--code-bg)" strokeWidth={1.5} />
                )}
                <rect x={LEFT + w + 12} y={top + h / 2 - 20} width={3} height={14} rx={1.5} style={{ fill: series(k) }} />
                <text x={LEFT + w + 20} y={top + h / 2 - 9} fontSize={11} fill="currentColor" opacity={0.65}>{tr.name}</text>
                <text x={LEFT + w + 12} y={top + h / 2 + 10} fontSize={14} fontWeight={600} fill="currentColor" className="tabular-nums">
                  {si(value, unit(tr.name))}
                </text>
              </g>
            );
          })}
          {/* the time axis, under the lanes */}
          <line x1={LEFT} x2={LEFT + w} y1={height - AXIS} y2={height - AXIS} stroke="currentColor" strokeOpacity={0.2} />
          {back.map((v) => (
            <text key={v} x={x(t1 - v)} y={height - 7} fontSize={10} textAnchor={v === 0 ? "end" : v === span ? "start" : "middle"}
                  fill="currentColor" opacity={0.55} className="tabular-nums">
              {v === 0 ? t("scope.now") : `−${si(v, "s")}`}
            </text>
          ))}
          {hover !== null && at !== null && (
            <g pointerEvents="none">
              <line x1={hover} x2={hover} y1={4} y2={height - AXIS} stroke="currentColor" strokeOpacity={0.35} strokeDasharray="3 3" />
              <text x={hover} y={height - AXIS - 4} fontSize={10} textAnchor="middle" fill="currentColor" opacity={0.7}
                    className="tabular-nums" paintOrder="stroke" stroke="var(--code-bg)" strokeWidth={4}>
                {si(at, "s")}
              </text>
            </g>
          )}
        </svg>
      )}
    </div>
  );
}
