// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
//
// The canvas is drawn 1:1 (one grid unit = library.grid px) from a fixed origin and only
// grows to the right/bottom, so nothing ever jumps under the cursor.
import { useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { ElementData, Point, SchematicData, SymbolLibrary, WireData } from "../types";
import {
  KINDS, MARGIN, attach, bounds, elbow, hasValue, isComponent, isConnectionPoint, junctions, kindInfo, nextId, normalized,
  moveSegment, openPins, pins, rotatedAbout, same, simplify, updateElement,
} from "./model";

type Tool = { type: "select" } | { type: "wire" } | { type: "place"; kind: string };
type Selection = { type: "element"; id: string } | { type: "wire"; index: number } | null;
type Gesture =
  | { type: "move"; id: string; start: Point; origin: Point; snapshot: SchematicData; moved: boolean }
  | { type: "wire"; from: Point }
  | { type: "segment"; wire: number; index: number; start: Point; snapshot: SchematicData; moved: boolean };

interface Props {
  value: SchematicData;
  onChange: (value: SchematicData) => void;
  library: SymbolLibrary;
}

const MIN_W = 30;
const MIN_H = 15;
const HISTORY = 100;

export function SchematicEditor({ value, onChange, library }: Props) {
  const G = library.grid;
  const gridId = useId();
  const svgRef = useRef<SVGSVGElement>(null);
  const [tool, setTool] = useState<Tool>({ type: "select" });
  const [selection, setSelection] = useState<Selection>(null);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Point[] | null>(null);
  const [gesture, setGesture] = useState<Gesture | null>(null);
  const history = useRef<{ past: SchematicData[]; future: SchematicData[] }>({ past: [], future: [] });

  // drawings made elsewhere (auto-layout, files) may start at negative coordinates
  useEffect(() => {
    const moved = normalized(value, library);
    if (moved !== value) onChange(moved);
  }, [value, library, onChange]);

  const [, , maxX, maxY] = bounds(value, library);
  const width = Math.max(MIN_W, maxX + 8);
  const height = Math.max(MIN_H, maxY + 6);

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

  /** Keep every pin at least MARGIN grid units inside the canvas. */
  const clamped = (e: ElementData): ElementData => {
    const ps = pins(e, library);
    const dx = Math.max(0, MARGIN - Math.min(...ps.map((p) => p[0])));
    const dy = Math.max(0, MARGIN - Math.min(...ps.map((p) => p[1])));
    return dx || dy ? { ...e, at: [e.at[0] + dx, e.at[1] + dy] } : e;
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
    // no clamping here: that would shift the element off its middle and 180° would not land
    // back on the wires; near the edge the whole drawing is shifted instead (normalized)
    const at = rotatedAbout(selectedElement, library, rotation);
    commit({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, rotation, at } : e)) });
  };

  const removeSelected = () => {
    if (selection?.type === "element")
      commit({ ...value, elements: value.elements.filter((e) => e.id !== selection.id) });
    if (selection?.type === "wire") commit({ ...value, wires: value.wires.filter((_, i) => i !== selection.index) });
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
      const element = clamped({
        id: nextId(value, tool.kind), kind: tool.kind, at: p, rotation: 0,
        value: null, text: tool.kind === "label" ? "A" : null,
      });
      commit(attach({ ...value, elements: [...value.elements, element] }, library, element.id));
      setSelection({ type: "element", id: element.id });
      setTool({ type: "select" });
    } else if (tool.type === "wire") addDraftPoint(p);
    else setSelection(null);
  };

  const onElementDown = (event: ReactPointerEvent, e: ElementData) => {
    if (tool.type !== "select") return;
    event.stopPropagation();
    svgRef.current?.focus({ preventScroll: true });
    setSelection({ type: "element", id: e.id });
    setGesture({ type: "move", id: e.id, start: toGrid(event), origin: e.at, snapshot: value, moved: false });
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
      const at = clamped({ ...e, at: [gesture.origin[0] + p[0] - gesture.start[0], gesture.origin[1] + p[1] - gesture.start[1]] }).at;
      if (!same(at, value.elements.find((x) => x.id === gesture.id)!.at)) {
        onChange(updateElement(gesture.snapshot, library, gesture.id, { at }));
        if (!gesture.moved) setGesture({ ...gesture, moved: true });
      }
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
    if (gesture?.type === "wire" && cursor && !same(cursor, gesture.from)) addWire(elbow(gesture.from, cursor));
    setGesture(null);
  };

  const onKey = (event: React.KeyboardEvent) => {
    const mod = event.metaKey || event.ctrlKey;
    if (mod && event.key.toLowerCase() === "z") (event.shiftKey ? redo : undo)();
    else if (mod && event.key.toLowerCase() === "y") redo();
    else if (event.key === "Escape") {
      if (draft) setDraft(null);
      else {
        setTool({ type: "select" });
        setSelection(null);
      }
    } else if (event.key === "Enter" && draft) {
      addWire(draft);
      setDraft(null);
    } else if ((event.key === "r" || event.key === "R") && !mod) rotateSelected();
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

  return (
    <div className="schematic-editor">
      <div className="palette no-print">
        <button className={tool.type === "select" ? "active" : ""} onClick={() => { setTool({ type: "select" }); setDraft(null); }}>
          Zaznacz
        </button>
        <button className={tool.type === "wire" ? "active" : ""} onClick={() => setTool({ type: "wire" })}>
          Przewód
        </button>
        <span className="sep" />
        {KINDS.map((k) => (
          <button
            key={k.kind}
            title={k.name}
            className={tool.type === "place" && tool.kind === k.kind ? "active" : ""}
            onClick={() => { setTool({ type: "place", kind: k.kind }); setDraft(null); }}
          >
            {isComponent(k.kind) ? (
              <svg viewBox="-6 -24 92 48" width="46" height="24" className="palette-icon">
                <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[k.kind].svg }} />
              </svg>
            ) : k.name}
          </button>
        ))}
        <span className="sep" />
        <button onClick={undo} title="Cofnij (Ctrl/Cmd+Z)">↶</button>
        <button onClick={redo} title="Ponów (Ctrl/Cmd+Shift+Z)">↷</button>
      </div>
      <div className="editor-body">
        <div className="canvas-scroll">
          <svg
            ref={svgRef}
            className={`canvas tool-${tool.type} ${wiring ? "wiring" : ""}`}
            viewBox={`0 0 ${width * G} ${height * G}`}
            width={width * G}
            height={height * G}
            tabIndex={0}
            onPointerDown={onCanvasDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            onPointerLeave={() => setCursor(null)}
            onDoubleClick={() => { if (draft) { addWire(draft); setDraft(null); } }}
            onKeyDown={onKey}
          >
            <style>{library.style}</style>
            <defs>
              <pattern id={gridId} width={G} height={G} patternUnits="userSpaceOnUse" x={-G / 2} y={-G / 2}>
                <circle cx={G / 2} cy={G / 2} r="1" className="grid-dot" />
              </pattern>
            </defs>
            <rect className="grid no-print" width={width * G} height={height * G} fill={`url(#${CSS.escape(gridId)})`} />

            {value.wires.map((w, i) => (
              <g key={i}>
                <polyline className={`w wire ${selection?.type === "wire" && selection.index === i ? "selected" : ""}`}
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
              <ElementView key={e.id} element={e} library={library} wires={value.wires}
                           selected={selection?.type === "element" && selection.id === e.id}
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
            {snap && <circle className="snap" cx={snap[0] * G} cy={snap[1] * G} r="7" />}
            {tool.type === "place" && cursor && (
              <g className="w ghost" transform={`translate(${cursor[0] * G} ${cursor[1] * G})`}
                 dangerouslySetInnerHTML={{ __html: library.kinds[tool.kind].svg }} />
            )}
          </svg>
        </div>
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
      </div>
    </div>
  );
}

/** The text next to an element: "R_1 = 100 Ω", "A_1", or a net label's name. */
function label_(e: ElementData): string {
  const unit = kindInfo(e.kind)?.unit ?? "";
  if (e.kind === "label") return e.text ?? "";
  if (!isComponent(e.kind)) return "";
  if (!hasValue(e.kind)) return e.id;
  return `${e.id} = ${e.value ?? "?"}${e.value && /\d$/.test(e.value) ? ` ${unit}` : ""}`;
}

function Label({ text, x, y, anchor }: { text: string; x: number; y: number; anchor: "middle" | "end" | "start" }) {
  const parts = text.match(/^([A-Za-z]+)_(\w+)(.*)$/);
  return (
    <text x={x} y={y} textAnchor={anchor} className="label">
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

function ElementView({ element: e, library, wires, selected, onPointerDown }: {
  element: ElementData; library: SymbolLibrary; wires: WireData[]; selected: boolean;
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
  // …or unless it would not fit on the canvas (which starts at 0, 0)
  const flip = vertical
    ? (crosses(cx - 20 - labelWidth, cx - 20, cy - 8, cy + 8) || cx - 20 - labelWidth < 0)
      && !crosses(cx + 20, cx + 20 + labelWidth, cy - 8, cy + 8)
    : (crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy - 32, cy - 16) || cy - 32 < 0)
      && !crosses(cx - labelWidth / 2, cx + labelWidth / 2, cy + 16, cy + 32);
  const label = label_(e);
  return (
    <g className={`element ${selected ? "selected" : ""}`} onPointerDown={onPointerDown}>
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
          ? <Label text={label} x={flip ? cx + 20 : cx - 20} y={cy + 4} anchor={flip ? "start" : "end"} />
          : <Label text={label} x={cx} y={flip ? cy + 30 : cy - 20} anchor="middle" />)}
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
  if (selection?.type === "wire")
    return (
      <div className="inspector no-print">
        <h4>Przewód</h4>
        <button className="danger" onClick={onRemove}>Usuń (Del)</button>
      </div>
    );
  if (!element)
    return (
      <div className="inspector no-print help">
        <h4>Jak rysować</h4>
        <ol>
          <li>Kliknij symbol na pasku, potem miejsce na siatce.</li>
          <li><b>Połącz:</b> przeciągnij od końcówki elementu do drugiej końcówki (albo narzędzie <i>Przewód</i>: klikaj kolejne punkty).</li>
          <li>Czerwona kropka = zacisk jeszcze niepodłączony.</li>
          <li>Przeciągnij element, żeby go przesunąć — przewody idą za nim. Odcinek przewodu też można przeciągnąć.</li>
          <li>Obrót nie rusza przewodów: po 90° trzeba podłączyć na nowo, dwa obroty (180°) odwracają element w miejscu.</li>
        </ol>
        <p><kbd>R</kbd> obrót · <kbd>Del</kbd> usuń · <kbd>Esc</kbd> przerwij · <kbd>⌘/Ctrl Z</kbd> cofnij</p>
      </div>
    );
  const info = kindInfo(element.kind);
  const commitId = () => {
    const clean = id.trim();
    if (clean && clean !== element.id && !taken.includes(clean)) onRename(clean);
    else setId(element.id);
  };
  return (
    <div className="inspector no-print">
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
          Wartość {info?.unit && <small>({info.unit}; puste = niewiadoma, litera = symbol)</small>}
          <input value={element.value ?? ""} placeholder="?"
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
