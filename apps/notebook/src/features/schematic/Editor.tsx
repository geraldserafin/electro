// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
//
// The drawing lives on an endless plane; the board shows it through a camera (useCamera), like
// Excalidraw. Here: the state of the drawing being edited, the pointer and the keyboard; the
// islands around it are components of their own.
import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ElementData, ElementResult, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { cn } from "@/shared/lib/cn";
import { Target } from "@/shared/ui/icons";
import { board, BoardIsland, boardIsland } from "./Board";
import { ElementView, liveColor } from "./ElementView";
import { HelpPanel } from "./HelpPanel";
import { Inspector, type Selection } from "./Inspector";
import { LibraryPanel } from "./LibraryPanel";
import {
  KINDS, attach, bounds, defaultText, elbow, inBox, moveGroup, isComponent, isConnectionPoint, junctions,
  ledColor, nextId, moveSegment, openPins, pins, rotatedAbout, same, simplify, updateElement,
} from "./model";
import { SymbolIcon } from "./SymbolIcon";
import { LiveToolbar, Toolbar, type LiveTool, type Tool } from "./Toolbar";
import { useCamera, type Camera } from "./useCamera";
import { useHistory } from "./useHistory";
import { ScreenAndHelp, ZoomAndHistory } from "./ViewControls";
import "./Canvas.css";

type Gesture =
  | { type: "move"; id: string; start: Point; origin: Point; snapshot: SchematicData; moved: boolean } // start: not rounded
  | { type: "wire"; from: Point }
  | { type: "segment"; wire: number; index: number; start: Point; snapshot: SchematicData; moved: boolean }
  | { type: "group"; ids: string[]; wires: number[]; start: Point; snapshot: SchematicData; moved: boolean }
  | { type: "box"; from: Point; to: Point }; // shift + drag on empty space, in drawing units (not rounded)

/** What the meter was put on while the circuit runs: an element, or a wire. */
export type ProbeTarget = { type: "element"; id: string } | { type: "wire"; index: number };

/** The circuit running in time (features/simulation), as the board shows it. */
export interface LiveView {
  wires: (number | null)[]; // each wire's voltage
  pins: Record<string, (number | null)[]>; // each element's pins' voltages
  scale: number; // the largest |V|: full colour
  leds: Record<string, number>; // LED id → brightness 0–1
  pressed: string[]; // buttons held down
  onPress: (id: string, down: boolean) => void;
}

interface Props {
  value: SchematicData;
  onChange: (value: SchematicData) => void;
  library: SymbolLibrary;
  results?: Record<string, ElementResult>; // from a run, drawn next to the elements
  topLeft?: ReactNode;
  topRight?: ReactNode;
  status?: ReactNode; // next to the full screen button, as it is (e.g. the warning sign)
  camera?: { current: Camera | null }; // where the view was: kept here while the editor is away
  autoFocus?: boolean; // take the keyboard when shown
  live?: LiveView; // running in time: wires coloured by voltage, LEDs lit, switches and buttons work
  below?: ReactNode; // an island at the bottom, in the middle (the live simulation's controls)
  full: boolean; // full screen: the board fills the space its parent gives it
  onFull: (full: boolean) => void;
  onSketch?: (id: string) => void; // an Arduino's sketch, opened from its inspector
  bare?: boolean; // no frame of its own: it fills an editor group (the cell's)
  probe?: (target: ProbeTarget, onClose: () => void) => ReactNode; // running: the meter's panel for what it was put on
}

const PANEL = 260; // screen px the element panel takes on the left (with its margin)


/** Where a new element's first pin goes so that its middle lands on ``p`` (on the grid). */
function placedAt(kind: string, p: Point, lib: SymbolLibrary): Point {
  const ps = lib.kinds[kind].pins;
  const mid = (i: 0 | 1) => Math.round(ps.reduce((s, q) => s + q[i], 0) / ps.length / lib.grid);
  return [p[0] - mid(0), p[1] - mid(1)];
}

