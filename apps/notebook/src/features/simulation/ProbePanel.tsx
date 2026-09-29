// The meter, while the circuit runs: an element (or a wire) clicked with it shows here what it is
// doing — each quantity's value now, big, and under it its last moments as a small chart. A panel
// like the inspector's, on the right; it records what it shows only while it is open.
import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Panel, PanelHead, Section } from "@/features/schematic";
import { si } from "./format";
import type { Live, ScopeTrace } from "./useLive";

const unit = (name: string) => (name.startsWith("I_") ? "A" : "V");
const series = (k: number) => `var(--series-${(k % 4) + 1})`;

/** "U_R_1" → U and R₁'s subscript; "V_n3" → V at n3. */
function Name({ name }: { name: string }) {
  const [head, ...rest] = name.split("_");
  return <>{head}{rest.length > 0 && <sub>{rest.join("_")}</sub>}</>;
}

/** The last moments of one quantity: a line over the panel's width, its range at the side. */
function Spark({ trace, k }: { trace: ScopeTrace; k: number }) {
  const W = 220, H = 52;
  if (trace.t.length < 2) return <div style={{ height: H }} />;
  const t0 = trace.t[0], t1 = trace.t[trace.t.length - 1];
  let lo = Math.min(0, ...trace.v), hi = Math.max(0, ...trace.v);
  if (hi - lo < 1e-12) hi = lo + 1;
  const x = (s: number) => ((s - t0) / (t1 - t0 || 1)) * W;
  const y = (v: number) => H - 3 - ((v - lo) / (hi - lo)) * (H - 6);
  const points = trace.t.map((s, i) => `${x(s).toFixed(1)},${y(trace.v[i]).toFixed(1)}`).join(" ");
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="block w-full rounded-lg bg-hover" style={{ height: H }}>
        {lo < 0 && hi > 0 && <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="currentColor" strokeOpacity={0.15} vectorEffect="non-scaling-stroke" />}
        <polyline points={points} fill="none" strokeWidth={1.8} strokeLinejoin="round" vectorEffect="non-scaling-stroke" style={{ stroke: series(k) }} />
      </svg>
      <span className="absolute top-0.5 right-1.5 text-[10px] tabular-nums text-faint">{si(hi, unit(trace.name))}</span>
      <span className="absolute bottom-0.5 right-1.5 text-[10px] tabular-nums text-faint">{si(lo, unit(trace.name))}</span>
    </div>
  );
}

export type Probed = { type: "element"; id: string } | { type: "wire"; index: number };

export function ProbePanel({ live, target, caption, title, icon, onClose }: {
  live: Live;
  target: Probed;
  caption: string; // what it is ("Rezystor", "Przewód")
  title?: string; // its name (R_1)
  icon?: ReactNode;
  onClose: () => void;
}) {
  const { t } = useTranslation("simulation");
  const key = target.type === "element" ? target.id : `wire:${target.index}`;
  // what to record: an element's voltage and current (and the like), a wire's node voltage
  useEffect(() => {
    const names = target.type === "element" ? live.quantitiesOf(target.id).slice(0, 4)
      : [live.wireVoltage(target.index)].filter((n): n is string => !!n);
    live.setProbe(names);
    return () => live.setProbe([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const traces = live.probeTraces;
  return (
    <Panel className="top-15 right-3 w-66 max-h-[calc(100%-8rem)] overflow-y-auto" role="group" aria-label={t("probe.label")}>
      <PanelHead icon={icon} caption={caption} title={title} onClose={onClose} closeLabel={t("probe.close")} />
      {!traces.length && <p className="m-0 text-[13px] text-muted">{target.type === "wire" ? t("probe.ground") : t("probe.nothing")}</p>}
      {traces.map((trace, k) => (
        <Section key={trace.name} label={<Name name={trace.name} />}>
          <span className="text-[22px] font-semibold tabular-nums leading-none">{si(trace.v[trace.v.length - 1] ?? 0, unit(trace.name))}</span>
          <Spark trace={trace} k={k} />
        </Section>
      ))}
    </Panel>
  );
}
