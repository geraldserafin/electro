// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
//
// The drawing lives on an endless plane; the board shows it through a camera (a viewBox
// that pans and zooms), like Excalidraw. Nothing moves under the cursor unless you pan.
import { useEffect, useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { Expand, Grid, Hand, Help, Minus, Plus, Pointer, Redo, Search, Shrink, Undo, WireIcon } from "../icons";
import type { ElementData, ElementResult, Point, SchematicData, SymbolLibrary, WireData } from "../types";
import {
  KINDS, attach, bounds, elbow, inBox, moveGroup, searchKinds, hasValue, isComponent, isConnectionPoint, junctions, kindInfo, nextId,
  moveSegment, openPins, pins, rotatedAbout, same, simplify, updateElement,
} from "./model";

type Tool = { type: "select" } | { type: "hand" } | { type: "wire" } | { type: "place"; kind: string };
type Camera = { x: number; y: number; zoom: number }; // top-left corner of the view, in drawing px
type Selection =
  | { type: "element"; id: string }
  | { type: "wire"; index: number }
  | { type: "group"; ids: string[]; wires: number[] } // from shift + drag
  | null;
type Gesture =
  | { type: "move"; id: string; start: Point; origin: Point; snapshot: SchematicData; moved: boolean }
  | { type: "wire"; from: Point }
  | { type: "segment"; wire: number; index: number; start: Point; snapshot: SchematicData; moved: boolean }
  | { type: "group"; ids: string[]; wires: number[]; start: Point; snapshot: SchematicData; moved: boolean }
  | { type: "box"; from: Point; to: Point }; // shift + drag on empty space, in drawing units (not rounded)

interface Props {
  value: SchematicData;
  onChange: (value: SchematicData) => void;
  library: SymbolLibrary;
  results?: Record<string, ElementResult>; // from "Symuluj", drawn next to the elements
  topLeft?: ReactNode;
  topRight?: ReactNode;
}

const clampZoom = (z: number) => Math.min(3, Math.max(0.25, z));

const HISTORY = 100;
const PANEL = 260; // screen px the element panel takes on the left (with its margin)

/** Start with the drawing near the top-left, below the toolbar. */
function startCamera(sch: SchematicData, lib: SymbolLibrary): Camera {
  if (!sch.elements.length && !sch.wires.length) return { x: -40, y: -100, zoom: 1 };
  const [x0, y0] = bounds(sch, lib);
  return { x: x0 * lib.grid - 80, y: y0 * lib.grid - 110, zoom: 1 };
}

export function SchematicEditor({ value, onChange, library, results, topLeft, topRight }: Props) {
  const G = library.grid;
  const gridId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const [tool, setTool] = useState<Tool>({ type: "select" });
  const [selection, setSelection] = useState<Selection>(null);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Point[] | null>(null);
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const history = useRef<{ past: SchematicData[]; future: SchematicData[] }>({ past: [], future: [] });
  const viewRef = useRef<HTMLDivElement>(null);
  const [help, setHelp] = useState(false);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [full, setFull] = useState(false);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const [cam, setCam] = useState<Camera>(() => startCamera(value, library));
  const pan = useRef<{ x: number; y: number; cam: Camera; moved: boolean; click: boolean } | null>(null);

  // the size of the board on screen: the camera shows view.w × view.h screen px
  const [view, setView] = useState({ w: 800, h: 480 });
  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setView({ w: el.clientWidth, h: el.clientHeight }));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  // in the notebook the board is as tall as the drawing needs (fixed after opening, so it never jumps)
  const [boardHeight] = useState(() => {
    const [, y0, , y1] = bounds(value, library);
    return Math.min(640, Math.max(440, (y1 - y0) * G + 240)); // ≥ 440: room for the element panel
  });

  /** A camera that shows the whole drawing. */
  const fitted = (): Camera => {
    if (!value.elements.length && !value.wires.length) return startCamera(value, library);
    const [x0, y0, x1, y1] = bounds(value, library);
    const w = (x1 - x0) * G + 160;
    const h = (y1 - y0) * G + 140;
    const zoom = clampZoom(Math.min(1.5, view.w / w, (view.h - 120) / h));
    return { x: ((x0 + x1) / 2) * G - view.w / 2 / zoom, y: ((y0 + y1) / 2) * G - (view.h + 40) / 2 / zoom, zoom };
  };

  const zoomAround = (factor: number, px = view.w / 2, py = view.h / 2) =>
    setCam((c) => {
      const zoom = clampZoom(c.zoom * factor);
      return { x: c.x + px / c.zoom - px / zoom, y: c.y + py / c.zoom - py / zoom, zoom };
    });

  // wheel / trackpad: pinch or ⌘/Ctrl zooms around the cursor; scrolling pans — but only once the
  // board is in use (clicked, or full screen), so that the notebook page still scrolls past it
  const [active, setActive] = useState(false);
  useEffect(() => {
    const el = viewRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      const zooming = event.ctrlKey || event.metaKey;
      if (!zooming && !active && !full) return;
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      // a trackpad pinch sends small steps, a mouse wheel big ones: cap a step at ~28%
      const step = Math.max(-25, Math.min(25, event.deltaY));
      if (zooming) zoomAround(Math.exp(-step * 0.01), event.clientX - rect.left, event.clientY - rect.top);
      else setCam((c) => ({ ...c, x: c.x + event.deltaX / c.zoom, y: c.y + event.deltaY / c.zoom }));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  // ------------------------------------------------------------------ changes and history

  const commit = (next: SchematicData, before: SchematicData = value) => {
    history.current.past = [...history.current.past.slice(-HISTORY + 1), before];
    history.current.future = [];
    onChange(next);
  };
  const undo = () => {
    const previous = history.current.past.pop();
    if (!previous) return;
    history.current.future.push(value);
    setSelection(null);
    onChange(previous);
  };
  const redo = () => {
    const next = history.current.future.pop();
    if (!next) return;
    history.current.past.push(value);
    onChange(next);
  };

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

  const addWire = (points: Point[]) => {
    const clean = simplify(points);
    if (clean.length >= 2) commit({ ...value, wires: [...value.wires, { points: clean }] });
  };

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

  const onCanvasDown = (event: ReactPointerEvent) => {
    svgRef.current?.focus({ preventScroll: true });
    const p = toGrid(event);
    if (tool.type === "place") {
      const element: ElementData = {
        id: nextId(value, tool.kind), kind: tool.kind, at: p, rotation: 0,
        value: null, text: tool.kind === "label" ? "A" : null,
      };
      commit(attach({ ...value, elements: [...value.elements, element] }, library, element.id));
      setSelection({ type: "element", id: element.id });
      setTool({ type: "select" });
    } else if (tool.type === "wire") addDraftPoint(p);
  };

  /** Drag the view. From empty space in select mode a click without dragging deselects. */
  const startPan = (event: ReactPointerEvent, click: boolean) => {
    svgRef.current?.focus({ preventScroll: true });
    pan.current = { x: event.clientX, y: event.clientY, cam, moved: false, click };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onElementDown = (event: ReactPointerEvent, e: ElementData) => {
    if (tool.type !== "select") return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    if (selection?.type === "group" && selection.ids.includes(e.id))
      setGesture({ type: "group", ids: selection.ids, wires: selection.wires, start: toGrid(event), snapshot: value, moved: false });
    else {
      setSelection({ type: "element", id: e.id });
      setGesture({ type: "move", id: e.id, start: toGrid(event), origin: e.at, snapshot: value, moved: false });
    }
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const toDrawing = (event: { clientX: number; clientY: number }): Point => {
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svgRef.current!.getScreenCTM()!.inverse());
    return [point.x / G, point.y / G];
  };

  const startBox = (event: ReactPointerEvent) => {
    svgRef.current?.focus({ preventScroll: true });
    const p = toDrawing(event);
    setGesture({ type: "box", from: p, to: p });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onPinDown = (event: ReactPointerEvent, pin: Point) => {
    if (tool.type !== "select") return; // the wire tool handles pins like any other point
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    setGesture({ type: "wire", from: pin });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onMove = (event: ReactPointerEvent) => {
    const p = toGrid(event);
    if (!cursor || !same(cursor, p)) setCursor(p);
    if (gesture?.type === "move") {
      const e = gesture.snapshot.elements.find((x) => x.id === gesture.id)!;
      const at: Point = [e.at[0] + p[0] - gesture.start[0], e.at[1] + p[1] - gesture.start[1]];
      if (!same(at, value.elements.find((x) => x.id === gesture.id)!.at)) {
        onChange(updateElement(gesture.snapshot, library, gesture.id, { at }));
        if (!gesture.moved) setGesture({ ...gesture, moved: true });
      }
    }
    if (gesture?.type === "box") setGesture({ ...gesture, to: toDrawing(event) });
    if (gesture?.type === "group") {
      const d: Point = [p[0] - gesture.start[0], p[1] - gesture.start[1]];
      onChange(moveGroup(gesture.snapshot, library, gesture.ids, gesture.wires, d));
      if ((d[0] || d[1]) && !gesture.moved) setGesture({ ...gesture, moved: true });
    }
    if (gesture?.type === "segment") {
      const w = gesture.snapshot.wires[gesture.wire];
      const [a, b] = [w.points[gesture.index], w.points[gesture.index + 1]];
      const by = a[1] === b[1] ? p[1] - gesture.start[1] : p[0] - gesture.start[0];
      const wires = gesture.snapshot.wires.map((x, i) => (i === gesture.wire ? moveSegment(x, gesture.index, by) : x));
      onChange({ ...gesture.snapshot, wires });
      if (by && !gesture.moved) setGesture({ ...gesture, moved: true });
    }
  };

  const onSegmentDown = (event: ReactPointerEvent, wire: number, index: number) => {
    if (tool.type !== "select") return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    setSelection({ type: "wire", index: wire });
    setGesture({ type: "segment", wire, index, start: toGrid(event), snapshot: value, moved: false });
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onUp = () => {
    if (gesture?.type === "move" && gesture.moved) commit(attach(value, library, gesture.id), gesture.snapshot);
    if (gesture?.type === "segment" && gesture.moved) commit(value, gesture.snapshot);
    if (gesture?.type === "group" && gesture.moved) commit(value, gesture.snapshot);
    if (gesture?.type === "box") {
      const { ids, wires } = inBox(value, library, gesture.from, gesture.to);
      setSelection(ids.length + wires.length === 0 ? null
        : ids.length === 1 && !wires.length ? { type: "element", id: ids[0] }
        : { type: "group", ids, wires });
    }
    if (gesture?.type === "wire" && cursor && !same(cursor, gesture.from)) addWire(elbow(gesture.from, cursor));
    setGesture(null);
  };

  const onKey = (event: React.KeyboardEvent) => {
    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === "z") (event.shiftKey ? redo : undo)();
    else if (mod && event.key.toLowerCase() === "y") redo();
    else if (event.key === "Escape") {
      // one step back at a time: the wire being drawn, the tool / selection, the panel, full screen
      if (draft) setDraft(null);
      else if (tool.type !== "select" || selection) {
        setTool({ type: "select" });
        setSelection(null);
      } else if (libraryOpen) setLibraryOpen(false);
      else if (full) setFull(false);
    } else if (event.key === "Enter" && draft) {
      addWire(draft);
      setDraft(null);
    } else if ((event.key === "r" || event.key === "R") && !mod) rotateSelected();
    else if ((event.key === "v" || event.key === "V") && !mod) { setTool({ type: "select" }); setDraft(null); }
    else if ((event.key === "h" || event.key === "H") && !mod) { setTool({ type: "hand" }); setDraft(null); }
    else if ((event.key === "w" || event.key === "W") && !mod) setTool({ type: "wire" });
    else if (/^[0-9]$/.test(event.key) && !mod) {
      const k = KINDS[(Number(event.key) + 9) % 10];
      if (k) choose(k.kind);
    }
    else if ((event.key === "k" || event.key === "K") && !mod) (libraryOpen ? setLibraryOpen(false) : openLibrary());
    else if (event.key === "/" && !mod) openLibrary();
    else if ((event.key === "f" || event.key === "F") && !mod) setFull((f) => !f);
    else if (event.key === "Delete" || event.key === "Backspace") removeSelected();
    else return;
    event.preventDefault();
  };

  // ------------------------------------------------------------------ what to draw

  const wiring = draft !== null || gesture?.type === "wire";
  const preview: Point[] | null =
    cursor && draft ? [...draft, ...elbow(draft[draft.length - 1], cursor).slice(1)]
    : cursor && gesture?.type === "wire" ? elbow(gesture.from, cursor)
    : null;
  const snap = wiring && cursor && isConnectionPoint(value, library, cursor) ? cursor : null;
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");

  const hint =
    tool.type === "place" ? `Kliknij na siatce, żeby postawić: ${kindInfo(tool.kind)?.name ?? tool.kind}. Esc — anuluj.`
    : tool.type === "wire" ? "Klikaj kolejne punkty; przewód kończy się sam na pinie albo innym przewodzie. Esc — przerwij."
    : tool.type === "hand" ? "Przeciągnij, żeby przesunąć widok · ⌘/Ctrl + kółko albo szczypanie powiększa"
    : "Przeciągnij element, żeby go przesunąć · od końcówki — przewód · puste miejsce — przesuwa widok · Shift + przeciągnij — zaznacz wiele";

  /** Pick an element to place (the side panel stays open, like Excalidraw's). */
  function choose(kind: string) {
    setTool({ type: "place", kind });
    setDraft(null);
    svgRef.current?.focus({ preventScroll: true });
  }

  function openLibrary() {
    setQuery("");
    setLibraryOpen(true);
    // the panel covers the left of the board: move the drawing out from under it
    if (!value.elements.length && !value.wires.length) return;
    const left = (bounds(value, library)[0] * G - 60 - cam.x) * cam.zoom; // - room for labels
    if (left < PANEL) setCam((c) => ({ ...c, x: c.x - (PANEL - left) / c.zoom }));
  }

  const symbolIcon = (kind: string) =>
    isComponent(kind) || kind === "ground"
      ? (
        <svg viewBox={kind === "ground" ? "-14 -4 28 26" : "-6 -26 92 52"} width="30" height="22" className="tool-symbol">
          <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[kind].svg }} />
        </svg>
      )
      : <span className="tool-text">A</span>;
  const shortcut = (kind: string) => {
    const i = KINDS.findIndex((k) => k.kind === kind);
    return i >= 0 && i < 10 ? String((i + 1) % 10) : "";
  };

  const tools: { tool: Tool; label: string; key: string; icon: ReactNode }[] = [
    { tool: { type: "select" }, label: "Zaznacz", key: "V", icon: <Pointer /> },
    { tool: { type: "hand" }, label: "Rączka — przesuwanie widoku", key: "H", icon: <Hand /> },
    { tool: { type: "wire" }, label: "Przewód", key: "W", icon: <WireIcon /> },
  ];
  const found = searchKinds(query);
  const groups = [...new Set(found.map((k) => k.group))];
  const isActive = (t: Tool) => t.type === tool.type && (t.type !== "place" || (tool.type === "place" && t.kind === tool.kind));

  return (
    <div
      className={`board ${spaceHeld || tool.type === "hand" ? "panning" : ""} ${full ? "fullscreen" : ""} ${active ? "active" : ""}`}
      style={full ? undefined : { height: boardHeight }}
      onPointerDownCapture={() => setActive(true)}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setActive(false); }}
    >
      <div className="board-view" ref={viewRef}>
        <svg
          ref={svgRef}
          className={`canvas tool-${tool.type} ${wiring ? "wiring" : ""}`}
          viewBox={`${cam.x} ${cam.y} ${view.w / cam.zoom} ${view.h / cam.zoom}`}
          width="100%"
          height="100%"
          tabIndex={0}
          onPointerDown={(event) => {
            if (spaceHeld || tool.type === "hand" || event.button === 1) startPan(event, false);
            else if (tool.type === "select" && event.shiftKey) startBox(event); // shift + drag: select many
            else if (tool.type === "select") startPan(event, true); // empty space: drag pans, click deselects
            else onCanvasDown(event);
          }}
          onPointerMove={(event) => {
            const p = pan.current;
            if (p) {
              const [dx, dy] = [event.clientX - p.x, event.clientY - p.y];
              if (Math.abs(dx) + Math.abs(dy) > 3) p.moved = true;
              if (p.moved) setCam({ ...p.cam, x: p.cam.x - dx / p.cam.zoom, y: p.cam.y - dy / p.cam.zoom });
              return;
            }
            onMove(event);
          }}
          onPointerUp={() => {
            const p = pan.current;
            if (p) {
              if (p.click && !p.moved) setSelection(null);
              pan.current = null;
              return;
            }
            onUp();
          }}
          onPointerLeave={() => setCursor(null)}
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
          <rect className="grid no-print" x={cam.x} y={cam.y} width={view.w / cam.zoom} height={view.h / cam.zoom}
                fill={`url(#${CSS.escape(gridId)})`} />

          {value.wires.map((w, i) => (
            <g key={i}>
              <polyline className={`w wire ${(selection?.type === "wire" && selection.index === i)
                || (selection?.type === "group" && selection.wires.includes(i)) ? "selected" : ""}`}
                        points={pointsOf(w.points)} />
              {w.points.slice(1).map((q, j) => (
                <polyline
                  key={j}
                  className={`hit ${w.points[j][1] === q[1] ? "segment-h" : "segment-v"}`}
                  points={pointsOf([w.points[j], q])}
                  onPointerDown={(event) => onSegmentDown(event, i, j)}
                >
                  <title>Przeciągnij, żeby przesunąć ten odcinek</title>
                </polyline>
              ))}
            </g>
          ))}
          {junctions(value, library).map(([x, y]) => (
            <circle key={`j${x},${y}`} className="dot" cx={x * G} cy={y * G} r="3" />
          ))}
          {value.elements.map((e) => (
            <ElementView key={e.id} element={e} library={library} wires={value.wires} result={results?.[e.id]}
                         selected={(selection?.type === "element" && selection.id === e.id)
                           || (selection?.type === "group" && selection.ids.includes(e.id))}
                         onPointerDown={(event) => onElementDown(event, e)} />
          ))}
          {openPins(value, library).map(([x, y]) => (
            <circle key={`o${x},${y}`} className="open-pin no-print" cx={x * G} cy={y * G} r="3.5">
              <title>Niepodłączony zacisk</title>
            </circle>
          ))}
          {value.elements.filter((e) => isComponent(e.kind)).flatMap((e) =>
            pins(e, library).map(([x, y], i) => (
              <circle key={`p${e.id}${i}`} className="pin-handle no-print" cx={x * G} cy={y * G} r="8"
                      onPointerDown={(event) => onPinDown(event, [x, y])}>
                <title>Przeciągnij, żeby poprowadzić przewód</title>
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
            <g className="w ghost" transform={`translate(${cursor[0] * G} ${cursor[1] * G})`}
               dangerouslySetInnerHTML={{ __html: library.kinds[tool.kind].svg }} />
          )}
        </svg>
      </div>

      <div className="island top-left no-print">{topLeft}</div>
      <div className="island tools no-print" role="toolbar">
        {tools.map(({ tool: t, label, key, icon }) => (
          <button
            key={label}
            className={`tool ${isActive(t) ? "active" : ""}`}
            title={`${label}${key ? ` (${key})` : ""}`}
            aria-label={label}
            onClick={() => (t.type === "place" ? choose(t.kind) : (setTool(t), setDraft(null), svgRef.current?.focus({ preventScroll: true })))}
          >
            {icon}
            {key && <span className="key">{key}</span>}
          </button>
        ))}
        <span className="sep" />
        <button
          className={`tool library-button ${libraryOpen ? "active" : ""}`}
          title="Panel elementów (K)"
          aria-label="Elementy"
          onClick={() => (libraryOpen ? setLibraryOpen(false) : openLibrary())}
        >
          <Grid /> <span>Elementy</span>
          <span className="key">K</span>
        </button>
      </div>
      {libraryOpen && (
        <div className="island library no-print" role="complementary" aria-label="Biblioteka elementów">
          <div className="library-head">
            <h4>Elementy</h4>
            <button className="icon" onClick={() => setLibraryOpen(false)} title="Zamknij panel (K)" aria-label="Zamknij panel">×</button>
          </div>
          <label className="library-search">
            <Search />
            <input
              autoFocus
              value={query}
              placeholder="Szukaj: opornik, bateria, masa…"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && found[0]) choose(found[0].kind);
                if (e.key === "Escape") { setLibraryOpen(false); svgRef.current?.focus({ preventScroll: true }); }
              }}
            />
          </label>
          {groups.map((group) => (
            <section key={group}>
              <h5>{group}</h5>
              <div className="library-grid">
                {found.filter((k) => k.group === group).map((k) => (
                  <button key={k.kind} className={`library-item ${tool.type === "place" && tool.kind === k.kind ? "active" : ""}`}
                          title={k.name} onClick={() => choose(k.kind)}>
                    {symbolIcon(k.kind)}
                    <span>{k.name}</span>
                    {shortcut(k.kind) && <kbd>{shortcut(k.kind)}</kbd>}
                  </button>
                ))}
              </div>
            </section>
          ))}
          {!found.length && <p className="muted">Nic nie pasuje do „{query}”.</p>}
        </div>
      )}
      {!libraryOpen && <div className="board-hint no-print">{hint}</div>}
      <div className="island top-right no-print">{topRight}</div>
      {(selectedElement || selection?.type === "wire" || selection?.type === "group") && (
        <Inspector
          key={selectedElement?.id ?? selection?.type ?? "none"}
          selection={selection}
          element={selectedElement}
          taken={value.elements.map((e) => e.id)}
          onChange={(patch) => selectedElement && commit(updateElement(value, library, selectedElement.id, patch))}
          onRename={(id) => {
            if (!selectedElement) return;
            commit({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, id } : e)) });
            setSelection({ type: "element", id });
          }}
          onRotate={rotateSelected}
          onRemove={removeSelected}
        />
      )}
      <div className="island bottom-left no-print">
        <button className="icon" title="Pomniejsz" aria-label="Pomniejsz" onClick={() => zoomAround(1 / 1.2)}><Minus /></button>
        <button className="zoom" title="Pokaż cały schemat" aria-label="Dopasuj widok" onClick={() => setCam(fitted())}>
          {Math.round(cam.zoom * 100)}%
        </button>
        <button className="icon" title="Powiększ" aria-label="Powiększ" onClick={() => zoomAround(1.2)}><Plus /></button>
        <span className="sep" />
        <button className="icon" title="Cofnij (Ctrl/Cmd+Z)" aria-label="Cofnij" onClick={undo}><Undo /></button>
        <button className="icon" title="Ponów (Ctrl/Cmd+Shift+Z)" aria-label="Ponów" onClick={redo}><Redo /></button>
      </div>
      <div className="island bottom-right no-print">
        <button className="icon" title={full ? "Zamknij pełny ekran (F)" : "Pełny ekran (F)"} aria-label="Pełny ekran"
                onClick={() => setFull((f) => !f)}>{full ? <Shrink /> : <Expand />}</button>
        <button className="icon" title="Skróty klawiszowe" aria-label="Pomoc" onClick={() => setHelp((h) => !h)}><Help /></button>
      </div>
      {help && (
        <div className="island help-panel no-print">
          <h4>Skróty</h4>
          <dl>
            <dt>V</dt><dd>zaznacz / przesuń</dd>
            <dt>W</dt><dd>przewód</dd>
            <dt>K lub /</dt><dd>biblioteka elementów (z wyszukiwaniem)</dd>
            <dt>1–0</dt><dd>elementy w kolejności z biblioteki</dd>
            <dt>F</dt><dd>pełny ekran</dd>
            <dt>R</dt><dd>obróć o 90° (dwa razy = odwróć)</dd>
            <dt>Shift + przeciągnij</dt><dd>zaznacz wiele (potem przeciągnij razem, Del usuwa)</dd>
            <dt>Del</dt><dd>usuń zaznaczone</dd>
            <dt>Esc</dt><dd>przerwij / odznacz</dd>
            <dt>⌘/Ctrl Z</dt><dd>cofnij (⇧ — ponów)</dd>
            <dt>H</dt><dd>rączka: przesuwanie widoku</dd>
            <dt>przeciągnij tło</dt><dd>przesuń widok (też spacja, środkowy przycisk)</dd>
            <dt>kółko</dt><dd>przesuń widok (po kliknięciu w schemat)</dd>
            <dt>⌘/Ctrl kółko</dt><dd>powiększ wokół kursora (też szczypanie)</dd>
            <dt>klik w %</dt><dd>pokaż cały schemat</dd>
          </dl>
          <p>Czerwona kropka = zacisk niepodłączony. Przewody łączą się tylko końcami.</p>
        </div>
      )}
    </div>
  );
}