export function SchematicEditor({
  value, onChange, library, results, topLeft, topRight, status, camera, autoFocus, live, below, full, onFull, onSketch, bare, probe,
}: Props) {
  const { t } = useTranslation("schematic");
  const G = library.grid;
  const gridId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<Tool>({ type: "select" });
  const [selection, setSelection] = useState<Selection>(null);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Point[] | null>(null);
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const [help, setHelp] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  // running, the board has tools of its own: interact (switches, buttons, a potentiometer's slider),
  // the meter (what an element or a wire is doing, its values and charts), the hand
  const [liveTool, setLiveTool] = useState<LiveTool>("interact");
  const [probed, setProbed] = useState<ProbeTarget | null>(null);
  const [spaceHeld, setSpaceHeld] = useState(false);
  // the board is in use (clicked, or full screen): keys and the wheel go to it
  const [active, setActive] = useState(false);
  const { cam, setCam, view, fitted, lost, zoomAround, screenScale } =
    useCamera({ value, library, viewRef, kept: camera, inUse: active || full });
  const { commit, undo, redo } = useHistory(value, onChange);
  const pan = useRef<{ x: number; y: number; cam: Camera; moved: boolean; click: boolean; k: number } | null>(null);
  const focusBoard = () => svgRef.current?.focus({ preventScroll: true });
  // the pointer's last place on screen: when the view moves under a still pointer (the wheel, a
  // drag with space held), what follows it — the wire being drawn, the element to place — follows
  const pointer = useRef<{ clientX: number; clientY: number } | null>(null);
  useEffect(() => {
    if (!pointer.current || !svgRef.current) return;
    const p = toGrid(pointer.current);
    setCursor((c) => (c && same(c, p) ? c : p));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam]);
  // running in time: the board is an instrument, not a drawing — switches, buttons, the
  // potentiometer's slider; what would change the circuit steps aside
  useEffect(() => {
    if (!live) return;
    setTool({ type: "select" });
    setDraft(null);
    held.current = null;
    setGesture(null);
    setLibraryOpen(false);
    setHelp(false);
    setSelection(null);
    setLiveTool("interact");
    setProbed(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!live]);

  useEffect(() => { // eslint-disable-line react-hooks/exhaustive-deps
    if (!autoFocus) return;
    // a frame later: a click that brought the board moves the focus itself when it ends
    const frame = requestAnimationFrame(focusBoard);
    setActive(true); // as if clicked: keys and the wheel go to the board
    return () => cancelAnimationFrame(frame);
  }, []);
  // in the notebook the board is as tall as the drawing needs (fixed after opening, so it never jumps)
  const [boardHeight] = useState(() => {
    const [, y0, , y1] = bounds(value, library);
    return Math.min(640, Math.max(440, (y1 - y0) * G + 240)); // ≥ 440: room for the element panel
  });

  // ------------------------------------------------------------------ changes

  const selectedElement =
    selection?.type === "element" ? value.elements.find((e) => e.id === selection.id) ?? null : null;

  /**
   * Rotate about the element's middle; wires stay where they are. After 90° the pins come
   * off their wires (shown red, reconnect by dragging); after 180° they land back on the
   * same wire ends, swapped — the element is simply reversed (e.g. a source's polarity).
   */
  const rotateSelected = () => {
    if (!selectedElement) return;
    const rotation = (selectedElement.rotation + 90) % 360;
    const at = rotatedAbout(selectedElement, library, rotation);
    commit({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, rotation, at } : e)) });
  };

  const removeSelected = () => {
    if (selection?.type === "element")
      commit({ ...value, elements: value.elements.filter((e) => e.id !== selection.id) });
    if (selection?.type === "wire") commit({ ...value, wires: value.wires.filter((_, i) => i !== selection.index) });
    if (selection?.type === "group") {
      const ids = new Set(selection.ids);
      const wires = new Set(selection.wires);
      commit({ elements: value.elements.filter((e) => !ids.has(e.id)), wires: value.wires.filter((_, i) => !wires.has(i)) });
    }
    setSelection(null);
  };

  const undoStep = () => { if (undo()) setSelection(null); };

  // ------------------------------------------------------------------ pointer

  const toGrid = (event: { clientX: number; clientY: number }): Point => {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svgRef.current!.getScreenCTM()!.inverse());
    return [Math.round(point.x / G), Math.round(point.y / G)];
  };

  /** Wire tool: every click adds a corner; clicking something to connect to ends the wire. */
  const addDraftPoint = (p: Point) => {
    if (!draft) {
      setDraft([p]);
      return;
    }
    const last = draft[draft.length - 1];
    if (same(last, p)) {
      addWire(draft);
      setDraft(null);
      return;
    }
    const path = [...draft, ...elbow(last, p).slice(1)];
    if (isConnectionPoint(value, library, p)) {
      addWire(path);
      setDraft(null);
    } else setDraft(path);
  };

  const addWire = (points: Point[]) => {
    const clean = simplify(points);
    if (clean.length >= 2) commit({ ...value, wires: [...value.wires, { points: clean }] });
  };

  const onCanvasDown = (event: ReactPointerEvent) => {
    svgRef.current?.focus({ preventScroll: true });
    const p = toGrid(event);
    if (tool.type === "place") {
      const element: ElementData = {
        id: nextId(value, tool.kind), kind: tool.kind, at: placedAt(tool.kind, p, library), rotation: 0,
        value: null, text: defaultText(tool.kind),
      };
      commit(attach({ ...value, elements: [...value.elements, element] }, library, element.id));
      setSelection({ type: "element", id: element.id });
      setTool({ type: "select" });
    } else if (tool.type === "wire") addDraftPoint(p);
  };

  /** Drag the view. From empty space in select mode a click without dragging deselects. */
  const startPan = (event: ReactPointerEvent, click: boolean) => {
    svgRef.current?.focus({ preventScroll: true });
    pan.current = { x: event.clientX, y: event.clientY, cam, moved: false, click, k: screenScale() };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onElementDown = (event: ReactPointerEvent, e: ElementData) => {
    if (tool.type !== "select") return;
    if (live) {
      if (liveTool === "hand") return; // the view pans
      if (liveTool === "probe") { // the meter on it
        if (!isComponent(e.kind)) return;
        event.stopPropagation();
        setProbed({ type: "element", id: e.id });
        return;
      }
      // interacting: a button is held down, a switch flips, a potentiometer shows its slider — no menus
      if (!["button", "switch", "potentiometer"].includes(e.kind)) return;
      event.stopPropagation();
      focusBoard();
      if (e.kind === "button") {
        live.onPress(e.id, true);
        const release = () => { live.onPress(e.id, false); window.removeEventListener("pointerup", release); };
        window.addEventListener("pointerup", release);
      } else if (e.kind === "switch") commit(updateElement(value, library, e.id, { text: e.text === "closed" ? null : "closed" }));
      setSelection(e.kind === "potentiometer" ? { type: "element", id: e.id } : null);
      return;
    }
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    if (selection?.type === "group" && selection.ids.includes(e.id))
      begin({ type: "group", ids: selection.ids, wires: selection.wires, start: toGrid(event), snapshot: value, moved: false });
    else {
      setSelection({ type: "element", id: e.id });
      begin({ type: "move", id: e.id, start: toDrawing(event), origin: e.at, snapshot: value, moved: false });
    }
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  function toDrawing(event: { clientX: number; clientY: number }): Point {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svgRef.current!.getScreenCTM()!.inverse());
    return [point.x / G, point.y / G];
  }

  const startBox = (event: ReactPointerEvent) => {
    svgRef.current?.focus({ preventScroll: true });
    const p = toDrawing(event);
    begin({ type: "box", from: p, to: p });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onPinDown = (event: ReactPointerEvent, pin: Point) => {
    if (tool.type !== "select" || live) return; // the wire tool handles pins like any other point
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    begin({ type: "wire", from: pin });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  // The gesture and what it has drawn so far live in refs: pointer moves are rendered later than
  // they come (React gives them a lower priority), so by the time the pointer is let go the last
  // render — its `value`, `cursor`, `gesture` — can be a move or two behind. The end of a drag is
  // taken from here and from the pointerup event itself, never from that render.
  const held = useRef<Gesture | null>(null);
  const drawn = useRef<SchematicData | null>(null); // the drawing as the gesture last left it
  const begin = (g: Gesture) => {
    held.current = g;
    drawn.current = null;
    setGesture(g);
  };
  const emit = (g: Gesture & { moved: boolean }, next: SchematicData) => {
    drawn.current = next;
    g.moved = true;
    onChange(next);
  };

  const onMove = (event: { clientX: number; clientY: number }) => {
    const p = toGrid(event);
    if (!cursor || !same(cursor, p)) setCursor(p);
    const g = held.current;
    if (g?.type === "move") {
      // the element keeps the place it was grabbed by under the pointer: it moves a square once
      // the pointer went half a square, wherever on it the grab was
      const [x, y] = toDrawing(event);
      const at: Point = [g.origin[0] + Math.round(x - g.start[0]), g.origin[1] + Math.round(y - g.start[1])];
      const now = (drawn.current ?? g.snapshot).elements.find((e) => e.id === g.id)!.at;
      if (!same(at, now)) emit(g, updateElement(g.snapshot, library, g.id, { at }));
    }
    if (g?.type === "box") {
      g.to = toDrawing(event);
      setGesture({ ...g });
    }
    if (g?.type === "group") {
      const d: Point = [p[0] - g.start[0], p[1] - g.start[1]];
      if (d[0] || d[1] || g.moved) emit(g, moveGroup(g.snapshot, library, g.ids, g.wires, d));
    }
    if (g?.type === "segment") {
      const w = g.snapshot.wires[g.wire];
      const [a, b] = [w.points[g.index], w.points[g.index + 1]];
      const by = a[1] === b[1] ? p[1] - g.start[1] : p[0] - g.start[0];
      if (by || g.moved) emit(g, { ...g.snapshot, wires: g.snapshot.wires.map((x, i) => (i === g.wire ? moveSegment(x, g.index, by) : x)) });
    }
  };

  const onSegmentDown = (event: ReactPointerEvent, wire: number, index: number) => {
    if (live && liveTool === "probe") { // the meter on the wire: its node's voltage
      event.stopPropagation();
      setProbed({ type: "wire", index: wire });
      return;
    }
    if (tool.type !== "select" || live) return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    setSelection({ type: "wire", index: wire });
    begin({ type: "segment", wire, index, start: toGrid(event), snapshot: value, moved: false });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onUp = (event: { clientX: number; clientY: number }) => {
    onMove(event); // where the pointer was let go is where it ends
    const g = held.current;
    const now = drawn.current;
    held.current = null;
    drawn.current = null;
    setGesture(null);
    if (!g) return;
    if (g.type === "move" && g.moved && now) commit(attach(now, library, g.id), g.snapshot);
    if ((g.type === "segment" || g.type === "group") && g.moved && now) commit(now, g.snapshot);
    if (g.type === "box") {
      const { ids, wires } = inBox(value, library, g.from, g.to);
      setSelection(ids.length + wires.length === 0 ? null
        : ids.length === 1 && !wires.length ? { type: "element", id: ids[0] }
        : { type: "group", ids, wires });
    }
    const end = toGrid(event);
    if (g.type === "wire" && !same(end, g.from)) addWire(elbow(g.from, end));
  };

  // ------------------------------------------------------------------ keyboard

  const onKey = (event: KeyboardEvent) => {
    const mod = event.metaKey || event.ctrlKey;
    const plain = (k: string) => !mod && event.key.toLowerCase() === k;
    if (live) { // running: the live tools and the view — the drawing's tools are away
      if (event.key === "Escape" && probed) setProbed(null);
      else if (event.key === "Escape" && selection) setSelection(null);
      else if (plain("v")) setLiveTool("interact");
      else if (plain("m")) setLiveTool("probe");
      else if (plain("h")) setLiveTool("hand");
      else if (event.key === "Escape" && full) onFull(false);
      else if (plain("f")) onFull(!full);
      else return;
      event.preventDefault();
      return;
    }
    if (mod && event.key.toLowerCase() === "z") (event.shiftKey ? redo : undoStep)();
    else if (mod && event.key.toLowerCase() === "y") redo();
    else if (event.key === "Escape") {
      // one step back at a time: the wire being drawn, the tool / selection, the panel, full screen
      if (draft) setDraft(null);
      else if (tool.type !== "select" || selection) {
        setTool({ type: "select" });
        setSelection(null);
      } else if (libraryOpen) setLibraryOpen(false);
      else if (full) onFull(false);
    } else if (event.key === "Enter" && draft) {
      addWire(draft);
      setDraft(null);
    } else if (plain("r")) rotateSelected();
    else if (plain("v")) { setTool({ type: "select" }); setDraft(null); }
    else if (plain("h")) { setTool({ type: "hand" }); setDraft(null); }
    else if (plain("w")) setTool({ type: "wire" });
    else if (/^[0-9]$/.test(event.key) && !mod) {
      const k = KINDS[(Number(event.key) + 9) % 10];
      if (k) choose(k.kind);
    }
    else if (plain("k")) (libraryOpen ? setLibraryOpen(false) : openLibrary());
    else if (event.key === "/" && !mod) openLibrary();
    else if (plain("f")) onFull(!full);
    else if (event.key === "Delete" || event.key === "Backspace") removeSelected();
    else return;
    event.preventDefault();
  };

  /** Pick an element to place (the side panel stays open, like Excalidraw's). */
  function choose(kind: string) {
    setTool({ type: "place", kind });
    setDraft(null);
    focusBoard();
  }

  function openLibrary() {
    setLibraryOpen(true);
    // the panel floats over the left of the board: move the drawing out from under it
    if (!value.elements.length && !value.wires.length) return;
    const left = (bounds(value, library)[0] * G - 60 - cam.x) * cam.zoom; // - room for labels
    if (left < PANEL) setCam((c) => ({ ...c, x: c.x - (PANEL - left) / c.zoom }));
  }

  // ------------------------------------------------------------------ what to draw

  const wiring = draft !== null || gesture?.type === "wire";
  const preview: Point[] | null =
    cursor && draft ? [...draft, ...elbow(draft[draft.length - 1], cursor).slice(1)]
    : cursor && gesture?.type === "wire" ? elbow(gesture.from, cursor)
    : null;
  const snap = wiring && cursor && isConnectionPoint(value, library, cursor) ? cursor : null;
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");
  // running: a junction's dot takes the colour of the wires meeting there
  const dotVoltage = (p: Point) => {
    if (!live) return null;
    const i = value.wires.findIndex((w) => w.points.some((q) => same(q, p)));
    return i < 0 ? null : live.wires[i] ?? null;
  };
  const selectedKind = selectedElement?.kind;

  const panel = libraryOpen && !live && (
    <LibraryPanel library={library} chosen={tool.type === "place" ? tool.kind : undefined} onChoose={choose}
                  onClose={(backToBoard) => { setLibraryOpen(false); if (backToBoard) focusBoard(); }} />
  );

  const boardView = (
    <div
      data-board data-full={full || undefined}
      className={bare ? "group/board relative overflow-hidden bg-board h-full" : cn(board, "h-120", active && "border-accent")}
      // with a bar laid over its top edge: as much board as without one, its islands below the bar
      style={bare ? undefined : { height: boardHeight }}
      onPointerDownCapture={() => setActive(true)}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setActive(false); }}
    >
      <div className="absolute inset-0 overflow-hidden" ref={viewRef}>
        <svg
          ref={svgRef}
          className={cn("canvas", `tool-${tool.type}`, wiring && "wiring", (spaceHeld || tool.type === "hand" || (live && liveTool === "hand")) && "panning",
                            live && "running", live && liveTool === "probe" && "probing")}
          viewBox={`${cam.x} ${cam.y} ${view.w / cam.zoom} ${view.h / cam.zoom}`}
          width="100%"
          height="100%"
          tabIndex={0}
          onPointerDown={(event) => {
            if (spaceHeld || tool.type === "hand" || (live && liveTool === "hand") || event.button === 1) startPan(event, false);
            else if (tool.type === "select" && event.shiftKey) startBox(event); // shift + drag: select many
            else if (tool.type === "select") startPan(event, true); // empty space: drag pans, click deselects
            else onCanvasDown(event);
          }}
          onPointerMove={(event) => {
            pointer.current = { clientX: event.clientX, clientY: event.clientY };
            const p = pan.current;
            if (p) {
              const [dx, dy] = [event.clientX - p.x, event.clientY - p.y];
              if (Math.abs(dx) + Math.abs(dy) > 3) p.moved = true;
              // the drawing follows the pointer exactly (screen px → board px → drawing px)
              if (p.moved) setCam({ ...p.cam, x: p.cam.x - dx / p.k / p.cam.zoom, y: p.cam.y - dy / p.k / p.cam.zoom });
              return;
            }
            onMove(event);
          }}
          onPointerUp={(event) => {
            const p = pan.current;
            if (p) {
              if (p.click && !p.moved) setSelection(null);
              pan.current = null;
              return;
            }
            onUp(event);
          }}
          onPointerLeave={() => { pointer.current = null; setCursor(null); }}
          onDoubleClick={() => { if (draft) { addWire(draft); setDraft(null); } }}
          onKeyDown={(event) => {
            if (event.key === " ") { setSpaceHeld(true); event.preventDefault(); return; }
            onKey(event);
          }}
          onKeyUp={(event) => { if (event.key === " ") setSpaceHeld(false); }}
        >
          <style>{library.style}</style>
          <defs>
            <pattern id={gridId} width={G} height={G} patternUnits="userSpaceOnUse" x={-G / 2} y={-G / 2}>
              <circle cx={G / 2} cy={G / 2} r="1" className="grid-dot" />
            </pattern>
          </defs>
          {/* the grid covers exactly what the camera sees, so it never ends */}
          <rect className="grid" x={cam.x} y={cam.y} width={view.w / cam.zoom} height={view.h / cam.zoom}
                fill={`url(#${CSS.escape(gridId)})`} />

          {value.wires.map((w, i) => (
            <g key={i}>
              <polyline className={`w wire ${(selection?.type === "wire" && selection.index === i) || (probed?.type === "wire" && probed.index === i)
                || (selection?.type === "group" && selection.wires.includes(i)) ? "selected" : ""}`}
                        style={live ? { stroke: liveColor(live.wires[i] ?? null, live.scale) } : undefined}
                        points={pointsOf(w.points)} />
              {w.points.slice(1).map((q, j) => (
                <polyline
                  key={j}
                  className={`hit ${w.points[j][1] === q[1] ? "segment-h" : "segment-v"}`}
                  points={pointsOf([w.points[j], q])}
                  onPointerDown={(event) => onSegmentDown(event, i, j)}
                >
                  <title>{t("drawing.moveSegment")}</title>
                </polyline>
              ))}
            </g>
          ))}
          {junctions(value, library).map(([x, y]) => (
            <circle key={`j${x},${y}`} className="dot" cx={x * G} cy={y * G} r="3"
                    style={live ? { fill: liveColor(dotVoltage([x, y]), live.scale) } : undefined} />
          ))}
          {live && value.elements.filter((e) => e.kind === "led" && (live.leds[e.id] ?? 0) > 0.01).map((e) => {
            const [a, b] = pins(e, library);
            return (
              <circle key={`glow${e.id}`} className="led-glow" cx={(a[0] + b[0]) / 2 * G} cy={(a[1] + b[1]) / 2 * G} r={22}
                      style={{ fill: ledColor(e.text), opacity: 0.15 + 0.75 * Math.sqrt(live.leds[e.id]) }} />
            );
          })}
          {value.elements.map((e) => (
            <ElementView key={e.id} element={e} library={library} wires={value.wires} result={results?.[e.id]}
                         closed={e.kind === "switch" ? e.text === "closed" : e.kind === "button" ? !!live?.pressed.includes(e.id) : false}
                         lit={live && e.kind === "led" ? live.leds[e.id] ?? 0 : undefined}
                         live={live && { pins: live.pins[e.id] ?? [], scale: live.scale }}
                         selected={(selection?.type === "element" && selection.id === e.id) || (probed?.type === "element" && probed.id === e.id)
                           || (selection?.type === "group" && selection.ids.includes(e.id))}
                         onPointerDown={(event) => onElementDown(event, e)} />
          ))}
          {openPins(value, library).map(([x, y]) => (
            <circle key={`o${x},${y}`} className="open-pin" cx={x * G} cy={y * G} r="3.5">
              <title>{t("drawing.openPin")}</title>
            </circle>
          ))}
          {value.elements.filter((e) => isComponent(e.kind)).flatMap((e) =>
            pins(e, library).map(([x, y], i) => (
              <circle key={`p${e.id}${i}`} className="pin-handle" cx={x * G} cy={y * G} r="8"
                      onPointerDown={(event) => onPinDown(event, [x, y])}>
                <title>{t("drawing.drawWire")}</title>
              </circle>
            )),
          )}
          {preview && <polyline className="w draft" points={pointsOf(preview)} />}
          {gesture?.type === "box" && (
            <rect className="rubber-band"
                  x={Math.min(gesture.from[0], gesture.to[0]) * G} y={Math.min(gesture.from[1], gesture.to[1]) * G}
                  width={Math.abs(gesture.to[0] - gesture.from[0]) * G} height={Math.abs(gesture.to[1] - gesture.from[1]) * G} />
          )}
          {snap && <circle className="snap" cx={snap[0] * G} cy={snap[1] * G} r="7" />}
          {tool.type === "place" && cursor && (
            <g className="w ghost" transform={`translate(${placedAt(tool.kind, cursor, library).map((c) => c * G).join(" ")})`}
               dangerouslySetInnerHTML={{ __html: library.kinds[tool.kind].svg }} />
          )}
        </svg>
      </div>

      {topLeft && <BoardIsland className="top-[calc(var(--board-top,0px)+0.75rem)] left-3 p-1">{topLeft}</BoardIsland>}
      {live ? (
        <LiveToolbar current={liveTool} onTool={(next) => { setLiveTool(next); if (next !== "probe") setProbed(null); focusBoard(); }} />
      ) : (
        <Toolbar current={tool} libraryOpen={libraryOpen} library={library}
                 onTool={(next) => { setTool(next); setDraft(null); focusBoard(); }}
                 onLibrary={() => (libraryOpen ? setLibraryOpen(false) : openLibrary())} />
      )}
      {live && probed && probe?.(probed, () => setProbed(null))}
      {panel}
      {topRight && <BoardIsland className="top-[calc(var(--board-top,0px)+0.75rem)] right-3">{topRight}</BoardIsland>}
      {(live ? selectedKind === "potentiometer" && !probed
        : selectedElement || selection?.type === "wire" || selection?.type === "group") && (
        <Inspector
          key={selectedElement?.id ?? selection?.type ?? "none"}
          selection={selection}
          element={selectedElement}
          live={!!live}
          onSketch={onSketch && selectedElement ? () => onSketch(selectedElement.id) : undefined}
          taken={value.elements.map((e) => e.id)}
          onChange={(patch) => selectedElement && commit(updateElement(value, library, selectedElement.id, patch))}
          onRename={(id) => {
            if (!selectedElement) return;
            commit({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, id } : e)) });
            setSelection({ type: "element", id });
          }}
          onRotate={rotateSelected}
          onRemove={removeSelected}
          icon={selectedElement ? <SymbolIcon kind={selectedElement.kind} library={library} /> : null}
        />
      )}
      {lost && (
        // the drawing is out of view: a way back, bottom centre (like Excalidraw's "scroll back to content")
        <button className={cn(boardIsland(), below ? "bottom-17" : "bottom-3", // above the simulation's controls
                              "left-1/2 -translate-x-1/2 gap-2 px-3.5 py-2 border border-transparent text-[14px] font-medium text-fg hover:bg-selected")}
                onClick={() => setCam(fitted())}>
          <Target /> {t("view.back")}
        </button>
      )}
      {below && <BoardIsland stays className="bottom-3 left-1/2 -translate-x-1/2">{below}</BoardIsland>}
      <ZoomAndHistory zoom={cam.zoom} onZoom={(f) => zoomAround(f)} onFit={() => setCam(fitted())} onUndo={undoStep} onRedo={redo}
                      history={!live} />
      {/* bottom right: what is wrong with the circuit (always shown, a sign of its own), then full screen */}
      <div className="absolute bottom-3 right-3 z-3 flex items-end gap-1.5">
        {status}
        <ScreenAndHelp className="static" full={full} onFull={() => onFull(!full)} onHelp={() => setHelp((h) => !h)} help={!live} screen={!bare} />
      </div>
      {help && !live && <HelpPanel />}
    </div>
  );
  return boardView;
}
