// A text cell edited in place, like a document (Milkdown's Crepe, on ProseMirror): what you see
// is the formatted text; "/" inserts headings, lists, tables, formulas; selecting text shows a
// small toolbar. The cell still stores Markdown ($…$ for formulas), so files and PDF stay the same.
//
// Blocks are moved and deleted with our own handle — inside the cell, with a small menu, and
// Alt+↑/↓ — instead of Crepe's: that one sat outside the cell, and its drag and drop could
// copy a block instead of moving it.
import { Crepe } from "@milkdown/crepe";
import "@milkdown/crepe/theme/common/style.css";
import { editorViewCtx } from "@milkdown/kit/core";
import { TextSelection } from "@milkdown/kit/prose/state";
import type { EditorView } from "@milkdown/kit/prose/view";
import { useEffect, useRef, useState } from "react";
import { Down, Grip, Plus, Trash, Up } from "../icons";

const POLISH = {
  [Crepe.Feature.Placeholder]: { text: "Pisz… albo „/”, żeby wstawić nagłówek, listę, tabelę, wzór", mode: "block" as const },
  [Crepe.Feature.BlockEdit]: {
    textGroup: {
      label: "Tekst",
      text: { label: "Zwykły tekst" },
      h1: { label: "Nagłówek 1" },
      h2: { label: "Nagłówek 2" },
      h3: { label: "Nagłówek 3" },
      h4: { label: "Nagłówek 4" },
      h5: { label: "Nagłówek 5" },
      h6: { label: "Nagłówek 6" },
      quote: { label: "Cytat" },
      divider: { label: "Linia" },
    },
    listGroup: {
      label: "Listy",
      bulletList: { label: "Lista punktowana" },
      orderedList: { label: "Lista numerowana" },
      taskList: { label: "Lista zadań" },
    },
    advancedGroup: {
      label: "Więcej",
      image: null,
      codeBlock: { label: "Blok kodu" },
      table: { label: "Tabela" },
      math: { label: "Wzór (LaTeX)" },
    },
  },
  [Crepe.Feature.Toolbar]: {
    boldLabel: "Pogrubienie",
    italicLabel: "Kursywa",
    strikethroughLabel: "Przekreślenie",
    codeLabel: "Kod",
    linkLabel: "Link",
    latexLabel: "Wzór",
  },
  [Crepe.Feature.Latex]: { inlineEditConfirm: "Gotowe" },
};

// ------------------------------------------------------------------ top-level blocks

/** Start and end of the index-th top-level block. */
function span(view: EditorView, index: number): [number, number] {
  let found: [number, number] = [0, 0];
  view.state.doc.forEach((node, offset, i) => {
    if (i === index) found = [offset, offset + node.nodeSize];
  });
  return found;
}

/** Swap block `index` with its neighbour above (by = -1) or below (by = 1). */
function moveBlock(view: EditorView, index: number, by: -1 | 1) {
  const doc = view.state.doc;
  const other = index + by;
  if (other < 0 || other >= doc.childCount) return;
  const [a, b] = by < 0 ? [other, index] : [index, other]; // a comes first
  const [aFrom] = span(view, a);
  const [bFrom, bTo] = span(view, b);
  const lower = doc.child(b);
  const tr = view.state.tr.delete(bFrom, bTo).insert(aFrom, lower); // the lower one goes above
  const moved = by < 0 ? aFrom : aFrom + lower.nodeSize; // where our block starts now
  tr.setSelection(TextSelection.near(tr.doc.resolve(Math.min(moved + 1, tr.doc.content.size))));
  view.dispatch(tr.scrollIntoView());
}

function deleteBlock(view: EditorView, index: number) {
  const [from, to] = span(view, index);
  view.dispatch(view.state.tr.delete(from, to)); // the last block leaves an empty paragraph
}

/** An empty paragraph under block `index`, with "/" typed in it: the insert menu opens. */
function insertBelow(view: EditorView, index: number) {
  const [, to] = span(view, index);
  const tr = view.state.tr.insert(to, view.state.schema.nodes.paragraph.create());
  tr.setSelection(TextSelection.create(tr.doc, to + 1));
  view.dispatch(tr);
  view.focus();
  view.dispatch(view.state.tr.insertText("/"));
}

// ------------------------------------------------------------------ the editor

