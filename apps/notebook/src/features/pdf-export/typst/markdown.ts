// Markdown (as the text cells have it: GFM tables, $math$) to Typst markup. Text is escaped, the
// structure becomes Typst's own (headings, lists, tables, quotes); formulas are handed to `math`,
// which gives the markup that shows them (they stay LaTeX: mitex reads them in the document).
import type { Nodes, Parent, Root } from "mdast";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import remarkParse from "remark-parse";
import { unified } from "unified";

const parser = unified().use(remarkParse).use(remarkGfm).use(remarkMath);

/** Typst markup for text: every character that means something in markup, escaped. */
export const text = (s: string) => s.replace(/[\\#*_`$\[\]<>@~/=+\-^{}|&%!.,:;()]/g, (c) => `\\${c}`);
// (escaping more than needed is harmless: `\.` is a plain dot — a list marker or "1." at the start
// of a line stays text, and a "." right after a call is not read as a method. Quotes stay: Typst
// makes them typographic, in the note's language)

/** A Typst string literal. */
export const str = (s: string) =>
  `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "").replace(/\t/g, "\\t")
    .replace(/[\u0000-\u001f]/g, "")}"`;

/** How a formula shows: `block` — on its own line, centred. */
export type MathHook = (latex: string, block: boolean) => string;

/**
 * ``shift``: levels to lift the headings by — a note written with ## (and no #) numbers its
 * sections 1., 2., not 0.1., 0.2.
 */
export function markdownToTypst(source: string, math: MathHook, shift = 0): string {
  const tree = parser.parse(source) as Root;
  lift = shift;
  return blocks(tree.children as Nodes[], math);
}
let lift = 0;

/** The highest heading level in some Markdown (1 for #), or none. */
export function topHeading(source: string): number | null {
  const depths = (parser.parse(source) as Root).children.flatMap((n) => (n.type === "heading" ? [n.depth] : []));
  return depths.length ? Math.min(...depths) : null;
}

function blocks(nodes: Nodes[], math: MathHook): string {
  return nodes.map((n) => block(n, math)).filter((s) => s.trim()).join("\n\n");
}

function inline(nodes: Nodes[], math: MathHook): string {
  return nodes.map((n) => span(n, math)).join("");
}

const children = (n: Parent, math: MathHook) => inline(n.children as Nodes[], math);

function block(n: Nodes, math: MathHook): string {
  switch (n.type) {
    case "heading":
      return `#heading(level: ${Math.max(1, n.depth - lift)})[${children(n, math)}]`;
    case "paragraph":
      return `#par[${children(n, math)}]`;
    case "thematicBreak":
      return `#line(length: 100%, stroke: 0.5pt + luma(180))`;
    case "blockquote":
      return `#quote(block: true)[${blocks(n.children as Nodes[], math)}]`;
    case "code":
      return `#raw(block: true, ${n.lang ? `lang: ${str(n.lang)}, ` : ""}${str(n.value)})`;
    case "math":
      return math(n.value, true);
    case "list": {
      const items = n.children.map((item) => {
        const box = item.checked === true ? "☑ " : item.checked === false ? "☐ " : "";
        return `[${box}${blocks(item.children as Nodes[], math)}]`;
      });
      return n.ordered
        ? `#enum(start: ${n.start ?? 1}, tight: ${!n.spread}, ${items.join(", ")})`
        : `#list(tight: ${!n.spread}, ${items.join(", ")})`;
    }
    case "table": {
      const columns = n.children[0]?.children.length ?? 1;
      const align = Array.from({ length: columns }, (_, i) => n.align?.[i] ?? "left").map((a) => (a === "center" ? "center" : a === "right" ? "right" : "left"));
      const [head, ...rows] = n.children;
      const cells = (row: typeof head) => row.children.map((c) => `[${children(c, math)}]`).join(", ");
      return `#table(columns: ${columns}, align: (${align.join(", ")},), table.header(${cells(head)}),${rows.map((r) => ` ${cells(r)},`).join("")})`;
    }
    case "html":
      return `#par[${text(n.value)}]`;
    case "definition":
    case "footnoteDefinition":
      return "";
    default:
      // a stray inline node on its own (e.g. in a list item without a paragraph)
      return "children" in n || "value" in n ? `#par[${span(n, math)}]` : "";
  }
}

function span(n: Nodes, math: MathHook): string {
  switch (n.type) {
    case "text":
      return text(n.value.replace(/\n/g, " "));
    case "strong":
      return `#strong[${children(n, math)}]`;
    case "emphasis":
      return `#emph[${children(n, math)}]`;
    case "delete":
      return `#strike[${children(n, math)}]`;
    case "inlineCode":
      return `#raw(${str(n.value)})`;
    case "inlineMath":
      return math(n.value, false);
    case "break":
      return `#linebreak()`;
    case "link":
      return /^(https?|mailto):/i.test(n.url) ? `#link(${str(n.url)})[${children(n, math)}]` : children(n, math);
    case "image":
      return n.alt ? `#emph[${text(n.alt)}]` : "";
    case "html":
      return text(n.value);
    case "linkReference":
      return children(n, math);
    case "footnoteReference":
    case "imageReference":
      return "";
    default:
      return "children" in n ? inline((n as Parent).children as Nodes[], math) : "value" in n ? text(String(n.value)) : "";
  }
}
