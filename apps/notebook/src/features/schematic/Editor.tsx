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
import { ElementView } from "./ElementView";
import { HelpPanel } from "./HelpPanel";
import { Inspector, type Selection } from "./Inspector";
import { LibraryPanel } from "./LibraryPanel";
import {
  KINDS, attach, bounds, elbow, inBox, moveGroup, isComponent, isConnectionPoint, junctions, nextId,
  moveSegment, openPins, pins, rotatedAbout, same, simplify, updateElement,
} from "./model";
import { SymbolIcon } from "./SymbolIcon";
import { Toolbar, type Tool } from "./Toolbar";
import { useCamera, type Camera } from "./useCamera";
import { useHistory } from "./useHistory";
import { ScreenAndHelp, ZoomAndHistory } from "./ViewControls";
import "./Canvas.css";

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
  results?: Record<string, ElementResult>; // from a run, drawn next to the elements
  topLeft?: ReactNode;
  topRight?: ReactNode;
  status?: ReactNode; // its own island, next to the full screen button (e.g. warnings)
  camera?: { current: Camera | null }; // where the view was: kept here while the editor is away
  autoFocus?: boolean; // take the keyboard when shown
}

const PANEL = 260; // screen px the element panel takes on the left (with its margin)

export function SchematicEditor({ value, onChange, library, results, topLeft, topRight, status, camera, autoFocus }: Props) {
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
  const [full, setFull] = useState(false);
  const [spaceHeld, setSpaceHeld] = useState(false);
  // the board is in use (clicked, or full screen): keys and the wheel go to it
  const [active, setActive] = useState(false);
  const { cam, setCam, view, fitted, lost, zoomAround, screenScale } =
    useCamera({ value, library, viewRef, kept: camera, inUse: active || full });
  const { commit, undo, redo } = useHistory(value, onChange);
  const pan = useRef<{ x: number; y: number; cam: Camera; moved: boolean; click: boolean; k: number } | null>(null);
  const focusBoard = () => svgRef.current?.focus({ preventScroll: true });

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
    pan.current = { x: event.clientX, y: event.clientY, cam, moved: false, click, k: screenScale() };
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

  // ------------------------------------------------------------------ keyboard

  const onKey = (event: KeyboardEvent) => {
    const mod = event.metaKey || event.ctrlKey;
    const plain = (k: string) => !mod && event.key.toLowerCase() === k;
    if (mod && event.key.toLowerCase() === "z") (event.shiftKey ? redo : undoStep)();
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
    else if (plain("f")) setFull((f) => !f);
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
    // the panel covers the left of the board: move the drawing out from under it
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

  return (
    <div
      data-board data-full={full || undefined}
      className={cn(board, "h-120", active && "border-accent", full && "fixed inset-3 z-100 h-auto shadow-[0_10px_40px_rgb(0_0_0/0.25)]")}
      style={full ? undefined : { height: boardHeight }}
      onPointerDownCapture={() => setActive(true)}
      onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setActive(false); }}
    >
      <div className="absolute inset-0 overflow-hidden" ref={viewRef}>
        <svg
          ref={svgRef}
          className={cn("canvas", `tool-${tool.type}`, wiring && "wiring", (spaceHeld || tool.type === "hand") && "panning")}
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
              // the drawing follows the pointer exactly (screen px → board px → drawing px)
              if (p.moved) setCam({ ...p.cam, x: p.cam.x - dx / p.k / p.cam.zoom, y: p.cam.y - dy / p.k / p.cam.zoom });
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
          <rect className="grid" x={cam.x} y={cam.y} width={view.w / cam.zoom} height={view.h / cam.zoom}
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
                  <title>{t("drawing.moveSegment")}</title>
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
            <g className="w ghost" transform={`translate(${cursor[0] * G} ${cursor[1] * G})`}
               dangerouslySetInnerHTML={{ __html: library.kinds[tool.kind].svg }} />
          )}
        </svg>
      </div>

      <BoardIsland className="top-3 left-3 p-1">{topLeft}</BoardIsland>
      <Toolbar current={tool} libraryOpen={libraryOpen}
               onTool={(next) => { setTool(next); setDraft(null); focusBoard(); }}
               onLibrary={() => (libraryOpen ? setLibraryOpen(false) : openLibrary())} />
      {libraryOpen && (
        <LibraryPanel library={library} chosen={tool.type === "place" ? tool.kind : undefined} onChoose={choose}
                      onClose={(backToBoard) => { setLibraryOpen(false); if (backToBoard) focusBoard(); }} />
      )}
      <BoardIsland className="top-3 right-3">{topRight}</BoardIsland>
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
          icon={selectedElement ? <SymbolIcon kind={selectedElement.kind} library={library} /> : null}
        />
      )}
      {lost && (
        // the drawing is out of view: a way back, bottom centre (like Excalidraw's "scroll back to content")
        <button className={cn(boardIsland(), "bottom-3 left-1/2 -translate-x-1/2 gap-2 px-3.5 py-2 border border-transparent text-[14px] font-medium text-fg hover:bg-selected")}
                onClick={() => setCam(fitted())}>
          <Target /> {t("view.back")}
        </button>
      )}
      <ZoomAndHistory zoom={cam.zoom} onZoom={(f) => zoomAround(f)} onFit={() => setCam(fitted())} onUndo={undoStep} onRedo={redo} />
      {status && (
        // what is wrong with the circuit: always shown, next to the full screen button
        <BoardIsland stays className="bottom-3 right-26 mr-1.5 border border-line text-[13px] text-muted whitespace-nowrap">{status}</BoardIsland>
      )}
      <ScreenAndHelp full={full} onFull={() => setFull((f) => !f)} onHelp={() => setHelp((h) => !h)} />
      {help && <HelpPanel />}
    </div>
  );
}
