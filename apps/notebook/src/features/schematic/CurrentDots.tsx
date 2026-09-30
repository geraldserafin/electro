// The current, moving: dots along the wires and through the elements while the circuit runs (as
// EveryCircuit draws it), faster where more flows, the way it goes. The biggest current in the circuit
// moves fastest; a thousandth of it (or less than a microampere) stands still, not drawn.
// Each frame of the simulation brings new currents (30 a second); the dots move at the screen's
// pace in between, straight on the DOM (no React render each time).
import { useEffect, useRef } from "react";
import type { Segment } from "./flow";

const GAP = 16; // px between dots
const FAST = 90; // px/s: the biggest current's
const RANGE = 3; // decades below it still moving (slower and slower)
const FLOOR = 1e-6; // A: less is nothing

const still = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

export function CurrentDots({
  segments,
  currents,
  moving,
}: {
  segments: Segment[];
  currents: ArrayLike<number>; // each segment's, from a to b (A)
  moving: boolean; // paused: they stay where they are
}) {
  const paths = useRef<(SVGPathElement | null)[]>([]);
  const latest = useRef({ segments, currents, moving });
  latest.current = { segments, currents, moving };
  const phase = useRef(new Float64Array(0)); // each segment's dots' place along its axis (px, mod GAP)

  useEffect(() => {
    if (still()) return;
    let frame = 0;
    let last = performance.now();
    let top = 0; // the biggest current lately (it falls slowly: one quiet frame does not speed up the rest)
    const tick = (now: number) => {
      frame = requestAnimationFrame(tick);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      const { segments, currents, moving } = latest.current;
      if (phase.current.length !== segments.length) phase.current = new Float64Array(segments.length);
      let most = 0;
      for (let i = 0; i < segments.length; i++) most = Math.max(most, Math.abs(currents[i] ?? 0));
      top = Math.max(most, top * 0.97);
      for (let i = 0; i < segments.length; i++) {
        const path = paths.current[i];
        if (!path) continue;
        const I = currents[i] ?? 0;
        const size = Math.abs(I);
        const speed = size < FLOOR || !top ? 0 : Math.max(0, 1 + Math.log10(size / top) / RANGE);
        if (!speed) {
          path.style.opacity = "0";
          continue;
        }
        // along its axis: dots at the points where x (or y) ≡ phase, so pieces in a row line up
        const { a, b } = segments[i];
        const across = a[1] === b[1];
        const sign = Math.sign(across ? b[0] - a[0] : b[1] - a[1]) || 1;
        if (moving) phase.current[i] = (phase.current[i] + sign * Math.sign(I) * speed * FAST * dt) % GAP;
        path.style.opacity = "1";
        path.style.strokeDashoffset = String(sign * ((across ? a[0] : a[1]) - phase.current[i]));
      }
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  if (still()) return null;
  return (
    <g className="current-dots" aria-hidden>
      {segments.map(({ a, b }, i) => (
        <path
          key={i}
          ref={(el) => {
            paths.current[i] = el;
          }}
          d={`M${a[0]} ${a[1]}L${b[0]} ${b[1]}`}
          strokeDasharray={`0 ${GAP}`}
          style={{ opacity: 0 }}
        />
      ))}
    </g>
  );
}
