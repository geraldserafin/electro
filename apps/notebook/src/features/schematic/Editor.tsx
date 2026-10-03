// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
//
// The drawing lives on an endless plane; the board shows it through a camera (useCamera), like
// Excalidraw. Here: the state of the drawing being edited, the pointer and the keyboard; the
// islands around it are components of their own.
import {
  type KeyboardEvent,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/shared/lib/cn";
import type { ElementData, ElementResult, Point, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { More, Rotate, Target, Trash } from "@/shared/ui/icons";
import { isAdjustable } from "./Adjusters";
import { BoardButton, BoardIsland, board, boardIsland, islandButton } from "./Board";
import { CurrentDots } from "./CurrentDots";
import { ElementView, liveColor } from "./ElementView";
import { flowGraph, type Segment, segmentCurrents } from "./flow";
import { HelpPanel } from "./HelpPanel";
import { Inspector, type Selection } from "./Inspector";
import { LcdScreen, type LcdScreenData } from "./LcdScreen";
import { LibraryPanel, type MyPart } from "./LibraryPanel";
import {
  attach,
  bounds,
  defaultText,
  defaultValue,
  elbow,
  inBox,
  inTheWay,
  isComponent,
  isConnectionPoint,
  junctions,
  KINDS,
  key,
  keyName,
  ledColor,
  moveGroup,
  moveSegment,
  nextId,
  openPins,
  pins,
  rotatedAbout,
  same,
  simplify,
  updateElement,
} from "./model";
import { OledScreen, type OledScreenData } from "./OledScreen";
import { partKind, usedParts, withParts } from "./parts";
import { TftScreen, type TftScreenData } from "./TftScreen";
import { type LiveTool, LiveToolbar, type Tool, Toolbar } from "./Toolbar";
import { type Camera, useCamera } from "./useCamera";
import { useHistory } from "./useHistory";
import { ScreenAndHelp, ZoomAndHistory } from "./ViewControls";
import "./Canvas.css";

type Gesture =
  | { type: "move"; id: string; start: Point; origin: Point; snapshot: SchematicData; moved: boolean } // start: not rounded
  | { type: "wire"; from: Point; tap: { wire: number } | { id: string } } // tap: let go where it started, that is selected
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
  looks: Record<string, Record<string, number>>; // what else each element shows (useLive's LiveFrame.looks)
  screens: Record<string, LcdScreenData>; // what each LCD shows
  oleds: Record<string, OledScreenData>; // what each OLED shows
  tfts: Record<string, TftScreenData>; // what each colour TFT shows
  pressed: string[]; // buttons held down
  currents?: Record<string, number[]>; // each element's terminals' currents (into it): the moving dots
  nodes?: { wires: (string | null)[]; pins: Record<string, (string | null)[]> }; // which node each wire and pin is
  paused?: boolean; // the dots stand still
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
  corner?: ReactNode; // an island of the cell's own in the bottom right corner (a phone: what is wrong, …)
  phone?: boolean; // the selection's own buttons in that corner (turn it, away with it, its panel), not over the board
  viewOnly?: boolean; // looked at, not edited: no tools, nothing moves (while it runs, its buttons still work)
  camera?: { current: Camera | null }; // where the view was: kept here while the editor is away
  autoFocus?: boolean; // take the keyboard when shown
  live?: LiveView; // running in time: wires coloured by voltage, LEDs lit, switches and buttons work
  below?: ReactNode; // an island at the bottom, in the middle (the live simulation's controls)
  full: boolean; // full screen: the board fills the space its parent gives it
  onFull: (full: boolean) => void;
  bare?: boolean; // no frame of its own: it fills an editor group (the cell's)
  probe?: (target: ProbeTarget, onClose: () => void) => ReactNode; // running: the meter's panel for what it was put on
  // the user's own components, offered first in the element library (features/components)
  myParts?: { list: MyPart[]; label: string; removeLabel: string; onRemove: (part: MyPart) => void };
}

const PANEL = 260; // screen px the element panel takes on the left (with its margin)

/** What is selected, as elements and wires (one of them alone too). */
const picked = (s: Selection): { ids: string[]; wires: number[] } =>
  s?.type === "element"
    ? { ids: [s.id], wires: [] }
    : s?.type === "wire"
      ? { ids: [], wires: [s.index] }
      : s?.type === "group"
        ? { ids: s.ids, wires: s.wires }
        : { ids: [], wires: [] };
const selectionOf = (ids: string[], wires: number[]): Selection =>
  ids.length + wires.length === 0
    ? null
    : ids.length === 1 && !wires.length
      ? { type: "element", id: ids[0] }
      : !ids.length && wires.length === 1
        ? { type: "wire", index: wires[0] }
        : { type: "group", ids, wires };
/** Shift + click: in the selection, or out of it again. */
const toggled = (s: Selection, item: { id: string } | { wire: number }): Selection => {
  const { ids, wires } = picked(s);
  if ("id" in item)
    return selectionOf(ids.includes(item.id) ? ids.filter((x) => x !== item.id) : [...ids, item.id], wires);
  return selectionOf(ids, wires.includes(item.wire) ? wires.filter((x) => x !== item.wire) : [...wires, item.wire]);
};

// Ctrl/⌘ C: what was copied, shared by every board on the page (from one cell into another too)
let clipboard: SchematicData | null = null;

/** Where a new element's first pin goes so that its middle lands on ``p`` (on the grid). */
function placedAt(kind: string, p: Point, lib: SymbolLibrary): Point {
  const ps = lib.kinds[kind]?.pins ?? [[0, 0]];
  const mid = (i: 0 | 1) => Math.round(ps.reduce((s, q) => s + q[i], 0) / ps.length / lib.grid);
  return [p[0] - mid(0), p[1] - mid(1)];
}

export function SchematicEditor({
  value,
  onChange,
  library: symbols,
  results,
  topLeft,
  topRight,
  status,
  corner,
  phone = false,
  viewOnly = false,
  camera,
  autoFocus,
  live,
  below,
  full,
  onFull,
  bare,
  probe,
  myParts,
}: Props) {
  const { t } = useTranslation("schematic");
  const library = withParts(symbols, value.parts); // one's own components: kinds of their own ("part:<key>")
  const G = library.grid;
  const gridId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const viewRef = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<Tool>({ type: "hand" }); // (the hand: the view moves, the drawing is at hand)
  // what the element being placed is drawn from (one's own component, not on the drawing yet: with it)
  const placing =
    tool.type === "place" && tool.part
      ? withParts(symbols, { ...value.parts, [tool.part.key]: tool.part.def })
      : library;
  const [selection, setSelection] = useState<Selection>(null);
  const [cursor, setCursor] = useState<Point | null>(null);
  // a tap selects (a finger: the element's panel only from its ⋯, not over the board at once)
  const [inspect, setInspect] = useState(true);
  const [locked, setLocked] = useState(false); // the tool stays (the lock): an element placed again and again
  // the segment of a wire (not selected) under the pointer: a wire starts from it — its point shown
  const [over, setOver] = useState<{ wire: number; index: number } | null>(null);
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
  // (a touch screen does not always move the focus off it: a tap elsewhere leaves it too)
  useEffect(() => {
    if (!active) return;
    const away = (event: PointerEvent) => {
      if (!viewRef.current?.parentElement?.contains(event.target as Node)) setActive(false);
    };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, [active]);
  const { cam, setCam, view, fitted, lost, zoomAround, screenScale } = useCamera({
    value,
    library,
    viewRef,
    kept: camera,
    inUse: active || full,
    full,
    // (an element selected: two fingers turning it turn it, a quarter at a time)
    onTwist: (dir) => !live && !viewOnly && rotateSelected(dir),
    // (two fingers: the drawing as it was before the first one touched it — no drag, no wire, no box)
    onPinch: () => {
      const g = held.current;
      held.current = null;
      setGesture(null);
      if (g && "snapshot" in g && g.moved) onChange(g.snapshot);
      pan.current = null;
    },
  });
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
  // only looked at now (a phone, out of full screen): what was picked, let go
  useEffect(() => {
    if (!viewOnly) return;
    setSelection(null);
    setTool({ type: "hand" });
    setLibraryOpen(false);
  }, [viewOnly]);
  // running in time: the board is an instrument, not a drawing — switches, buttons, the
  // potentiometer's slider; what would change the circuit steps aside
  useEffect(() => {
    if (!live) return;
    setTool({ type: "hand" });
    held.current = null;
    setGesture(null);
    setLibraryOpen(false);
    setHelp(false);
    setSelection(null);
    setLiveTool("interact");
    setProbed(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!live]);

  useEffect(() => {
    // eslint-disable-line react-hooks/exhaustive-deps
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
    selection?.type === "element" ? (value.elements.find((e) => e.id === selection.id) ?? null) : null;

  /**
   * Rotate about the element's middle; wires stay where they are. After 90° the pins come
   * off their wires (shown red, reconnect by dragging); after 180° they land back on the
   * same wire ends, swapped — the element is simply reversed (e.g. a source's polarity).
   */
  /** A quarter turn, clockwise (or back, ``-1``). */
  const rotateSelected = (dir: 1 | -1 = 1) => {
    if (!selectedElement) return;
    const rotation = (selectedElement.rotation + 360 + 90 * dir) % 360;
    const at = rotatedAbout(selectedElement, library, rotation);
    commit({
      ...value,
      elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, rotation, at } : e)),
    });
  };

  const removeSelected = () => {
    const { ids, wires } = picked(selection);
    if (ids.length + wires.length) {
      const elements = value.elements.filter((e) => !ids.includes(e.id));
      commit({
        elements,
        wires: value.wires.filter((_, i) => !wires.includes(i)),
        parts: usedParts({ ...value, elements }),
      });
    }
    setSelection(null);
  };

  const copySelected = () => {
    const { ids, wires } = picked(selection);
    if (!ids.length && !wires.length) return false;
    const elements = value.elements.filter((e) => ids.includes(e.id));
    clipboard = { elements, wires: wires.map((i) => value.wires[i]), parts: usedParts({ ...value, elements }) };
    return true;
  };

  /** What was copied, its middle under the pointer (off the board: a little beside where it was); new names, selected. */
  const paste = () => {
    if (!clipboard) return;
    const [x0, y0, x1, y1] = bounds(clipboard, library);
    const d: Point = cursor ? [cursor[0] - Math.round((x0 + x1) / 2), cursor[1] - Math.round((y0 + y1) / 2)] : [2, 2];
    const shift = ([x, y]: Point): Point => [x + d[0], y + d[1]];
    let next = clipboard.parts ? { ...value, parts: { ...value.parts, ...clipboard.parts } } : value;
    const ids: string[] = [];
    for (const e of clipboard.elements) {
      const id = nextId(next, e.kind, e.kind === "part" ? next.parts?.[e.text ?? ""]?.prefix : undefined);
      ids.push(id);
      next = { ...next, elements: [...next.elements, { ...e, id, at: shift(e.at) }] };
    }
    const wires = clipboard.wires.map((_, i) => next.wires.length + i);
    commit({ ...next, wires: [...next.wires, ...clipboard.wires.map((w) => ({ points: w.points.map(shift) }))] });
    setTool({ type: "hand" });
    setSelection(selectionOf(ids, wires));
  };

  const undoStep = () => {
    if (undo()) setSelection(null);
  };

  // ------------------------------------------------------------------ pointer

  const toGrid = (event: { clientX: number; clientY: number }): Point => {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svgRef.current!.getScreenCTM()!.inverse());
    return [Math.round(point.x / G), Math.round(point.y / G)];
  };

  /** A wire's way from a pin (or a wire) to ``b``: out of a pin along its element first (up from a
   *  source's top, not sideways into its body's way). */
  const wireTo = (g: Extract<Gesture, { type: "wire" }>, b: Point): Point[] => {
    const a = g.from;
    const tap = g.tap;
    const e = "id" in tap ? value.elements.find((x) => x.id === tap.id) : undefined;
    const ps = e ? pins(e, library) : [];
    const upright = ps.length === 2 && ps[0]![0] === ps[1]![0];
    return upright && a[0] !== b[0] && a[1] !== b[1] ? [a, [a[0], b[1]], b] : elbow(a, b);
  };

  const addWire = (points: Point[]) => {
    const clean = simplify(points);
    if (clean.length >= 2) commit({ ...value, wires: [...value.wires, { points: clean }] });
  };

  const onCanvasDown = (event: ReactPointerEvent) => {
    svgRef.current?.focus({ preventScroll: true });
    const p = toGrid(event);
    if (tool.type === "place") {
      // one's own component: its definition comes onto the drawing with it
      const part = tool.part;
      const next = part ? { ...value, parts: { ...value.parts, [part.key]: part.def } } : value;
      const element: ElementData = part
        ? {
            id: nextId(next, "part", part.def.prefix ?? "U"),
            kind: "part",
            at: placedAt(tool.kind, p, placing),
            rotation: 0,
            value: null,
            text: part.key,
          }
        : {
            id: nextId(value, tool.kind),
            kind: tool.kind,
            at: placedAt(tool.kind, p, library),
            rotation: 0,
            value: defaultValue(tool.kind),
            text: defaultText(tool.kind),
          };
      // right on one that is there (the same pins): that one, picked — not another over it
      const lib = withParts(symbols, next.parts);
      const there = value.elements.find((e) => {
        const [a, b] = [pins(e, lib).map(key).sort(), pins(element, lib).map(key).sort()];
        return a.length === b.length && a.every((k, i) => k === b[i]);
      });
      if (there) {
        setSelection({ type: "element", id: there.id });
        setInspect(event.pointerType !== "touch");
        return;
      }
      commit(attach({ ...next, elements: [...next.elements, element] }, lib, element.id));
      // once, then the hand (the lock shut: another one where the next click is)
      if (!locked) setTool({ type: "hand" });
      setSelection({ type: "element", id: element.id });
      setInspect(event.pointerType !== "touch");
    }
  };

  /** Drag the view. From empty space in select mode a click without dragging deselects. */
  const startPan = (event: ReactPointerEvent, click: boolean) => {
    svgRef.current?.focus({ preventScroll: true });
    pan.current = { x: event.clientX, y: event.clientY, cam, moved: false, click, k: screenScale() };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  // the elements get one handler for the whole life of the board (it calls the latest onElementDown),
  // so an element whose look did not change is not drawn again (ElementView is memo)
  const elementDown = useRef<(event: ReactPointerEvent, e: ElementData) => void>(() => {});
  const onElementDownStable = useCallback(
    (event: ReactPointerEvent, e: ElementData) => elementDown.current(event, e),
    [],
  );
  // a finger on a board not yet tapped: it may be scrolling the page — nothing moves, nothing is wired
  const untapped = (event: ReactPointerEvent) => event.pointerType === "touch" && !active && !full;
  /** The hand or the arrow: the drawing at hand (elements moved, wires drawn from pins). */
  const drawingTool = tool.type === "hand" || tool.type === "select";
  const onElementDown = (event: ReactPointerEvent, e: ElementData) => {
    if (!drawingTool) return;
    if (live) {
      if (liveTool === "hand") return; // the view pans
      if (liveTool === "probe") {
        // the meter on it
        if (!isComponent(e.kind)) return;
        event.stopPropagation();
        setProbed({ type: "element", id: e.id });
        return;
      }
      // interacting: a button is held down, a switch flips, a potentiometer or a sensor shows its slider — no menus
      if (!["button", "switch"].includes(e.kind) && !isAdjustable(e.kind)) return;
      event.stopPropagation();
      focusBoard();
      if (e.kind === "button") {
        live.onPress(e.id, true);
        const release = () => {
          live.onPress(e.id, false);
          window.removeEventListener("pointerup", release);
        };
        window.addEventListener("pointerup", release);
      } else if (e.kind === "switch")
        commit(updateElement(value, library, e.id, { text: e.text === "closed" ? null : "closed" }));
      setSelection(isAdjustable(e.kind) ? { type: "element", id: e.id } : null);
      return;
    }
    if (viewOnly || untapped(event)) return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    if (event.shiftKey) {
      setSelection(toggled(selection, { id: e.id }));
      return;
    }
    if (selection?.type === "group" && selection.ids.includes(e.id))
      begin({
        type: "group",
        ids: selection.ids,
        wires: selection.wires,
        start: toGrid(event),
        snapshot: value,
        moved: false,
      });
    else {
      // a finger only picks it (its panel from its own buttons' ⋯)
      setInspect(event.pointerType !== "touch");
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

  const onPinDown = (event: ReactPointerEvent, pin: Point, e: ElementData) => {
    if (!drawingTool || live || viewOnly || untapped(event)) return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    begin({ type: "wire", from: pin, tap: { id: e.id } });
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
      if (by || g.moved)
        emit(g, {
          ...g.snapshot,
          wires: g.snapshot.wires.map((x, i) => (i === g.wire ? moveSegment(x, g.index, by) : x)),
        });
    }
  };

  const onSegmentDown = (event: ReactPointerEvent, wire: number, index: number) => {
    if (live && liveTool === "probe") {
      // the meter on the wire: its node's voltage
      event.stopPropagation();
      setProbed({ type: "wire", index: wire });
      return;
    }
    if (!drawingTool || live || viewOnly || untapped(event)) return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    if (event.shiftKey) {
      setSelection(toggled(selection, { wire }));
      return;
    }
    // not selected: a new wire from this point of it (let go where it was: the wire is selected)
    const chosen = picked(selection).wires.includes(wire);
    if (!chosen) {
      begin({ type: "wire", from: toGrid(event), tap: { wire } });
      svgRef.current?.setPointerCapture(event.pointerId);
      return;
    }
    // a wire of the selection: all of it moves; otherwise the segment, sideways
    if (selection?.type === "group" && selection.wires.includes(wire))
      begin({
        type: "group",
        ids: selection.ids,
        wires: selection.wires,
        start: toGrid(event),
        snapshot: value,
        moved: false,
      });
    else {
      setSelection({ type: "wire", index: wire });
      begin({ type: "segment", wire, index, start: toGrid(event), snapshot: value, moved: false });
    }
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onUp = (event: { clientX: number; clientY: number; pointerType?: string }) => {
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
      // added to what was selected (shift is held for it)
      const box = inBox(value, library, g.from, g.to);
      const had = picked(selection);
      setSelection(selectionOf([...new Set([...had.ids, ...box.ids])], [...new Set([...had.wires, ...box.wires])]));
    }
    // a wire: from something to something (a pin, a wire) — let go on nothing, there is none
    const end = toGrid(event);
    if (g.type === "wire" && !same(end, g.from) && isConnectionPoint(value, library, end)) addWire(wireTo(g, end));
    // a tap: what it was on, selected (an element as a tap on it)
    if (g.type === "wire" && same(end, g.from)) {
      const tap = g.tap;
      if ("wire" in tap) setSelection({ type: "wire", index: tap.wire });
      else {
        setInspect(event.pointerType !== "touch");
        setSelection({ type: "element", id: tap.id });
      }
    }
  };

  // ------------------------------------------------------------------ keyboard

  // running: a button with a key (its text) is held while the key is — several at once, as a game wants
  const heldKeys = useRef(new Set<string>());
  const pressKey = (event: KeyboardEvent, down: boolean): boolean => {
    const name = keyName(event.key);
    const bound = value.elements.filter((e) => e.kind === "button" && e.text === name);
    if (!bound.length || !live) return false;
    event.preventDefault();
    if (event.repeat) return true;
    for (const e of bound) {
      if (down) heldKeys.current.add(e.id);
      else heldKeys.current.delete(e.id);
      live.onPress(e.id, down);
    }
    return true;
  };

  const onKey = (event: KeyboardEvent) => {
    const mod = event.metaKey || event.ctrlKey;
    const plain = (k: string) => !mod && event.key.toLowerCase() === k;
    if (live) {
      // running: the live tools and the view — the drawing's tools are away
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
    else if (mod && event.key.toLowerCase() === "c") copySelected();
    else if (mod && event.key.toLowerCase() === "x") {
      if (copySelected()) removeSelected();
    } else if (mod && event.key.toLowerCase() === "v") paste();
    else if (event.key === "Escape") {
      // one step back at a time: the tool / selection, the panel, full screen
      if (tool.type !== "hand" || selection) {
        setTool({ type: "hand" });
        setSelection(null);
      } else if (libraryOpen) setLibraryOpen(false);
      else if (full) onFull(false);
    } else if (plain("r")) rotateSelected();
    else if (plain("v")) setTool({ type: "select" });
    else if (plain("h")) setTool({ type: "hand" });
    else if (plain("q")) setLocked((l) => !l);
    else if (/^[0-9]$/.test(event.key) && !mod) {
      const k = KINDS[(Number(event.key) + 9) % 10];
      if (k) choose(k.kind);
    } else if (plain("k")) libraryOpen ? setLibraryOpen(false) : openLibrary();
    else if (event.key === "/" && !mod) openLibrary();
    else if (plain("f")) onFull(!full);
    else if (event.key === "Delete" || event.key === "Backspace") removeSelected();
    else return;
    event.preventDefault();
  };

  /** Pick an element to place, as many times as clicked (the side panel stays open, like Excalidraw's —
   *  a phone's: out of the board's way). */
  function choose(kind: string) {
    setTool({ type: "place", kind });
    if (matchMedia("(pointer: coarse)").matches) setLibraryOpen(false);
    focusBoard();
  }

  function openLibrary() {
    setLibraryOpen(true);
    // the panel floats over the left of the board: move the drawing out from under it (a phone's is a
    // sheet from the bottom: nothing to move)
    if (!value.elements.length && !value.wires.length) return;
    if (matchMedia("(max-width: 639px)").matches) return;
    const left = (bounds(value, library)[0] * G - 60 - cam.x) * cam.zoom; // - room for labels
    if (left < PANEL) setCam((c) => ({ ...c, x: c.x - (PANEL - left) / c.zoom }));
  }

  // ------------------------------------------------------------------ what to draw

  elementDown.current = onElementDown;
  // (the same drawing: the same dots; while it runs, the board is drawn 30 times a second)
  const junctionPoints = useMemo(() => junctions(value, library), [value, library]);
  const obstacles = useMemo(() => inTheWay(value), [value]); // (what labels keep off)
  const openPinPoints = useMemo(() => openPins(value, library), [value, library]);
  const wiring = gesture?.type === "wire";
  const preview: Point[] | null = cursor && gesture?.type === "wire" ? wireTo(gesture, cursor) : null;
  const snap = wiring && cursor && isConnectionPoint(value, library, cursor) ? cursor : null;
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");
  // running: a junction's dot takes the colour of the wires meeting there
  const dotVoltage = (p: Point) => {
    if (!live) return null;
    const i = value.wires.findIndex((w) => w.points.some((q) => same(q, p)));
    return i < 0 ? null : (live.wires[i] ?? null);
  };
  // running: the wires' network, once for the drawing (the currents along it, each frame), and the
  // two-pin elements the current goes through
  const known = live?.currents;
  const flow = useMemo(
    () => (live?.nodes && known ? flowGraph(value, library, live.nodes, (id) => !!known[id]) : null),
    // (the elements whose currents are known stay the same while it runs: not each frame's)
    [value, library, live?.nodes, !!known],
  );
  const through = useMemo(
    () =>
      flow
        ? value.elements.flatMap((e) => {
            const ps = pins(e, library);
            if (ps.length !== 2 || !known?.[e.id]) return [];
            const [a, b] = ps.map(([x, y]) => [x * G, y * G] as Point);
            return [{ id: e.id, a, b }];
          })
        : [],
    [flow],
  );
  const dotted = useMemo<Segment[]>(() => (flow ? [...flow.segments, ...through] : []), [flow, through]);
  const dottedCurrents =
    flow && known ? [...segmentCurrents(flow, known), ...through.map((e) => known[e.id]?.[0] ?? 0)] : [];
  const selectedKind = selectedElement?.kind;
  // many selected: one dashed frame around all of it, besides each thing's own
  const groupFrame =
    selection?.type === "group"
      ? bounds(
          {
            elements: value.elements.filter((e) => selection.ids.includes(e.id)),
            wires: selection.wires.map((i) => value.wires[i]).filter(Boolean),
          },
          library,
        )
      : null;

  const panel = libraryOpen && !live && (
    <LibraryPanel
      library={library}
      chosen={tool.type === "place" ? tool.kind : undefined}
      onChoose={choose}
      onClose={(backToBoard) => {
        setLibraryOpen(false);
        if (backToBoard) focusBoard();
      }}
      parts={myParts?.list}
      partsLabel={myParts?.label}
      removeLabel={myParts?.removeLabel}
      onRemovePart={myParts?.onRemove}
      onChoosePart={(p) => setTool({ type: "place", kind: partKind(p.id), part: { key: p.id, def: p.def } })}
    />
  );

  const boardView = (
    <div
      data-board
      data-full={full || undefined}
      data-active={active || full || undefined} // (on a touch screen: one finger pans it, not the page — Canvas.css)
      className={
        bare ? "group/board relative overflow-hidden bg-board h-full" : cn(board, "h-120", active && "border-accent")
      }
      // with a bar laid over its top edge: as much board as without one, its islands below the bar
      style={bare ? undefined : { height: boardHeight }}
      // (a finger: once it taps, not as it scrolls the page past)
      onPointerDownCapture={(event) => event.pointerType !== "touch" && setActive(true)}
      onClickCapture={() => setActive(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node)) setActive(false);
      }}
    >
      <div className="absolute inset-0 overflow-hidden" ref={viewRef}>
        <svg
          ref={svgRef}
          className={cn(
            "canvas",
            `tool-${tool.type}`,
            wiring && "wiring",
            (spaceHeld || (live && liveTool === "hand")) && "panning",
            live && "running",
            live && liveTool === "probe" && "probing",
          )}
          viewBox={`${cam.x} ${cam.y} ${view.w / cam.zoom} ${view.h / cam.zoom}`}
          width="100%"
          height="100%"
          tabIndex={0}
          onPointerDown={(event) => {
            if (spaceHeld || (live && liveTool === "hand") || event.button === 1) startPan(event, false);
            else if (drawingTool && (tool.type === "select" || event.shiftKey) && !viewOnly && !live)
              startBox(event); // the arrow (or shift held): a drag selects many
            else if (drawingTool)
              startPan(event, true); // the hand: a drag pans, a click deselects
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
          onPointerCancel={() => {
            pan.current = null; // (the page scrolled instead: a finger on a board not in use)
          }}
          onPointerLeave={() => {
            pointer.current = null;
            setCursor(null);
          }}
          onKeyDown={(event) => {
            if (live && pressKey(event, true)) return;
            if (event.key === " ") {
              setSpaceHeld(true);
              event.preventDefault();
              return;
            }
            if (!viewOnly) onKey(event);
          }}
          onKeyUp={(event) => {
            if (live && pressKey(event, false)) return;
            if (event.key === " ") setSpaceHeld(false);
          }}
          onBlur={() => {
            if (live) for (const id of heldKeys.current) live.onPress(id, false);
            heldKeys.current.clear();
          }}
        >
          <style>{library.style}</style>
          <defs>
            <pattern id={gridId} width={G} height={G} patternUnits="userSpaceOnUse" x={-G / 2} y={-G / 2}>
              <circle cx={G / 2} cy={G / 2} r="1" className="grid-dot" />
            </pattern>
          </defs>
          {/* the grid covers exactly what the camera sees, so it never ends */}
          <rect
            className="grid"
            x={cam.x}
            y={cam.y}
            width={view.w / cam.zoom}
            height={view.h / cam.zoom}
            fill={`url(#${CSS.escape(gridId)})`}
          />

          {value.wires.map((w, i) => {
            const chosen = picked(selection).wires.includes(i) || (probed?.type === "wire" && probed.index === i);
            return (
              <g key={i}>
                {chosen && <polyline className="wire-glow" points={pointsOf(w.points)} />}
                <polyline
                  className={`w wire ${chosen ? "selected" : ""}`}
                  style={live ? { stroke: liveColor(live.wires[i] ?? null, live.scale) } : undefined}
                  points={pointsOf(w.points)}
                />
                {w.points.slice(1).map((q, j) => (
                  <polyline
                    key={j}
                    // (selected: its segment moves sideways; else a wire starts from it)
                    className={`hit ${chosen ? (w.points[j][1] === q[1] ? "segment-h" : "segment-v") : "segment-from"}`}
                    points={pointsOf([w.points[j], q])}
                    onPointerDown={(event) => onSegmentDown(event, i, j)}
                    onPointerEnter={() => !chosen && setOver({ wire: i, index: j })}
                    onPointerLeave={() => setOver(null)}
                  >
                    <title>{t(chosen ? "drawing.moveSegment" : "drawing.drawWire")}</title>
                  </polyline>
                ))}
              </g>
            );
          })}
          {groupFrame && (
            <rect
              className="group-frame"
              x={groupFrame[0] * G - 20}
              y={groupFrame[1] * G - 20}
              width={(groupFrame[2] - groupFrame[0]) * G + 40}
              height={(groupFrame[3] - groupFrame[1]) * G + 40}
              rx="6"
            />
          )}
          {junctionPoints.map(([x, y]) => (
            <circle
              key={`j${x},${y}`}
              className="dot"
              cx={x * G}
              cy={y * G}
              r="3"
              style={live ? { fill: liveColor(dotVoltage([x, y]), live.scale) } : undefined}
            />
          ))}
          {live &&
            value.elements
              .filter((e) => e.kind === "led" && (live.leds[e.id] ?? 0) > 0.01)
              .map((e) => {
                const [a, b] = pins(e, library);
                return (
                  <circle
                    key={`glow${e.id}`}
                    className="led-glow"
                    cx={((a[0] + b[0]) / 2) * G}
                    cy={((a[1] + b[1]) / 2) * G}
                    r={22}
                    style={{ fill: ledColor(e.text), opacity: 0.15 + 0.75 * Math.sqrt(live.leds[e.id]) }}
                  />
                );
              })}
          {live &&
            value.elements
              .filter((e) => e.kind === "rgb_led")
              .map((e) => {
                // the three colours mixed, as the eye sees them a little way off
                const { r = 0, g = 0, b = 0 } = live.looks[e.id] ?? {};
                const most = Math.max(r, g, b);
                if (most <= 0.01) return null;
                const [, green, , k] = pins(e, library);
                const rgb = [r, g, b].map((c) => Math.round((255 * c) / most)).join(" ");
                return (
                  <circle
                    key={`glow${e.id}`}
                    className="led-glow"
                    cx={((green[0] + k[0]) / 2) * G}
                    cy={((green[1] + k[1]) / 2) * G}
                    r={30}
                    style={{ fill: `rgb(${rgb})`, opacity: 0.15 + 0.75 * most }}
                  /> /* (its channels: as the eye sees them already) */
                );
              })}
          {value.elements.map((e) => (
            <ElementView
              key={e.id}
              element={e}
              library={library}
              wires={obstacles}
              result={results?.[e.id]}
              closed={
                e.kind === "switch" ? e.text === "closed" : e.kind === "button" ? !!live?.pressed.includes(e.id) : false
              }
              lit={live && e.kind === "led" ? (live.leds[e.id] ?? 0) : undefined}
              look={live?.looks[e.id]}
              live={live && { pins: live.pins[e.id] ?? [], scale: live.scale }}
              selected={picked(selection).ids.includes(e.id) || (probed?.type === "element" && probed.id === e.id)}
              onPointerDown={onElementDownStable}
            />
          ))}
          {live && flow && <CurrentDots segments={dotted} currents={dottedCurrents} moving={!live.paused} />}
          {live &&
            value.elements
              .filter((e) => (e.kind === "lcd1602" || e.kind === "lcd1602_i2c") && live.screens[e.id])
              .map((e) => (
                <LcdScreen
                  key={`lcd${e.id}`}
                  screen={live.screens[e.id]}
                  at={[e.at[0] * G, e.at[1] * G]}
                  rotation={e.rotation}
                  offset={e.kind === "lcd1602_i2c" ? [50, -50] : undefined}
                />
              ))}
          {live &&
            value.elements
              .filter((e) => e.kind === "ssd1306" && live.oleds[e.id])
              .map((e) => (
                <OledScreen
                  key={`oled${e.id}`}
                  screen={live.oleds[e.id]}
                  at={[e.at[0] * G, e.at[1] * G]}
                  rotation={e.rotation}
                />
              ))}
          {live &&
            value.elements
              .filter((e) => e.kind === "ili9341" && live.tfts[e.id])
              .map((e) => (
                <TftScreen
                  key={`tft${e.id}`}
                  id={e.id}
                  screen={live.tfts[e.id]}
                  at={[e.at[0] * G, e.at[1] * G]}
                  rotation={e.rotation}
                />
              ))}
          {openPinPoints.map(([x, y]) => (
            <circle key={`o${x},${y}`} className="open-pin" cx={x * G} cy={y * G} r="3.5">
              <title>{t("drawing.openPin")}</title>
            </circle>
          ))}
          {value.elements
            .filter((e) => isComponent(e.kind))
            .flatMap((e) =>
              pins(e, library).map(([x, y], i) => (
                <circle
                  key={`p${e.id}${i}`}
                  className="pin-handle"
                  cx={x * G}
                  cy={y * G}
                  r="8"
                  onPointerDown={(event) => onPinDown(event, [x, y], e)}
                >
                  <title>{t("drawing.drawWire")}</title>
                </circle>
              )),
            )}
          {preview && <polyline className="w draft" points={pointsOf(preview)} />}
          {gesture?.type === "box" && (
            <rect
              className="rubber-band"
              x={Math.min(gesture.from[0], gesture.to[0]) * G}
              y={Math.min(gesture.from[1], gesture.to[1]) * G}
              width={Math.abs(gesture.to[0] - gesture.from[0]) * G}
              height={Math.abs(gesture.to[1] - gesture.from[1]) * G}
            />
          )}
          {snap && <circle className="snap" cx={snap[0] * G} cy={snap[1] * G} r="7" />}
          {(() => {
            // where on the wire under the pointer a new one would start
            const w = over && !gesture && !live && drawingTool && cursor ? value.wires[over.wire] : undefined;
            const [a, b] = w ? [w.points[over!.index], w.points[over!.index + 1]] : [];
            if (!a || !b || !cursor || picked(selection).wires.includes(over!.wire)) return null;
            const clamp = (v: number, p: number, q: number) => Math.min(Math.max(v, Math.min(p, q)), Math.max(p, q));
            const at = a[1] === b[1] ? [clamp(cursor[0], a[0], b[0]), a[1]] : [a[0], clamp(cursor[1], a[1], b[1])];
            return <circle className="wire-start" cx={at[0] * G} cy={at[1] * G} r="5" />;
          })()}
          {tool.type === "place" && cursor && (
            <g
              className="w ghost"
              transform={`translate(${placedAt(tool.kind, cursor, placing)
                .map((c) => c * G)
                .join(" ")})`}
              dangerouslySetInnerHTML={{ __html: placing.kinds[tool.kind]?.svg ?? "" }}
            />
          )}
        </svg>
      </div>

      {topLeft && <BoardIsland className="top-[calc(var(--board-top,0px)+0.75rem)] left-3 p-1">{topLeft}</BoardIsland>}
      {live ? (
        <LiveToolbar
          current={liveTool}
          onTool={(next) => {
            setLiveTool(next);
            if (next !== "probe") setProbed(null);
            focusBoard();
          }}
        />
      ) : viewOnly ? null : (
        <Toolbar
          // (a phone: the top right corner is the full screen button's — the tools from the left, short of it)
          className={topRight ? "max-sm:left-3 max-sm:translate-x-0 max-sm:max-w-[calc(100%-80px)]" : undefined}
          current={tool}
          locked={locked}
          onLock={() => setLocked(!locked)}
          libraryOpen={libraryOpen}
          onTool={(next) => {
            setTool(next);
            focusBoard();
          }}
          onLibrary={() => (libraryOpen ? setLibraryOpen(false) : openLibrary())}
        />
      )}
      {live && probed && probe?.(probed, () => setProbed(null))}
      {panel}
      {topRight && <BoardIsland className="top-[calc(var(--board-top,0px)+0.75rem)] right-3">{topRight}</BoardIsland>}
      {/* a wire, a few things, or an element tapped once (its panel not open) selected: away with them (a
          finger has no Del key) */}
      {!live &&
        !viewOnly &&
        !phone &&
        (selection?.type === "wire" || selection?.type === "group" || (selection?.type === "element" && !inspect)) && (
          <BoardIsland stays className="top-15 right-3">
            <BoardButton
              className={cn(islandButton(), "hover:bg-err-bg hover:text-danger")}
              onClick={removeSelected}
              title={t("inspector.removeTitle")}
              aria-label={t("inspector.remove")}
            >
              <Trash />
            </BoardButton>
          </BoardIsland>
        )}
      {(live ? isAdjustable(selectedKind ?? "") && !probed : !viewOnly && selectedElement && inspect) && (
        <Inspector
          element={selectedElement}
          live={!!live}
          taken={value.elements.map((e) => e.id)}
          onChange={(patch) => selectedElement && commit(updateElement(value, library, selectedElement.id, patch))}
          onRename={(id) => {
            if (!selectedElement) return;
            commit({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, id } : e)) });
            setSelection({ type: "element", id });
          }}
          onRotate={() => rotateSelected()}
          onRemove={removeSelected}
        />
      )}
      {lost && (
        // the drawing is out of view: a way back, bottom centre (like Excalidraw's "scroll back to content")
        <button
          className={cn(
            boardIsland(),
            below ? "bottom-17" : "bottom-3", // above the simulation's controls
            corner && (below ? "max-sm:bottom-31" : "max-sm:bottom-17"), // (a phone: above the corner's island too)
            "left-1/2 -translate-x-1/2 gap-2 px-3.5 py-2 border border-transparent text-[14px] font-medium text-fg hover:bg-selected",
          )}
          onClick={() => setCam(fitted())}
        >
          <Target /> {t("view.back")}
        </button>
      )}
      {below && (
        <BoardIsland
          stays
          // (a phone: a row up, the corner's island is as wide as the rest of the bottom)
          className={cn("bottom-3 left-1/2 -translate-x-1/2", corner && "max-sm:bottom-17")}
        >
          {below}
        </BoardIsland>
      )}
      <ZoomAndHistory
        zoom={cam.zoom}
        onZoom={(f) => zoomAround(f)}
        onFit={() => setCam(fitted())}
        onUndo={undoStep}
        onRedo={redo}
        history={!live && !viewOnly}
      />
      {/* bottom right: what is wrong with the circuit (always shown, a sign of its own), then full screen */}
      <div className="absolute bottom-3 right-3 z-3 flex items-end gap-1.5">
        {status}
        {/* a phone: what is selected, its own buttons — turned, away, its whole panel */}
        {phone && !live && !viewOnly && selection && !(selectedElement && inspect) && (
          <BoardIsland stays className="static gap-1 [&_button]:size-9">
            {selectedElement && (
              <BoardButton
                className={islandButton()}
                onClick={() => rotateSelected()}
                title={t("inspector.rotateTitle")}
                aria-label={t("inspector.rotate")}
              >
                <Rotate />
              </BoardButton>
            )}
            <BoardButton
              className={cn(islandButton(), "hover:bg-err-bg hover:text-danger")}
              onClick={removeSelected}
              title={t("inspector.removeTitle")}
              aria-label={t("inspector.remove")}
            >
              <Trash />
            </BoardButton>
            {selectedElement && (
              <BoardButton
                className={islandButton()}
                onClick={() => setInspect(true)}
                title={t("inspector.label")}
                aria-label={t("inspector.label")}
              >
                <More />
              </BoardButton>
            )}
          </BoardIsland>
        )}
        {corner && (
          <BoardIsland stays className="static gap-1 [&_button]:size-9">
            {corner}
          </BoardIsland>
        )}
        <ScreenAndHelp
          className="static"
          full={full}
          onFull={() => onFull(!full)}
          onHelp={() => setHelp((h) => !h)}
          help={!live && !viewOnly}
          screen={!bare}
        />
      </div>
      {help && !live && <HelpPanel />}
    </div>
  );
  return boardView;
}
