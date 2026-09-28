// The board shows the drawing (an endless plane) through a camera: a viewBox that pans and zooms,
// like Excalidraw. Nothing moves under the cursor unless you pan.
import { useEffect, useState, type RefObject } from "react";
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

export function useCamera({ value, library, viewRef, kept, inUse }: {
  value: SchematicData;
  library: SymbolLibrary;
  viewRef: RefObject<HTMLDivElement | null>; // the board's view: its size, its wheel
  kept?: { current: Camera | null }; // where the view was: kept there while the editor is away
  inUse: boolean; // the board was clicked (or is full screen): the wheel pans it, not the page
}) {
  const G = library.grid;
  const [cam, setCam] = useState<Camera>(() => kept?.current ?? startCamera(value, library));
  useEffect(() => { if (kept) kept.current = cam; }, [cam, kept]);

  /** Screen px per CSS px of the board (not 1 when the page is scaled, e.g. CSS zoom). */
  const screenScale = () => {
    const el = viewRef.current;
    return el && el.clientWidth ? el.getBoundingClientRect().width / el.clientWidth : 1;
  };

  // the size of the board on screen: the camera shows view.w × view.h screen px
  const [view, setView] = useState({ w: 800, h: 480 });
  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setView({ w: el.clientWidth, h: el.clientHeight }));
    observer.observe(el);
    return () => observer.disconnect();
  }, [viewRef]);

  /** A camera that shows the whole drawing. */
  const fitted = (): Camera => {
    if (!value.elements.length && !value.wires.length) return startCamera(value, library);
    const [x0, y0, x1, y1] = bounds(value, library);
    const w = (x1 - x0) * G + 160;
    const h = (y1 - y0) * G + 140;
    const zoom = clampZoom(Math.min(1.5, view.w / w, (view.h - 120) / h));
    return { x: ((x0 + x1) / 2) * G - view.w / 2 / zoom, y: ((y0 + y1) / 2) * G - (view.h + 40) / 2 / zoom, zoom };
  };

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

  return { cam, setCam, view, fitted, lost, zoomAround, screenScale };
}
