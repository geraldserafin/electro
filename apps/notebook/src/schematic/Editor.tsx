// Grid editor for a schematic cell. Symbols come from the Python symbol library,
// so the editor and the rendered report look the same.
import { useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import type { ElementData, Point, SchematicData, SymbolLibrary } from "../types";
import {
  KINDS, bounds, hasValue, isComponent, junctions, kindInfo, nextId, pins, same, updateElement,
} from "./model";

type Tool = { type: "select" } | { type: "wire" } | { type: "place"; kind: string };
type Selection = { type: "element"; id: string } | { type: "wire"; index: number } | null;

interface Props {
  value: SchematicData;
  onChange: (value: SchematicData) => void;
  library: SymbolLibrary;
}

const MIN_W = 32;
const MIN_H = 14;
const MARGIN = 3;
const LABEL_ROOM = 6;  // labels sit left of vertical elements

export function SchematicEditor({ value, onChange, library }: Props) {
  const G = library.grid;
  const gridId = useId();  // one <pattern> per editor
  const svgRef = useRef<SVGSVGElement>(null);
  const [tool, setTool] = useState<Tool>({ type: "select" });
  const [selection, setSelection] = useState<Selection>(null);
  const [cursor, setCursor] = useState<Point | null>(null);
  const [draft, setDraft] = useState<Point[] | null>(null);
  const drag = useRef<{ id: string; start: Point; origin: Point; snapshot: SchematicData } | null>(null);

  const [x0, y0, x1, y1] = useMemo(() => {
    const [a, b, c, d] = bounds(value, library);
    const empty = !value.elements.length && !value.wires.length;
    const left = Math.min(empty ? 0 : a - LABEL_ROOM, 0);
    const top = Math.min(empty ? 0 : b - MARGIN, 0);
    return [left, top, Math.max(empty ? 0 : c + MARGIN, left + MIN_W), Math.max(empty ? 0 : d + MARGIN, top + MIN_H)];
  }, [value, library]);

  const toGrid = (event: { clientX: number; clientY: number }): Point => {
    const svg = svgRef.current!;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM()!.inverse());
    return [Math.round(point.x / G), Math.round(point.y / G)];
  };

  const selectedElement =
    selection?.type === "element" ? value.elements.find((e) => e.id === selection.id) ?? null : null;

  const change = (id: string, patch: Partial<ElementData>) => onChange(updateElement(value, library, id, patch));

  const remove = () => {
    if (selection?.type === "element")
      onChange({ ...value, elements: value.elements.filter((e) => e.id !== selection.id) });
    if (selection?.type === "wire") onChange({ ...value, wires: value.wires.filter((_, i) => i !== selection.index) });
    setSelection(null);
  };

  const finishWire = () => {
    if (draft && draft.length >= 2) onChange({ ...value, wires: [...value.wires, { points: draft }] });
    setDraft(null);
  };

  const onBackgroundDown = (event: ReactPointerEvent) => {
    const p = toGrid(event);
    if (tool.type === "place") {
      const element: ElementData = {
        id: nextId(value, tool.kind), kind: tool.kind, at: p, rotation: 0,
        value: null, text: tool.kind === "label" ? "A" : null,
      };
      onChange({ ...value, elements: [...value.elements, element] });
      setSelection({ type: "element", id: element.id });
      setTool({ type: "select" });
    } else if (tool.type === "wire") {
      if (!draft) setDraft([p]);
      else {
        const last = draft[draft.length - 1];
        if (same(last, p)) finishWire();
        else setDraft([...draft, ...(last[0] !== p[0] && last[1] !== p[1] ? [[p[0], last[1]] as Point] : []), p]);
      }
    } else setSelection(null);
  };

  const onElementDown = (event: ReactPointerEvent, e: ElementData) => {
    if (tool.type !== "select") return;
    event.stopPropagation();
    setSelection({ type: "element", id: e.id });
    drag.current = { id: e.id, start: toGrid(event), origin: e.at, snapshot: value };
    svgRef.current?.setPointerCapture(event.pointerId);
  };

  const onMove = (event: ReactPointerEvent) => {
    const p = toGrid(event);
    setCursor(p);
    const d = drag.current;
    if (d) {
      const at: Point = [d.origin[0] + p[0] - d.start[0], d.origin[1] + p[1] - d.start[1]];
      onChange(updateElement(d.snapshot, library, d.id, { at }));
    }
  };

  const onKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      setDraft(null);
      setTool({ type: "select" });
    } else if (event.key === "Enter") finishWire();
    else if ((event.key === "r" || event.key === "R") && selectedElement)
      change(selectedElement.id, { rotation: (selectedElement.rotation + 90) % 360 });
    else if ((event.key === "Delete" || event.key === "Backspace") && selection) remove();
    else return;
    event.preventDefault();
  };

  const preview: Point[] | null =
    draft && cursor
      ? [...draft, ...(draft[draft.length - 1][0] !== cursor[0] ? [[cursor[0], draft[draft.length - 1][1]] as Point] : []), cursor]
      : null;

  return (
    <div className="schematic-editor">
      <div className="palette no-print">
        <button className={tool.type === "select" ? "active" : ""} onClick={() => setTool({ type: "select" })}>
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
            onClick={() => setTool({ type: "place", kind: k.kind })}
          >
            {isComponent(k.kind) ? (
              <svg viewBox="-6 -24 92 48" width="46" height="24" className="palette-icon">
                <g className="w" dangerouslySetInnerHTML={{ __html: library.kinds[k.kind].svg }} />
              </svg>
            ) : k.name}
          </button>
        ))}
      </div>
      <div className="editor-body">
        <svg
          ref={svgRef}
          className={`canvas tool-${tool.type}`}
          viewBox={`${x0 * G} ${y0 * G} ${(x1 - x0) * G} ${(y1 - y0) * G}`}
          tabIndex={0}
          onPointerDown={onBackgroundDown}
          onPointerMove={onMove}
          onPointerUp={() => (drag.current = null)}
          onPointerLeave={() => setCursor(null)}
          onDoubleClick={finishWire}
          onKeyDown={onKey}
        >
          <style>{library.style}</style>
          <defs>
            <pattern id={gridId} width={G} height={G} patternUnits="userSpaceOnUse" x={-G / 2} y={-G / 2}>
              <circle cx={G / 2} cy={G / 2} r="1" className="grid-dot" />
            </pattern>
          </defs>
          <rect className="grid no-print" x={x0 * G} y={y0 * G} width={(x1 - x0) * G} height={(y1 - y0) * G} fill={`url(#${CSS.escape(gridId)})`} />

          {value.wires.map((w, i) => (
            <g key={i}>
              <polyline
                className={`w wire ${selection?.type === "wire" && selection.index === i ? "selected" : ""}`}
                points={w.points.map(([x, y]) => `${x * G},${y * G}`).join(" ")}
              />
              <polyline
                className="hit"
                points={w.points.map(([x, y]) => `${x * G},${y * G}`).join(" ")}
                onPointerDown={(event) => {
                  if (tool.type !== "select") return;
                  event.stopPropagation();
                  setSelection({ type: "wire", index: i });
                }}
              />
            </g>
          ))}
          {junctions(value, library).map(([x, y]) => (
            <circle key={`${x},${y}`} className="dot" cx={x * G} cy={y * G} r="3" />
          ))}
          {value.elements.map((e) => (
            <ElementView
              key={e.id}
              element={e}
              library={library}
              selected={selection?.type === "element" && selection.id === e.id}
              onPointerDown={(event) => onElementDown(event, e)}
            />
          ))}
          {preview && (
            <polyline className="w draft" points={preview.map(([x, y]) => `${x * G},${y * G}`).join(" ")} />
          )}
          {tool.type === "place" && cursor && (
            <g className="w ghost" transform={`translate(${cursor[0] * G} ${cursor[1] * G})`}
               dangerouslySetInnerHTML={{ __html: library.kinds[tool.kind].svg }} />
          )}
        </svg>
        {selectedElement && (
          <Inspector
            key={selectedElement.id}
            element={selectedElement}
            taken={value.elements.map((e) => e.id)}
            onChange={(patch) => change(selectedElement.id, patch)}
            onRename={(id) => {
              onChange({ ...value, elements: value.elements.map((e) => (e.id === selectedElement.id ? { ...e, id } : e)) });
              setSelection({ type: "element", id });
            }}
            onRemove={remove}
          />
        )}
      </div>
      <p className="hint no-print">
        Klik na symbolu w pasku, potem na siatce — stawia element. Przeciągnij, żeby przesunąć (przewody idą za nim).
        <kbd>R</kbd> obraca, <kbd>Del</kbd> usuwa. Przewód: klikaj kolejne punkty, dwuklik albo <kbd>Enter</kbd> kończy.
      </p>
    </div>
  );
}