const PRINT_SCALE = 1.1; // drawing px → CSS px on paper: labels come out about as big as the text
const PRINT_PAD = 6;

/**
 * The drawing for the PDF: cropped to what is drawn (texts included), no grid, no selection,
 * the same scale whatever the zoom on screen. Hidden on screen but laid out (not display:none),
 * so it can measure itself.
 */
export function PrintDrawing({ value, library, results }: {
  value: SchematicData; library: SymbolLibrary; results?: Record<string, ElementResult>;
}) {
  const G = library.grid;
  const content = useRef<SVGGElement>(null);
  const [box, setBox] = useState<[number, number, number, number] | null>(null);
  useLayoutEffect(() => {
    const b = content.current?.getBBox();
    if (!b || !b.width) return;
    const next: [number, number, number, number] = [b.x - PRINT_PAD, b.y - PRINT_PAD, b.width + 2 * PRINT_PAD, b.height + 2 * PRINT_PAD];
    if (!box || next.some((v, i) => Math.abs(v - box[i]) > 0.5)) setBox(next);
  });
  if (!value.elements.length && !value.wires.length) return null;
  const pointsOf = (ps: Point[]) => ps.map(([x, y]) => `${x * G},${y * G}`).join(" ");
  const [x, y, w, h] = box ?? [0, 0, 1, 1];
  return (
    <div className="print-drawing" aria-hidden>
      <svg className="canvas" viewBox={`${x} ${y} ${w} ${h}`} width={w * PRINT_SCALE} height={h * PRINT_SCALE}>
        <style>{library.style}</style>
        <g ref={content}>
          {value.wires.map((wire, i) => <polyline key={i} className="w wire" points={pointsOf(wire.points)} />)}
          {junctions(value, library).map(([jx, jy]) => <circle key={`j${jx},${jy}`} className="dot" cx={jx * G} cy={jy * G} r="3" />)}
          {value.elements.map((e) => (
            <ElementView key={e.id} element={e} library={library} wires={value.wires} result={results?.[e.id]}
                         selected={false} onPointerDown={() => {}} />
          ))}
        </g>
      </svg>
    </div>
  );
}

