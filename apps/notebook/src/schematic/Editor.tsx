// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
//
// The canvas is drawn 1:1 (one grid unit = library.grid px) from a fixed origin and only
// grows to the right/bottom, so nothing ever jumps under the cursor.
import { useEffect, useId, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { Help, Minus, Plus, Pointer, Redo, Undo, WireIcon } from "../icons";
import type { ElementData, ElementResult, Point, SchematicData, SymbolLibrary, WireData } from "../types";
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
  results?: Record<string, ElementResult>; // from "Symuluj", drawn next to the elements
  topLeft?: ReactNode;
  topRight?: ReactNode;
}

const clampZoom = (z: number) => Math.min(2.5, Math.max(0.4, z));

const MIN_W = 30;
const MIN_H = 15;
const HISTORY = 100;

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
  const scrollRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [help, setHelp] = useState(false);
  const [panning, setPanning] = useState(false);
  const pan = useRef<{ x: number; y: number; left: number; top: number } | null>(null);

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
    else if ((event.key === "v" || event.key === "V") && !mod) { setTool({ type: "select" }); setDraft(null); }
    else if ((event.key === "w" || event.key === "W") && !mod) setTool({ type: "wire" });
    else if (/^[0-9]$/.test(event.key) && !mod) {
      const k = KINDS[(Number(event.key) + 9) % 10];
      if (k) { setTool({ type: "place", kind: k.kind }); setDraft(null); }
    }
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
    : "Przeciągnij element, żeby go przesunąć · od końcówki, żeby poprowadzić przewód · R obraca · spacja + przeciągnij przesuwa widok";

  const tools: { tool: Tool; label: string; key: string; icon: ReactNode }[] = [
    { tool: { type: "select" }, label: "Zaznacz", key: "V", icon: <Pointer /> },
    { tool: { type: "wire" }, label: "Przewód", key: "W", icon: <WireIcon /> },
    ...KINDS.map((k, i) => ({
      tool: { type: "place", kind: k.kind } as Tool,
      label: k.name,
      key: i < 10 ? String((i + 1) % 10) : "",
      icon: isComponent(k.kind) || k.kind === "ground"
        ? (
          <svg viewBox={k.kind === "ground" ? "-14 -4 28 26" : "-6 -26 92 52"} width="30" height="22" className="tool-symbol">
            <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[k.kind].svg }} />
          </svg>
        )
        : <span className="tool-text">A</span>,
    })),
  ];
  const isActive = (t: Tool) => t.type === tool.type && (t.type !== "place" || (tool.type === "place" && t.kind === tool.kind));

  return (
    <div
      className={`board ${panning ? "panning" : ""}`}
      // tall enough for the drawing plus the islands above and below it (the rest scrolls)
      style={{ height: Math.min(720, Math.max(380, (maxY + MARGIN) * G * zoom + 150)) }}
    >
      <div
        className="board-scroll"
        ref={scrollRef}
        onWheel={(event) => {
          if (!(event.ctrlKey || event.metaKey)) return;
          event.preventDefault();
          setZoom((z) => clampZoom(z * (event.deltaY < 0 ? 1.1 : 1 / 1.1)));
        }}
      >
        <svg
          ref={svgRef}
          className={`canvas tool-${tool.type} ${wiring ? "wiring" : ""}`}
          viewBox={`0 0 ${width * G} ${height * G}`}
          width={width * G * zoom}
          height={height * G * zoom}
          tabIndex={0}
          onPointerDown={(event) => {
            if (panning) {
              const el = scrollRef.current!;
              pan.current = { x: event.clientX, y: event.clientY, left: el.scrollLeft, top: el.scrollTop };
              svgRef.current?.setPointerCapture(event.pointerId);
              return;
            }
            onCanvasDown(event);
          }}
          onPointerMove={(event) => {
            if (pan.current) {
              const el = scrollRef.current!;
              el.scrollLeft = pan.current.left - (event.clientX - pan.current.x);
              el.scrollTop = pan.current.top - (event.clientY - pan.current.y);
              return;
            }
            onMove(event);
          }}
          onPointerUp={() => { pan.current = null; onUp(); }}
          onPointerLeave={() => setCursor(null)}
          onDoubleClick={() => { if (draft) { addWire(draft); setDraft(null); } }}
          onKeyDown={(event) => {
            if (event.key === " ") { setPanning(true); event.preventDefault(); return; }
            onKey(event);
          }}
          onKeyUp={(event) => { if (event.key === " ") setPanning(false); }}
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
            <ElementView key={e.id} element={e} library={library} wires={value.wires} result={results?.[e.id]}
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

      <div className="island top-left no-print">{topLeft}</div>
      <div className="island tools no-print" role="toolbar">
        {tools.map(({ tool: t, label, key, icon }, i) => (
          <button
            key={label}
            className={`tool ${isActive(t) ? "active" : ""} ${i === 1 ? "sep-after" : ""}`}
            title={`${label}${key ? ` (${key})` : ""}`}
            aria-label={label}
            onClick={() => { setTool(t); setDraft(null); svgRef.current?.focus({ preventScroll: true }); }}
          >
            {icon}
            {key && <span className="key">{key}</span>}
          </button>
        ))}
      </div>
      <div className="board-hint no-print">{hint}</div>
      <div className="island top-right no-print">{topRight}</div>
      {(selectedElement || selection?.type === "wire") && (
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
        <button className="icon" title="Pomniejsz" aria-label="Pomniejsz" onClick={() => setZoom((z) => clampZoom(z / 1.2))}><Minus /></button>
        <button className="zoom" title="100%" onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
        <button className="icon" title="Powiększ" aria-label="Powiększ" onClick={() => setZoom((z) => clampZoom(z * 1.2))}><Plus /></button>
        <span className="sep" />
        <button className="icon" title="Cofnij (Ctrl/Cmd+Z)" aria-label="Cofnij" onClick={undo}><Undo /></button>
        <button className="icon" title="Ponów (Ctrl/Cmd+Shift+Z)" aria-label="Ponów" onClick={redo}><Redo /></button>
      </div>
      <div className="island bottom-right no-print">
        <button className="icon" title="Skróty klawiszowe" aria-label="Pomoc" onClick={() => setHelp((h) => !h)}><Help /></button>
      </div>
      {help && (
        <div className="island help-panel no-print">
          <h4>Skróty</h4>
          <dl>
            <dt>V</dt><dd>zaznacz / przesuń</dd>
            <dt>W</dt><dd>przewód</dd>
            <dt>1–0</dt><dd>elementy z paska</dd>
            <dt>R</dt><dd>obróć o 90° (dwa razy = odwróć)</dd>
            <dt>Del</dt><dd>usuń zaznaczone</dd>
            <dt>Esc</dt><dd>przerwij / odznacz</dd>
            <dt>⌘/Ctrl Z</dt><dd>cofnij (⇧ — ponów)</dd>
            <dt>spacja</dt><dd>+ przeciągnij: przesuń widok</dd>
            <dt>⌘/Ctrl kółko</dt><dd>powiększenie</dd>
          </dl>
          <p>Czerwona kropka = zacisk niepodłączony. Przewody łączą się tylko końcami.</p>
        </div>
      )}
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
