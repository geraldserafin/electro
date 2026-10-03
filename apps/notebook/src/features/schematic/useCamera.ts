// The board shows the drawing (an endless plane) through a camera: a viewBox that pans and zooms,
// like Excalidraw. Nothing moves under the cursor unless you pan.
import { type RefObject, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { SchematicData, SymbolLibrary } from "@/shared/model/types";
import { bounds } from "./model";

export type Camera = { x: number; y: number; zoom: number }; // top-left corner of the view, in drawing px

const clampZoom = (z: number) => Math.min(3, Math.max(0.25, z));

/** Start with the drawing near the top-left, below the toolbar. */
function startCamera(sch: SchematicData, lib: SymbolLibrary): Camera {
  if (!sch.elements.length && !sch.wires.length) return { x: -40, y: -100, zoom: 1 };
  const [x0, y0] = bounds(sch, lib);
  return { x: x0 * lib.grid - 80, y: y0 * lib.grid - 110, zoom: 1 };
}

export function useCamera({
  value,
  library,
  viewRef,
  kept,
  inUse,
  inset = 0,
  onTwist,
  onPinch,
  full = false,
}: {
  value: SchematicData;
  library: SymbolLibrary;
  viewRef: RefObject<HTMLDivElement | null>; // the board's view: its size, its wheel
  kept?: { current: Camera | null }; // where the view was: kept there while the editor is away
  inUse: boolean; // the board was clicked (or is full screen): the wheel pans it, not the page
  inset?: number; // px of the board's top under a bar laid over it: "fit" centres in what is left
  onTwist?: (dir: 1 | -1) => void; // two fingers turned a quarter turn (past an eighth; 1: clockwise)
  onPinch?: () => void; // a second finger down: what the first one began is not to be (a drag, a wire)
  full?: boolean; // full screen: going in or out, the drawing fitted to the new size anew
}) {
  const G = library.grid;
  const [cam, setCam] = useState<Camera>(() => kept?.current ?? startCamera(value, library));
  useEffect(() => {
    if (kept) kept.current = cam;
  }, [cam, kept]);

  /** Screen px per CSS px of the board (not 1 when the page is scaled, e.g. CSS zoom). */
  const screenScale = () => {
    const el = viewRef.current;
    return el?.clientWidth ? el.getBoundingClientRect().width / el.clientWidth : 1;
  };

  // the size of the board on screen: the camera shows view.w × view.h screen px
  const [view, setView] = useState({ w: 800, h: 480 });
  const shown = useRef(view);
  // full screen toggled: its next size fits the drawing anew (a notebook's small board's zoom, kept in
  // a whole window, showed it far away)
  const refit = useRef(false);
  const wasFull = useRef(full);
  if (wasFull.current !== full) {
    wasFull.current = full;
    refit.current = true;
  }
  const fit = useRef<(size: { w: number; h: number }) => Camera>(() => startCamera(value, library));
  // measured before the first paint: a note opens with each drawing centred, as "fit" shows it
  // (unless the view was kept from before); later the board keeps its middle where it was
  // when it changes size (full screen, the window, a panel beside it)
  useLayoutEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const measure = () => {
      const size = { w: el.clientWidth, h: el.clientHeight };
      const before = shown.current;
      if (!size.w || (size.w === before.w && size.h === before.h)) return;
      shown.current = size;
      setView(size);
      if (refit.current) {
        refit.current = false;
        setCam(fit.current(size));
      } else
        setCam((c) => ({ ...c, x: c.x + (before.w - size.w) / 2 / c.zoom, y: c.y + (before.h - size.h) / 2 / c.zoom }));
    };
    const first = { w: el.clientWidth, h: el.clientHeight };
    if (first.w) {
      shown.current = first;
      setView(first);
      if (!kept?.current || full) setCam(fitted(first)); // (opened full screen: fitted to it, too)
    }
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, with the drawing as it opened
  }, [viewRef]);

  fit.current = (size) => fitted(size);
  /** A camera that shows the whole drawing (on a board of ``size``). */
  function fitted(size = view): Camera {
    if (!value.elements.length && !value.wires.length) return startCamera(value, library);
    const [x0, y0, x1, y1] = bounds(value, library);
    const w = (x1 - x0) * G + 160;
    const h = (y1 - y0) * G + 140;
    const zoom = clampZoom(Math.min(1.5, size.w / w, (size.h - 120 - inset) / h));
    return {
      x: ((x0 + x1) / 2) * G - size.w / 2 / zoom,
      y: ((y0 + y1) / 2) * G - (size.h + 40 + inset) / 2 / zoom,
      zoom,
    };
  }

  // the drawing is somewhere, but not in view (panned or zoomed away): offer the way back
  const lost = (() => {
    if (!value.elements.length && !value.wires.length) return false;
    const [x0, y0, x1, y1] = bounds(value, library);
    const [vx, vy, vw, vh] = [cam.x, cam.y, view.w / cam.zoom, view.h / cam.zoom];
    return x1 * G < vx || x0 * G > vx + vw || y1 * G < vy || y0 * G > vy + vh;
  })();

  const zoomAround = (factor: number, px = view.w / 2, py = view.h / 2) =>
    setCam((c) => {
      const zoom = clampZoom(c.zoom * factor);
      return { x: c.x + px / c.zoom - px / zoom, y: c.y + py / c.zoom - py / zoom, zoom };
    });

  // wheel / trackpad: pinch or ⌘/Ctrl zooms around the cursor; scrolling pans — but only once the
  // board is in use, so that the notebook page still scrolls past it
  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      const zooming = event.ctrlKey || event.metaKey;
      if (!zooming && !inUse) return;
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      // a trackpad pinch sends small steps, a mouse wheel big ones: cap a step at ~28%
      const step = Math.max(-25, Math.min(25, event.deltaY));
      const k = screenScale(); // the cursor's place on the board, in board px
      if (zooming) zoomAround(Math.exp(-step * 0.01), (event.clientX - rect.left) / k, (event.clientY - rect.top) / k);
      else setCam((c) => ({ ...c, x: c.x + event.deltaX / c.zoom, y: c.y + event.deltaY / c.zoom }));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  // two fingers (a touch screen): pinching zooms, moving them pans — the drawing stays under them.
  // Caught on the way down (capture): the board's own handlers do not see the second finger
  const camNow = useRef(cam);
  camNow.current = cam;
  const twist = useRef(onTwist);
  twist.current = onTwist;
  const pinchStart = useRef(onPinch);
  pinchStart.current = onPinch;
  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const touches = new Map<number, { x: number; y: number }>();
    let pinch: { d: number; x: number; y: number; a: number; cam: Camera } | null = null;
    let pinched = false; // till the last finger is up: the one left does not pan from where it started
    const between = () => {
      const [a, b] = [...touches.values()];
      return {
        d: Math.hypot(a.x - b.x, a.y - b.y) || 1,
        x: (a.x + b.x) / 2,
        y: (a.y + b.y) / 2,
        a: Math.atan2(b.y - a.y, b.x - a.x), // the line between them: turned, a twist
      };
    };
    const down = (event: PointerEvent) => {
      if (event.pointerType !== "touch") return;
      touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (touches.size < 2) return;
      event.stopPropagation();
      if (touches.size === 2) {
        pinch = { ...between(), cam: camNow.current };
        pinchStart.current?.();
      }
      pinched = true;
    };
    const move = (event: PointerEvent) => {
      if (!touches.has(event.pointerId)) return;
      touches.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pinched) event.stopPropagation();
      if (!pinch || touches.size !== 2) return;
      const now = between();
      // turned past an eighth of a turn: a quarter turn that way (the next one another quarter on)
      const turned = Math.atan2(Math.sin(now.a - pinch.a), Math.cos(now.a - pinch.a));
      if (Math.abs(turned) >= Math.PI / 4) {
        const dir = turned > 0 ? 1 : -1;
        pinch.a += (dir * Math.PI) / 2;
        twist.current?.(dir);
      }
      const rect = el.getBoundingClientRect();
      const k = screenScale();
      const { cam: from } = pinch;
      const zoom = clampZoom((from.zoom * now.d) / pinch.d);
      // the drawing's point that was between the fingers, between them again
      const px = from.x + (pinch.x - rect.left) / k / from.zoom,
        py = from.y + (pinch.y - rect.top) / k / from.zoom;
      setCam({ x: px - (now.x - rect.left) / k / zoom, y: py - (now.y - rect.top) / k / zoom, zoom });
    };
    const up = (event: PointerEvent) => {
      touches.delete(event.pointerId);
      if (touches.size < 2) pinch = null;
      if (!touches.size) pinched = false;
    };
    el.addEventListener("pointerdown", down, true);
    el.addEventListener("pointermove", move, true);
    el.addEventListener("pointerup", up, true);
    el.addEventListener("pointercancel", up, true);
    return () => {
      el.removeEventListener("pointerdown", down, true);
      el.removeEventListener("pointermove", move, true);
      el.removeEventListener("pointerup", up, true);
      el.removeEventListener("pointercancel", up, true);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- screenScale reads the element as it is then
  }, [viewRef]);

  return { cam, setCam, view, fitted, lost, zoomAround, screenScale };
}