export function RichText({ value, onChange, autoFocus }: {
  value: string; onChange: (markdown: string) => void; autoFocus?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const mount = useRef<HTMLDivElement>(null); // the editor's; React renders nothing into it
  const viewRef = useRef<EditorView | null>(null);
  const changed = useRef(onChange);
  changed.current = onChange;
  const [hover, setHover] = useState<{ index: number; top: number } | null>(null);
  const [menu, setMenu] = useState(false);

  // the editor owns its document; the cell only hears about changes (value is the start)
  useEffect(() => {
    if (!mount.current) return;
    // a fresh element per editor: React (StrictMode) may mount twice, and two editors must never
    // share one element
    const host = document.createElement("div");
    mount.current.appendChild(host);
    const crepe = new Crepe({
      root: host,
      defaultValue: value,
      features: { [Crepe.Feature.ImageBlock]: false, [Crepe.Feature.AI]: false, [Crepe.Feature.TopBar]: false },
      featureConfigs: POLISH,
    });
    crepe.on((listen) => listen.markdownUpdated((_, markdown, before) => {
      if (markdown !== before) changed.current(markdown.trimEnd());
    }));
    let alive = true;
    crepe.create().then((editor) => {
      if (!alive) return;
      viewRef.current = editor.action((ctx) => ctx.get(editorViewCtx));
      if (autoFocus) viewRef.current.focus();
    });
    return () => {
      alive = false;
      viewRef.current = null;
      crepe.destroy().finally(() => host.remove());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // our block handle follows the pointer from block to block (not while its menu is open)
  const track = (event: React.MouseEvent) => {
    const view = viewRef.current;
    if (menu || !root.current || !view) return;
    let el = event.target as HTMLElement | null;
    while (el && el.parentElement !== view.dom) el = el.parentElement;
    if (!el) return;
    // which block this is, by the document (the editor also puts other elements in there)
    let index = -1;
    view.state.doc.forEach((_, offset, i) => { if (view.nodeDOM(offset) === el) index = i; });
    const top = el.getBoundingClientRect().top - root.current.getBoundingClientRect().top;
    if (index >= 0 && (hover?.index !== index || hover.top !== top)) setHover({ index, top });
  };

  const act = (fn: (view: EditorView, index: number) => void) => {
    const view = viewRef.current;
    if (view && hover) fn(view, hover.index);
    setMenu(false);
    setHover(null);
  };

  return (
    <div
      className="rich-text"
      ref={root}
      onMouseMove={track}
      onMouseLeave={() => !menu && setHover(null)}
      onKeyDown={(event) => { // Alt+↑/↓ moves the block with the cursor
        const view = viewRef.current;
        if (!view || !event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
        event.preventDefault();
        moveBlock(view, view.state.selection.$from.index(0), event.key === "ArrowUp" ? -1 : 1);
      }}
    >
      {hover && (
        <BlockHandle top={hover.top} open={menu} setOpen={setMenu}
                     onInsert={() => act(insertBelow)}
                     onUp={() => act((v, i) => moveBlock(v, i, -1))}
                     onDown={() => act((v, i) => moveBlock(v, i, 1))}
                     onDelete={() => act(deleteBlock)} />
      )}
      <div ref={mount} />
    </div>
  );
}

function BlockHandle({ top, open, setOpen, onInsert, onUp, onDown, onDelete }: {
  top: number; open: boolean; setOpen: (open: boolean) => void;
  onInsert: () => void; onUp: () => void; onDown: () => void; onDelete: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { // a click anywhere else closes the menu
    if (!open) return;
    const close = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open, setOpen]);
  return (
    <div className="block-handle no-print" ref={ref} style={{ top }}>
      <button className="grip" onMouseDown={(e) => e.preventDefault()} onClick={() => setOpen(!open)}
              title="Blok: przenieś, usuń, wstaw (Alt+↑/↓ przenosi)" aria-label="Menu bloku" aria-expanded={open}>
        <Grip />
      </button>
      {open && (
        <div className="block-menu" role="menu">
          <button role="menuitem" onMouseDown={(e) => e.preventDefault()} onClick={onInsert}><Plus /> Wstaw poniżej</button>
          <button role="menuitem" onMouseDown={(e) => e.preventDefault()} onClick={onUp}><Up /> W górę <kbd>Alt ↑</kbd></button>
          <button role="menuitem" onMouseDown={(e) => e.preventDefault()} onClick={onDown}><Down /> W dół <kbd>Alt ↓</kbd></button>
          <hr />
          <button role="menuitem" className="danger" onMouseDown={(e) => e.preventDefault()} onClick={onDelete}><Trash /> Usuń</button>
        </div>
      )}
    </div>
  );
}
