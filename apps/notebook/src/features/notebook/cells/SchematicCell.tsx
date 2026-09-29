import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { usePdf } from "@/features/pdf-export";
import { kernel } from "@/features/python";
import { canRunInTime, inTimeOnly, PdfDrawing, SchematicEditor, updateElement, type Camera } from "@/features/schematic";
import { LiveControls, ProbePanel, SimPanel, SketchEditor, UploadButton, useLive } from "@/features/simulation";
import type { Cell, SchematicData, SymbolLibrary } from "@/shared/model/types";
import type { Failure } from "@/shared/model/issues";
import { FailureBox } from "@/features/solution";
import { Close, CodeIcon, Expand, Flash, SchematicIcon, Shrink } from "@/shared/ui/icons";
import { cn } from "@/shared/lib/cn";
import { Sash, useKeptSize } from "@/shared/ui/Splitter";
import { barButton, RunButton } from "./CellBar";
import { CodeEditor } from "./CodeEditor";
import { runOnShiftEnter } from "./CodeCell";
import { clean, close, dock, flat, initial, moveFlat, moveTo, open, resize, split, type Layout, type Side } from "./layout";
import { variableName } from "./NameBox";
import { Problems } from "./Problems";
import { ResultsTable } from "./ResultsTable";

const Stop = () => (
  <svg viewBox="0 0 24 24" width={14} height={14} aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" /></svg>
);

const BAR = "flex items-stretch h-9 flex-none border-b border-line bg-board"; // a tab bar (an editor group's)
const CODE_HEIGHT = 160; // px of code at least, in the notebook

/**
 * Where a dragged tab would land: in a group's bar before the tab at `at` ("tab"); on what a group
 * shows, its middle (a tab there, last) or an outer edge (a split, or that side); `box`: what to light.
 */
type Drop = { group: number; zone: Side | "middle" | "tab"; at?: number; box: { top: number; left: number; width: number; height: number } };

/** A file's tab: click to show it, drag it elsewhere, × (in a split) to send it back to the first group; the drawing's renames on a click once shown. */
function Tab({ id, label, icon, on, title, ariaLabel, onPick, onClose, onDrag, onRename, name }: {
  id: string; label: string; icon: ReactNode; on: boolean; title?: string; ariaLabel?: string;
  onPick: () => void; onClose?: () => void;
  onDrag: (id: string, label: string, e: ReactPointerEvent<HTMLElement>) => void;
  onRename?: (name: string) => void; name?: string; // the drawing's tab: its name, editable
}) {
  const { t } = useTranslation("notebook");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name ?? "");
  const commit = () => {
    setEditing(false);
    if (onRename && draft.trim() && draft.trim() !== name) onRename(draft.trim());
  };
  const look = cn("group/tab relative flex flex-none items-center gap-1.5 pl-3 pr-1.5 border-r border-line text-[13px] whitespace-nowrap select-none",
    on ? "bg-code-bg text-fg shadow-[inset_0_2px_0_var(--accent)]" : "bg-board text-muted hover:text-fg");
  if (editing)
    return (
      <span className={look}>
        {icon}
        <input autoFocus value={draft} spellCheck={false} aria-label={t("schematic.name")}
               className="w-36 bg-transparent outline-none" onChange={(e) => setDraft(e.target.value)} onBlur={commit}
               onKeyDown={(e) => {
                 if (e.key === "Enter") commit();
                 if (e.key === "Escape") { e.preventDefault(); setDraft(name ?? ""); setEditing(false); } // not full screen's
               }} />
        <small className="pr-1.5 text-[11px] text-faint">{t("schematic.inCode")} <code className="font-mono text-fg">{variableName(draft)}</code></small>
      </span>
    );
  return (
    <div role="tab" data-file={id} tabIndex={0} aria-selected={on} aria-label={ariaLabel} title={title} className={cn(look, "cursor-pointer touch-none")}
         onPointerDown={(e) => onDrag(id, label, e)}
         onClick={() => (on && onRename ? (setDraft(name ?? ""), setEditing(true)) : onPick())}
         onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(); } }}>
      {icon}
      <span className={cn(id !== "board" && "font-mono")}>{label}</span>
      {onClose ? (
        <button className={cn("inline-flex items-center justify-center size-5 rounded text-muted hover:bg-selected hover:text-fg [&_svg]:size-3.5",
                              on ? "opacity-100" : "opacity-0 group-hover/tab:opacity-100 focus-visible:opacity-100")}
                onPointerDown={(e) => e.stopPropagation()} onClick={(e) => { e.stopPropagation(); onClose(); }}
                title={t("tab.close")} aria-label={t("tab.close")}>
          <Close />
        </button>
      ) : <span className="w-1.5" />}
    </div>
  );
}