/** The text next to an element: "R_1 = 100 Ω", "A_1", or a net label's name. */
function label_(e: ElementData): string {
  const unit = kindInfo(e.kind)?.unit ?? "";
  if (e.kind === "label") return e.text ?? "";
  if (!isComponent(e.kind)) return "";
  if (!hasValue(e.kind)) return e.id;
  if (kindInfo(e.kind)?.meter && !e.value) return e.id; // no reading: the simulation fills it in
  return `${e.id} = ${e.value ?? "?"}${e.value && /\d$/.test(e.value) ? ` ${unit}` : ""}`;
}

function Label({ text, x, y, anchor, solved }: {
  text: string; x: number; y: number; anchor: "middle" | "end" | "start"; solved?: boolean;
}) {
  const parts = text.match(/^([A-Za-z]+)_(\w+)(.*)$/);
  return (
    <text x={x} y={y} textAnchor={anchor} className={`label ${solved ? "solved" : ""}`}>
      {parts ? (
        <>
          {parts[1]}
          <tspan className="sub" dy="4">{parts[2]}</tspan>
          <tspan dy="-4">{parts[3]}</tspan>
        </>
      ) : text}
    </text>
  );
}

const ARROW: Record<number, [string, string]> = { 0: ["→", "←"], 90: ["↓", "↑"], 180: ["←", "→"], 270: ["↑", "↓"] };

