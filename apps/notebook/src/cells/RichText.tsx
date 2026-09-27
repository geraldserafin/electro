// A text cell edited in place, like a document (Milkdown's Crepe, on ProseMirror): what you see
// is the formatted text; "/" inserts headings, lists, tables, formulas; selecting text shows a
// small toolbar. The cell still stores Markdown ($…$ for formulas), so files and PDF stay the same.
import { Crepe } from "@milkdown/crepe";
import "@milkdown/crepe/theme/common/style.css";
import { useEffect, useRef } from "react";

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

export function RichText({ value, onChange, autoFocus }: {
  value: string; onChange: (markdown: string) => void; autoFocus?: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  const changed = useRef(onChange);
  changed.current = onChange;

  // the editor owns its document; the cell only hears about changes (value is the start)
  useEffect(() => {
    if (!root.current) return;
    const crepe = new Crepe({
      root: root.current,
      defaultValue: value,
      features: { [Crepe.Feature.ImageBlock]: false, [Crepe.Feature.AI]: false, [Crepe.Feature.TopBar]: false },
      featureConfigs: POLISH,
    });
    crepe.on((listen) => listen.markdownUpdated((_, markdown, before) => {
      if (markdown !== before) changed.current(markdown.trimEnd());
    }));
    let alive = true;
    crepe.create().then(() => {
      if (alive && autoFocus) root.current?.querySelector<HTMLElement>(".ProseMirror")?.focus();
    });
    return () => {
      alive = false;
      crepe.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div className="rich-text" ref={root} />;
}