/**
 * A schematic, as an IDE shows files: the drawing (the board) is one of them, the circuit's code
 * and each Arduino's sketch the others. Editor groups side by side — each its tab bar, one file
 * shown — split by dragging a tab to a group's edge, resized by the lines between them. Every file
 * always has a tab: the first group holds those not split off; a split's tab closed goes back
 * there. The simulation's panel under the groups. The same in the notebook and full screen (then
 * the whole window). The element library is the board's own, docked beside it.
 *
 * A drawing with a non-linear element (a diode, an Arduino…) cannot be solved on paper, only run
 * in time: then the bolt runs it.
 */
export function SchematicCell({ cell, update, library, simulate, running: solving }: {
  cell: Extract<Cell, { type: "schematic" }>;
  update: (patch: Partial<Cell>) => void;
  library: SymbolLibrary;
  simulate: (schematic?: SchematicData) => void;
  running: boolean;
}) {
  const { t } = useTranslation("notebook");
  const { t: ts } = useTranslation("simulation");
  const { t: tk } = useTranslation("schematic");
  const empty = !cell.schematic.elements.length;
  const pdf = usePdf();
  const printed = pdf.results && !cell.stale ? cell.results : undefined; // values on the drawing, if the PDF has them
  // the circuit's code: `generated` is the drawing as code, `source` what is in the editor now
  const [source, setSource] = useState<string | null>(null);
  const [generated, setGenerated] = useState<string | null>(null);
  const [error, setError] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const live = useLive(cell.schematic);
  const running = live.status === "running" || live.status === "paused";
  const timed = inTimeOnly(cell.schematic); // only in time: the bolt runs it
  const arduinos = cell.schematic.elements.filter((e) => e.kind === "arduino");
  const pressed = useRef<string[]>([]);
  const [pressedIds, setPressedIds] = useState<string[]>([]);
  const [dismissed, setDismissed] = useState<unknown>(null); // the problems hidden (that very list)
  const sketchOf = (id: string | null) => arduinos.find((e) => e.id === id) ?? null;
  const setSketchText = (id: string, text: string) => update({
    schematic: { ...cell.schematic, elements: cell.schematic.elements.map((x) => (x.id === id ? { ...x, text } : x)) },
  });

  // ------------------------------------------------------------------ files and groups

  const files = ["board", "circuit", ...arduinos.map((e) => e.id)];
  const labelOf = (id: string) => (id === "board" ? cell.name : id === "circuit" ? `${variableName(cell.name)}.py` : `${id}.ino`);
  const iconOf = (id: string) => (id === "board" ? <SchematicIcon /> : <CodeIcon />);
  // the layout is this browser's, kept per cell (a reload keeps it); the file keeps what shows first
  const kept = `electro.layout.${cell.id}`;
  const [layoutState, setLayoutState] = useState<Layout>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(kept) ?? "null") as Layout | null;
      if (saved?.groups?.length) return saved;
    } catch { /* none, or not ours */ }
    return initial(files, cell.view === "code");
  });
  const layout = clean(layoutState, files);
  const setLayout = (next: Layout) => {
    setLayoutState(next);
    try { localStorage.setItem(kept, JSON.stringify(next)); } catch { /* private window */ }
    // the note keeps whether the drawing or its code shows (what opens first elsewhere)
    const view = next.groups.some((g) => g.active === "board") ? "schematic" : "code";
    if ((cell.view ?? "schematic") !== view) update({ view });
  };
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const full = params.get("board") === cell.id;
  // what shows: the split is for full screen; in the notebook one bar, every tab on it
  const viewOf = (l: Layout) => (full ? l : flat(l));
  const view = viewOf(layout);
  const shown = (id: string) => view.groups.some((g) => g.active === id);
  const circuitShown = shown("circuit");

  // full screen is in the address (?board=<cell>): back leaves it, a reload keeps it
  const setFull = (on: boolean) => {
    if (on === full) return;
    if (on) return setParams((p) => { p.set("board", cell.id); return p; }, { state: { board: cell.id } });
    // opened here: going back is leaving (a reload keeps the entry's state); else the address drops it
    if ((location.state as { board?: string } | null)?.board === cell.id) navigate(-1);
    else setParams((p) => { p.delete("board"); return p; }, { replace: true });
  };

  const [panelHeight, setPanelHeight] = useKeptSize("electro.panelHeight");
  const frame = useRef<HTMLDivElement>(null);
  // running out of view: the circuit goes on, the board is not drawn
  const { setOnScreen } = live;
  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setOnScreen(entry.isIntersecting), { rootMargin: "200px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [setOnScreen]);
  const groupEls = useRef<(HTMLElement | null)[]>([]);
  // the notebook: the editor as tall as the drawing needs (fixed after opening, so it never jumps)
  const [height] = useState(() => {
    const ys = [...cell.schematic.elements.map((e) => e.at[1]), ...cell.schematic.wires.flatMap((w) => w.points.map((p) => p[1]))];
    const span = ys.length ? Math.max(...ys) - Math.min(...ys) : 0;
    return Math.min(640, Math.max(440, span * library.grid + 240)) + 36;
  });

  // the drawing `source` describes: the code is written anew only after the drawing was edited
  // on the board — never just because it ran, so the way someone wrote it stays
  const writtenFor = useRef<SchematicData | null>(null);
  // the board's view survives while it is not shown; shown again, the board has the keyboard
  const camera = useRef<Camera | null>(null);
  const focusBoard = useRef(false);

  // full screen: the page behind does not scroll; Escape leaves it (unless something closer took
  // the key: the board steps back one thing at a time, the editor closes its completions)
  useEffect(() => {
    if (!full) return;
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) setFull(false);
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = before;
      window.removeEventListener("keydown", onKey);
    };
  });

  // ------------------------------------------------------------------ the circuit's code

  const load = async () => {
    if (source !== null && writtenFor.current === cell.schematic) return;
    const code = await kernel.code(cell.schematic, cell.name);
    writtenFor.current = cell.schematic;
    setSource(code);
    setGenerated(code);
    setError(null);
  };

  /** The drawing, with the edited code applied (null: the code has an error, shown). */
  const applied = async (): Promise<SchematicData | null> => {
    if (source === null || source === generated) return cell.schematic;
    const back = await kernel.fromCode(source, cell.name, cell.schematic);
    if ("error" in back) {
      setError(back.error);
      return null;
    }
    setError(null);
    writtenFor.current = back.schematic;
    setGenerated(source); // applied: the code in the editor is what the drawing is now
    update({ schematic: back.schematic, ...(cell.results ? { stale: true } : {}) });
    return back.schematic;
  };

  // shown, the code is written from the drawing — and again whenever the drawing changes while
  // nothing typed is waiting; what is typed goes to the drawing a moment after the typing stops
  useEffect(() => {
    if (circuitShown && (source === null || source === generated)) kernel.ready.then(load).catch((e) => setError({ data: String(e) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [circuitShown, cell.schematic]);
  useEffect(() => {
    if (!circuitShown || source === null || source === generated) return;
    const timer = setTimeout(() => void applied().catch((e) => setError({ data: String(e) })), 800);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [circuitShown, source]);

  /** A new layout; leaving the code, what was typed there goes to the drawing first. */
  const go = async (next: Layout) => {
    const hidesCode = circuitShown && !viewOf(next).groups.some((g) => g.active === "circuit");
    if (hidesCode && source !== generated) {
      setBusy(true);
      try {
        if (!(await applied())) return; // the code has an error: it stays, the error under it
      } finally {
        setBusy(false);
      }
    }
    if (!shown("board") && viewOf(next).groups.some((g) => g.active === "board")) focusBoard.current = true;
    setLayout(next);
  };

  const run = async () => {
    if (timed && running) return live.stop();
    setBusy(true);
    try {
      const schematic = await applied();
      if (schematic) (timed ? live.start(schematic) : simulate(schematic));
    } finally {
      setBusy(false);
    }
  };

  // ------------------------------------------------------------------ dragging a tab

  const [drag, setDrag] = useState<{ id: string; label: string; x: number; y: number; drop: Drop | null } | null>(null);
  const dragging = useRef<{ id: string; label: string; x: number; y: number; moved: boolean } | null>(null);

  /** What is under the pointer while `id`'s tab is dragged. */
  const dropAt = (id: string, x: number, y: number): Drop | null => {
    const count = view.groups.length;
    for (let g = 0; g < count; g++) {
      const el = groupEls.current[g];
      if (!el) continue;
      const box = el.getBoundingClientRect();
      if (x < box.left || x > box.right || y < box.top || y > box.bottom) continue;
      const bar = el.querySelector("[data-tab-bar]")!.getBoundingClientRect();
      const body = el.querySelector("[data-group-body]")!.getBoundingClientRect();
      if (y <= bar.bottom) {
        // in a bar: between which tabs (the dragged one left out), a line there
        const others = [...el.querySelectorAll<HTMLElement>("[data-file]")].filter((t) => t.dataset.file !== id).map((t) => t.getBoundingClientRect());
        const at = others.filter((r) => r.left + r.width / 2 < x).length;
        const lineX = at < others.length ? others[at].left : others.length ? others[others.length - 1].right : bar.left;
        return { group: g, zone: "tab", at, box: { top: bar.top, left: lineX - 1, width: 2, height: bar.height } };
      }
      const f = (x - body.left) / body.width;
      if (count < 2) { // one group: its left or right part splits off a new one there
        if (!full) return null; // in the notebook no splits: the bar only (the order of the tabs)
      if (f < 0.3 || f > 0.7) {
          const side: Side = f < 0.3 ? "left" : "right";
          return { group: g, zone: side, box: { top: body.top, height: body.height, width: body.width / 2, left: body.left + (side === "right" ? body.width / 2 : 0) } };
        }
      } else if ((g === 0 && f < 0.25) || (g === count - 1 && f > 0.75)) { // two: an outer edge — that side
        const side: Side = g === 0 ? "left" : "right";
        return { group: g, zone: side, box: body };
      }
      return { group: g, zone: "middle", box: body };
    }
    return null;
  };
  const startDrag = (id: string, label: string, e: ReactPointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    const el = e.currentTarget;
    dragging.current = { id, label, x: e.clientX, y: e.clientY, moved: false };
    const move = (ev: PointerEvent) => {
      const d = dragging.current;
      if (!d) return;
      if (!d.moved && Math.hypot(ev.clientX - d.x, ev.clientY - d.y) < 6) return;
      d.moved = true;
      setDrag({ id, label, x: ev.clientX, y: ev.clientY, drop: dropAt(id, ev.clientX, ev.clientY) });
    };
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      const d = dragging.current;
      dragging.current = null;
      setDrag(null);
      if (!d?.moved) return; // a click: the tab's own
      el.addEventListener("click", (c) => c.stopPropagation(), { capture: true, once: true }); // not a click too
      const drop = dropAt(id, ev.clientX, ev.clientY);
      if (!drop) return;
      void go(drop.zone === "tab" ? (full ? moveTo(layout, id, drop.group, files, drop.at) : moveFlat(layout, id, drop.at ?? 0, files))
        : drop.zone === "middle" ? moveTo(layout, id, drop.group, files)
        : layout.groups.length < 2 ? split(layout, id, drop.group, drop.zone, files)
        : dock(layout, id, drop.zone, files));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  // ------------------------------------------------------------------ what shows

  // the results are up to date: the run button rests until something changes
  const done = cell.results !== undefined && !cell.stale && !(circuitShown && source !== generated);
  // what solving found wrong: not for a circuit that only runs in time (the bolt does not solve it;
  // what is there is from before), and not once hidden, until a run brings a new list
  const problems = !timed && !cell.stale && cell.problems?.length && cell.problems !== dismissed
    ? <Problems problems={cell.problems} below compact onDismiss={() => setDismissed(cell.problems)} /> : null;
  // the bolt: solves the circuit — or runs (and stops) one that only works in time
  const runButton = (
    <RunButton run={run} eager icon={timed && running ? <Stop /> : <Flash />}
               running={timed ? live.status === "starting" : solving || busy}
               done={timed ? empty : done || empty}
               label={timed ? (running ? ts("controls.stop") : ts("controls.startTitle")) : t("schematic.run")} />
  );

  // a button held down (on the board or in the panel): drawn pressed, and closed in the circuit
  const press = (id: string, down: boolean) => {
    pressed.current = down ? [...pressed.current.filter((x) => x !== id), id] : pressed.current.filter((x) => x !== id);
    setPressedIds(pressed.current);
    live.press(id, down);
  };

  const board = (
    <SchematicEditor
      bare
      value={cell.schematic}
      onChange={(schematic) => update({ schematic, ...(cell.results ? { stale: true } : {}) })}
      library={library}
      results={running ? live.frame?.results : cell.stale ? undefined : cell.results}
      live={running && live.frame ? {
        wires: live.frame.wires, pins: live.frame.pins, scale: live.frame.scale, leds: live.frame.leds, looks: live.frame.looks, screens: live.frame.screens, oleds: live.frame.oleds, pressed: pressedIds,
        onPress: press,
      } : undefined}
      // the bolt runs a circuit that only works in time; one that can also be solved has its own
      // way to run in time, here
      // (not offered when it cannot run: a hole in it, a value not given)
      below={empty || running || timed || !canRunInTime(cell.schematic) ? undefined : <LiveControls live={live} />}
      camera={camera}
      autoFocus={focusBoard.current}
      // the meter, while it runs: what an element or a wire is doing
      probe={(target, onClose) => {
        const element = target.type === "element" ? cell.schematic.elements.find((e) => e.id === target.id) : undefined;
        return (
          <ProbePanel live={live} target={target} onClose={onClose}
                      caption={element ? tk(`kinds.${element.kind}.name` as "kinds.resistor.name") : tk("inspector.wire")} title={element?.id} />
        );
      }}
      full={full}
      onFull={setFull}
      // an Arduino's sketch from its inspector: beside the board
      onSketch={(id) => void go(shown(id) || !full ? open(layout, id, files) : split(layout, id, layout.groups.findIndex((g) => g.active === "board"), "right", files))}
    />
  );

  /** What a group shows: the board, the circuit's code or a sketch, filling it. */
  const body = (id: string) =>
    id === "board" ? board
    : id === "circuit" ? (
      <div className="flex flex-col h-full bg-code-bg" onKeyDownCapture={runOnShiftEnter(run)}>
        <div className="flex-1 min-h-0 overflow-auto">
          {source === null
            ? <p className="m-3 text-muted">{t("schematic.toCode")}</p>
            : <CodeEditor value={source} onChange={setSource} fill minHeight={full ? undefined : CODE_HEIGHT} />}
        </div>
        {error && <FailureBox failure={error} className="flex-none m-2 max-h-48 overflow-auto text-[14px]" />}
      </div>
    )
    : <SketchEditor key={id} element={sketchOf(id)!} live={live} fill onChange={(text) => setSketchText(id, text)} />;

  const panel = running && (
    <SimPanel live={live} arduinos={arduinos} elements={cell.schematic.elements} pressed={pressedIds} onPress={press}
              onElement={(id, patch) => update({ schematic: updateElement(cell.schematic, library, id, patch) })}
              full height={full ? panelHeight ?? 260 : 260} />
  );
  const last = view.groups.length - 1;

  return (
    <div>
      <div ref={frame}
           className={cn("flex flex-col overflow-hidden bg-board",
                         full ? "fixed inset-0 z-100" : "rounded-xl border border-line transition-shadow duration-150 group-data-focused/cell:shadow-raised")}>
        <div className="flex min-h-0" style={full ? { flex: "1 1 0" } : { height }}>
          {view.groups.map((g, i) => (
            <div key={i} className="contents">
              {i > 0 && (
                <Sash vertical label={t("tab.resizeGroups")}
                      onDrag={(x) => setLayout(resize(layout, groupEls.current.slice(0, layout.groups.length).map((el) => el?.getBoundingClientRect().width ?? 0),
                                                      i - 1, x - groupEls.current[i - 1]!.getBoundingClientRect().left))} />
              )}
              <section ref={(el) => { groupEls.current[i] = el; }} className="flex flex-col min-w-0 min-h-0"
                       style={{ flex: `${g.size} 1 0px` }} onPointerDownCapture={() => full && layout.focus !== i && setLayoutState({ ...layout, focus: i })}>
                <div data-tab-bar className={BAR}>
                  <div role="tablist" aria-label={ts("code.tabs")} className="flex min-w-0 overflow-x-auto [scrollbar-width:none]">
                    {g.tabs.map((id) => (
                      <Tab key={id} id={id} label={labelOf(id)} icon={iconOf(id)} on={g.active === id}
                           ariaLabel={id === "board" ? `${t("schematic.drawing")}: ${cell.name}` : id === "circuit" ? `${t("schematic.code")}: ${labelOf(id)}` : undefined}
                           title={id === "board" && g.active === id ? t("schematic.nameTitle", { variable: variableName(cell.name) }) : undefined}
                           name={id === "board" ? cell.name : undefined}
                           onRename={id === "board" ? (n) => update({ name: n }) : undefined}
                           onPick={() => void go(open(layout, id, files))}
                           onClose={full && i > 0 ? () => void go(close(layout, id, files)) : undefined}
                           onDrag={startDrag} />
                    ))}
                  </div>
                  <span className="flex-1" />
                  {/* a sketch shown here: compile it; the editor's own (once, at the end of the last bar):
                      what is wrong, the bolt, full screen */}
                  <div className="flex flex-none items-center gap-0.5 pr-1">
                    {sketchOf(g.active) && <UploadButton element={sketchOf(g.active)!} live={live} />}
                    {i === last && problems}
                    {i === last && runButton}
                    {i === last && (
                      <button className={cn(barButton, "[&_svg]:size-4")} onClick={() => setFull(!full)}
                              title={full ? t("schematic.exitFull") : t("schematic.full")} aria-label={t("schematic.full")}>
                        {full ? <Shrink /> : <Expand />}
                      </button>
                    )}
                  </div>
                </div>
                <div data-group-body className="relative flex-1 min-h-0">
                  {body(g.active)}
                </div>
              </section>
            </div>
          ))}
        </div>
        {panel && (
          <>
            {full && <Sash label={ts("panel.resize")}
                  onDrag={(y) => setPanelHeight(Math.min(frame.current!.getBoundingClientRect().height - 160, Math.max(120, frame.current!.getBoundingClientRect().bottom - y)))} />}
            {!full && <div className="h-px flex-none bg-line" />}
            {panel}
          </>
        )}
        {live.error && (
          <div className="relative flex-none border-t border-line p-2">
            <FailureBox failure={live.error} className="pr-10 text-[14px]" />
            <button className={cn(barButton, "absolute top-3.5 right-3.5 [&_svg]:size-4")}
                    onClick={live.dismissError} title={ts("error.dismiss")} aria-label={ts("error.dismiss")}><Close /></button>
          </div>
        )}
      </div>
      {drag && (
        <>
          {drag.drop && (
            // where it lands: a line between tabs, or the part of a group lit (a new split, a side, a tab there)
            <div className={cn("fixed z-150 pointer-events-none transition-all duration-100",
                               drag.drop.zone === "tab" ? "bg-accent rounded-full" : "bg-accent/15 border-2 border-accent/60")}
                 style={drag.drop.box} />
          )}
          <div className="fixed z-150 px-2.5 py-1 rounded-md border border-line bg-board text-[13px] shadow-tools pointer-events-none"
               style={{ left: drag.x + 12, top: drag.y + 12 }}>{drag.label}</div>
        </>
      )}
      {/* the PDF shows the circuit as drawn; results belong to code cells: schematic(układ1, sol) */}
      <PdfDrawing value={cell.schematic} library={library} results={printed} />
      {cell.results && Object.keys(cell.results).length > 0 && (
        <ResultsTable results={cell.results} stale={!!cell.stale} />
      )}
    </div>
  );
}