function Label({ text, x, y, anchor }: { text: string; x: number; y: number; anchor: "middle" | "end" }) {
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

function ElementView({ element: e, library, selected, onPointerDown }: {
  element: ElementData; library: SymbolLibrary; selected: boolean; onPointerDown: (event: ReactPointerEvent) => void;
}) {
  const G = library.grid;
  const symbol = library.kinds[e.kind];
  const ps = pins(e, library).map(([x, y]) => [x * G, y * G] as Point);
  const cx = ps.reduce((s, p) => s + p[0], 0) / ps.length;
  const cy = ps.reduce((s, p) => s + p[1], 0) / ps.length;
  const xs = ps.map((p) => p[0]);
  const ys = ps.map((p) => p[1]);
  const vertical = e.rotation % 180 !== 0;
  const unit = kindInfo(e.kind)?.unit ?? "";
  const label = e.kind === "label" ? e.text ?? ""
    : !isComponent(e.kind) ? ""
    : hasValue(e.kind) ? `${e.id} = ${e.value ?? "?"}${e.value && /\d$/.test(e.value) ? ` ${unit}` : ""}`
    : e.id;
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
        : <Label text={label} x={vertical ? cx - 20 : cx} y={vertical ? cy + 4 : cy - 20} anchor={vertical ? "end" : "middle"} />)}
    </g>
  );
}

function Inspector({ element, taken, onChange, onRename, onRemove }: {
  element: ElementData;
  taken: string[];
  onChange: (patch: Partial<ElementData>) => void;
  onRename: (id: string) => void;
  onRemove: () => void;
}) {
  const [id, setId] = useState(element.id);
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
        <button onClick={() => onChange({ rotation: (element.rotation + 90) % 360 })}>Obróć (R)</button>
        <button className="danger" onClick={onRemove}>Usuń</button>
      </div>
    </div>
  );
}
