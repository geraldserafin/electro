// The code editor of code cells and of a schematic's code view, dressed like Google Colab:
// a quiet grey block, faint line numbers, Colab's (VS Code's) syntax colours, and completion
// of electro's names. Colours come from CSS variables, so light / dark all follow.
import { autocompletion, completeFromList, type Completion } from "@codemirror/autocomplete";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";

// boost: above Python's own names (ResourceWarning, …) in the list
const doc = (label: string, detail: string, type = "class"): Completion => ({ label, detail, type, boost: 50 });

/** What a student types most: electro's components, combinators and helpers. */
const ELECTRO: Completion[] = [
  doc("Resistor", "(wartość, label=…) — opornik, Ω"),
  doc("Capacitor", "(wartość) — kondensator, F"),
  doc("Inductor", "(wartość) — cewka, H"),
  doc("VoltageSource", "(wartość) — źródło napięcia, V"),
  doc("CurrentSource", "(wartość) — źródło prądu, A"),
  doc("Ammeter", "(odczyt) — amperomierz; odczyt to dana pomiarowa"),
  doc("Voltmeter", "(odczyt) — woltomierz"),
  doc("Hole", "() — nieznany element; solver dobierze, czym jest"),
  doc("OpAmp", "() — wzmacniacz operacyjny"),
  ...["loop", "net", "series", "parallel", "shunt", "supply", "node"].map((f) => doc(f, "układ", "function")),
  ...["solve", "resistance", "equivalent", "blackbox", "code", "schematic", "steps", "schemat", "display"]
    .map((f) => doc(f, "electro", "function")),
  ...["ground", "wire", "split", "join", "open_end"].map((f) => doc(f, "połączenie", "variable")),
  ...["I", "U", "V", "P"].map((f) => doc(f, `(\"R_1\") — ${{ I: "prąd", U: "napięcie", V: "potencjał", P: "moc" }[f]}`, "function")),
  doc("find", "= \"R_2\" — czego szukać", "keyword"),
];

const colab = HighlightStyle.define([
  { tag: [t.keyword, t.bool, t.null, t.self], color: "var(--hl-keyword)" },
  { tag: [t.controlKeyword, t.moduleKeyword], color: "var(--hl-control)" },
  { tag: [t.string, t.special(t.string)], color: "var(--hl-string)" },
  { tag: t.number, color: "var(--hl-number)" },
  { tag: t.comment, color: "var(--hl-comment)", fontStyle: "italic" },
  { tag: [t.function(t.variableName), t.function(t.propertyName)], color: "var(--hl-function)" },
  { tag: [t.className, t.definition(t.className)], color: "var(--hl-class)" },
  { tag: [t.propertyName, t.attributeName], color: "var(--hl-property)" },
  { tag: t.operator, color: "var(--text)" },
]);

const look = EditorView.theme({
  "&": { background: "var(--code-bg)", color: "var(--text)", borderRadius: "8px" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.6", padding: "8px 0" },
  ".cm-content": { caretColor: "var(--text)" },
  ".cm-cursor": { borderLeftColor: "var(--text)", borderLeftWidth: "2px" },
  ".cm-gutters": { background: "transparent", border: "none", color: "var(--faint)", paddingLeft: "6px" },
  ".cm-lineNumbers .cm-gutterElement": { minWidth: "22px", padding: "0 10px 0 4px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": { background: "var(--selection) !important" },
  ".cm-matchingBracket": { background: "var(--bracket)", outline: "none" },
  ".cm-tooltip": { background: "var(--island)", border: "1px solid var(--line)", borderRadius: "8px", boxShadow: "var(--island-shadow)" },
  ".cm-tooltip-autocomplete ul li": { fontFamily: "var(--mono)", padding: "2px 8px" },
  ".cm-tooltip-autocomplete ul li[aria-selected]": { background: "var(--tool-active)", color: "var(--text)" },
  ".cm-completionDetail": { fontFamily: "var(--sans)", fontStyle: "normal", color: "var(--muted)", marginLeft: "12px" },
});

const extensions = [
  python(),
  pythonLanguage.data.of({ autocomplete: completeFromList(ELECTRO) }),
  autocompletion({ icons: false }),
  syntaxHighlighting(colab),
  look,
];

export function CodeEditor({ value, onChange, autoFocus }: { value: string; onChange: (v: string) => void; autoFocus?: boolean }) {
  return (
    <CodeMirror
      value={value}
      theme="none"
      extensions={extensions}
      autoFocus={autoFocus}
      basicSetup={{
        foldGutter: false,
        highlightActiveLine: false,
        highlightActiveLineGutter: false,
        syntaxHighlighting: false, // ours (colab) instead of the default colours
        autocompletion: false, // configured above
      }}
      onChange={onChange}
    />
  );
}
