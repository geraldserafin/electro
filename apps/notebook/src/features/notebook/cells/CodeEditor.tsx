// The code editor of code cells and of a schematic's code view, dressed like Google Colab:
// a quiet grey block, faint line numbers, Colab's (VS Code's) syntax colours, and completion
// of electro's names. Colours come from CSS variables, so light / dark all follow.
import { autocompletion, completeFromList, type Completion } from "@codemirror/autocomplete";
import { cpp } from "@codemirror/lang-cpp";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror from "@uiw/react-codemirror";
import type { TFunction } from "i18next";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { pl } from "../messages";

// boost: above Python's own names (ResourceWarning, …) in the list
const doc = (label: string, detail: string, type = "class"): Completion => ({ label, detail, type, boost: 50 });

/** What a student types most: electro's components, combinators and helpers (hints in the app's language). */
function electro(t: TFunction<"notebook">): Completion[] {
  const hint = (name: keyof typeof pl.completion) => t(`completion.${name}`);
  return [
    ...(["Resistor", "Capacitor", "Inductor", "VoltageSource", "CurrentSource", "Ammeter", "Voltmeter", "Hole", "OpAmp",
      "LED", "Diode", "Switch", "Button", "Potentiometer", "NPN", "PNP", "Timer555", "Arduino"] as const)
      .map((c) => doc(c, hint(c))),
    doc("simulate", hint("simulate"), "function"),
    ...["loop", "net", "series", "parallel", "shunt", "supply", "node"].map((f) => doc(f, hint("circuit"), "function")),
    ...["solve", "resistance", "equivalent", "blackbox", "code", "schematic", "steps", "schemat", "display"]
      .map((f) => doc(f, "electro", "function")),
    ...["ground", "wire", "split", "join", "open_end"].map((f) => doc(f, hint("connection"), "variable")),
    ...(["I", "U", "V", "P"] as const).map((f) => doc(f, hint(f), "function")),
    doc("find", hint("find"), "keyword"),
  ];
}

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
  "&": { background: "var(--code-bg)", color: "var(--text)", borderRadius: "8px", fontSize: "16px" },
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

export function CodeEditor({ value, onChange, autoFocus, minHeight, fill, language = "python" }: {
  value: string; onChange: (v: string) => void; autoFocus?: boolean;
  minHeight?: number; // px: the scroller fills it, so its scrollbar sits at the bottom
  language?: "python" | "cpp"; // cpp: an Arduino sketch
  fill?: boolean; // as tall as its parent, scrolling inside (a side pane)
}) {
  const { t, i18n } = useTranslation("notebook");
  const extensions = useMemo(() => [
    ...(language === "cpp" ? [cpp()] : [python(), pythonLanguage.data.of({ autocomplete: completeFromList(electro(t)) })]),
    autocompletion({ icons: false }),
    syntaxHighlighting(colab),
    look,
    ...(minHeight ? [EditorView.theme({ ".cm-scroller": { minHeight: `${minHeight}px` } })] : []),
    // a pane of its own: edge to edge, on the pane's background, like an IDE's editor
    ...(fill ? [EditorView.theme({ "&": { height: "100%", borderRadius: "0", background: "transparent" }, ".cm-scroller": { overflow: "auto" } })] : []),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- t changes with the language
  ], [i18n.language, minHeight, language, fill]);
  return (
    <CodeMirror
      value={value}
      theme="none"
      extensions={extensions}
      height={fill ? "100%" : undefined}
      className={fill ? "h-full" : undefined}
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