function ElementView({ element: e, library, wires, result, selected, onPointerDown }: {
  element: ElementData; library: SymbolLibrary; wires: WireData[]; result?: ElementResult; selected: boolean;
  onPointerDown: (event: ReactPointerEvent) => void;
}) {
  const G = library.grid;
  const symbol = library.kinds[e.kind];
  const ps = pins(e, library).map(([x, y]) => [x * G, y * G] as Point);
  const cx = ps.reduce((s, p) => s + p[0], 0) / ps.length;
  const cy = ps.reduce((s, p) => s + p[1], 0) / ps.length;
  const xs = ps.map((p) => p[0]);
  const ys = ps.map((p) => p[1]);
  const vertical = e.rotation % 180 !== 0;
  // label left of a vertical element (above a horizontal one), unless a wire runs through there
  const labelWidth = 7.4 * (label_(e).replace("_", "").length) + 6;
  const crosses = (x0: number, x1: number, y0: number, y1: number) =>
    wires.some((w) => w.points.slice(1).some((q, i) => {
      const [ax, ay] = [w.points[i][0] * G, w.points[i][1] * G];
      const [bx, by] = [q[0] * G, q[1] * G];
      return Math.min(ax, bx) <= x1 && Math.max(ax, bx) >= x0 && Math.min(ay, by) <= y1 && Math.max(ay, by) >= y0;
    }));
  // …and always when it would not fit on the canvas (which starts at 0, 0): cut-off text is
  // worse than text over a wire (the text has a halo)
  const flip = vertical
    ? cx - 20 - labelWidth < 0
      || (crosses(cx - 20 - labelWidth, cx - 20, cy - 8, cy + 8) && !crosses(cx + 20, cx + 20 + labelWidth, cy - 8, cy + 8))
    : cy - 32 < 0
      || (crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy - 32, cy - 16) && !crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy + 16, cy + 32));
  const label = result?.solved && result.value
    ? (e.kind === "hole" ? `${e.id}: ${result.value}` : `${e.id} = ${result.value}`)
    : label_(e);
  const readings = result
    ? [result.I && `I = ${result.I} ${ARROW[e.rotation][result.reversed ? 1 : 0]}`, result.U && `U = ${result.U}`].filter(Boolean) as string[]
    : [];
  return (
    <g className={`element ${selected ? "selected" : ""}`} data-id={e.id} onPointerDown={onPointerDown}>
      <rect
        className="hit"
        x={Math.min(...xs) - 12} y={Math.min(...ys) - 12}
        width={Math.max(...xs) - Math.min(...xs) + 24} height={Math.max(...ys) - Math.min(...ys) + 24}
      />
      <g className="w" transform={`translate(${e.at[0] * G} ${e.at[1] * G}) rotate(${symbol.upright ? 0 : e.rotation})`}
         dangerouslySetInnerHTML={{ __html: symbol.svg }} />
      {symbol.letter && <text className="letter" x={cx} y={cy}>{symbol.letter}</text>}
      {label && (e.kind === "label"
        ? <text x={cx + 4} y={cy - 6} className="node">{label}</text>
        : vertical
          ? <Label text={label} x={flip ? cx + 20 : cx - 20} y={readings.length ? cy - 2 : cy + 4} anchor={flip ? "start" : "end"} solved={result?.solved} />
          : <Label text={label} x={cx} y={flip ? cy + 30 : cy - 20} anchor="middle" solved={result?.solved} />)}
      {readings.map((text, i) => vertical
        // beside a vertical element: one block under its label, on the same (free) side
        ? <text key={i} className="reading" x={flip ? cx + 20 : cx - 20} y={cy + 19 + i * 14}
                textAnchor={flip ? "start" : "end"}>{text}</text>
        : <text key={i} className="reading" x={cx} y={(flip ? cy - 34 : cy + 28) + i * 14} textAnchor="middle">{text}</text>)}
    </g>
  );
}

function Inspector({ selection, element, taken, onChange, onRename, onRotate, onRemove }: {
  selection: Selection;
  element: ElementData | null;
  taken: string[];
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRotate: () => void;
  onRemove: () => void;
}) {
  const [id, setId] = useState(element?.id ?? "");
  if (selection?.type === "group")
    return (
      <div className="island inspector no-print">
        <h4>Zaznaczone</h4>
        <p className="muted">{selection.ids.length} el., {selection.wires.length} przew. — przeciągnij, żeby przesunąć razem</p>
        <button className="danger" onClick={onRemove}>Usuń (Del)</button>
      </div>
    );
  if (selection?.type === "wire")
    return (
      <div className="island inspector no-print">
        <h4>Przewód</h4>
        <button className="danger" onClick={onRemove}>Usuń (Del)</button>
      </div>
    );
  if (!element) return null;
  const info = kindInfo(element.kind);
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <div className="island inspector no-print">
      <h4>{info?.name ?? element.kind}</h4>
      {isComponent(element.kind) && (
        <label>
          Etykieta
          <input value={id} onChange={(e) => setId(e.target.value)} onBlur={commitId}
                 onKeyDown={(e) => e.key === "Enter" && commitId()} />
        </label>
      )}
      {hasValue(element.kind) && (
        <label>
          {info?.meter
            ? <>Odczyt <small>({info.unit}; wpisz pomiar z zadania, puste = policz)</small></>
            : <>Wartość {info?.unit && <small>({info.unit}; puste = niewiadoma, litera = symbol)</small>}</>}
          <input value={element.value ?? ""} placeholder={info?.meter ? "brak pomiaru" : "?"}
                 onChange={(e) => onChange({ value: e.target.value.trim() === "" ? null : e.target.value })} />
        </label>
      )}
      {element.kind === "label" && (
        <label>
          Nazwa węzła
          <input value={element.text ?? ""} onChange={(e) => onChange({ text: e.target.value })} />
        </label>
      )}
      <div className="row">
        <button onClick={onRotate}>Obróć (R)</button>
        <button className="danger" onClick={onRemove}>Usuń</button>
      </div>
    </div>
  );
}
