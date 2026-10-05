// The solver's types in words: an issue, a law's reason, a worked solution — as Markdown with
// the math in $…$ (KaTeX on the page, Typst's math in the PDF). One switch per kind of thing:
// a type the kernel has and this does not is a TypeScript error.
import i18n, { type TFunction } from "i18next";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import type { Issue, Reason, Steps, Tex } from "@/shared/model/issues";

const math = (tex: Tex) => `$${tex}$`;
const code = (text: string) => `\`${text.replaceAll("`", "'")}\``;

export type Say = ReturnType<typeof sayer>;

/** The words for the language `t` speaks (`lang`: for lists, "a, b lub c" / "a, b, or c"). */
export function sayer(t: TFunction<"solution">, lang: string) {
  const or = (items: string[]) => new Intl.ListFormat(lang, { type: "disjunction" }).format(items);
  const all = (items: string[]) => items.join(", ");
  const maths = (items: Tex[]) => all(items.map(math));
  const names = (items: string[]) => all(items.map(code)) || t("issue.none");

  function reason(r: Reason): string {
    switch (r.type) {
      case "Given":
        return t("reason.Given");
      case "Terminal":
        return t("reason.Terminal", { side: r.side, index: r.index });
      case "KirchhoffCurrent":
        return t("reason.KirchhoffCurrent", { node: math(r.node) });
      default:
        return t(`reason.${r.type}`, { label: math(r.label) });
    }
  }

  /** Not everything determined: what, how many data are missing, which would do. */
  function missing(targets: Tex[], needed: number | null, options: Tex[][]): string {
    if (needed === null) return t("issue.missingSeveral", { targets: maths(targets) });
    const head = t("issue.missing", { targets: maths(targets), count: needed });
    if (!options.length) return head;
    return `${head} ${
      needed === 1
        ? t("issue.anyOf", { options: maths(options.map((o) => o[0])) })
        : t("issue.forExample", { options: or(options.map((o) => `(${maths(o)})`)) })
    }`;
  }

  function issue(i: Issue): string {
    switch (i.type) {
      case "MissingData":
      case "Underdetermined":
        return missing(i.targets, i.needed, i.options);
      case "ConflictingData": {
        const conditions = maths(i.conditions),
          values = maths(i.values);
        if (i.conditions.length && i.values.length) return t("issue.conflict", { conditions, values });
        if (i.values.length) return t("issue.conflictValues", { values });
        if (i.conditions.length) return t("issue.conflictConditions", { conditions });
        return t("issue.conflictAll");
      }
      case "LawBroken":
        return t("issue.LawBroken", {
          equation: math(i.law.equation),
          reason: reason(i.law.reason),
          rest: math(i.rest),
        });
      case "NoSolutionFor":
        return t("issue.NoSolutionFor", {
          variable: math(i.variable),
          equation: math(i.law.equation),
          reason: reason(i.law.reason),
        });
      case "NoSystemSolution":
        return t("issue.NoSystemSolution", {
          laws: i.laws.map((l) => `${math(l.equation)} (${reason(l.reason)})`).join("; "),
        });
      case "Ambiguous":
        return t("issue.Ambiguous", { count: i.options.length, options: or(i.options.map(maths)) });
      case "Undetermined":
        return t("issue.Undetermined", { symbols: maths(i.symbols) });
      case "HoleUndetermined":
      case "NeedsSimulation":
      case "NotSimulated":
      case "ValueNeeded":
        return t(`issue.${i.type}`, { label: math(i.label) });
      case "NoConvergence":
        return t("issue.NoConvergence", { time: i.time.toPrecision(4) });
      case "NoSuchInput":
        return t("issue.NoSuchInput", { name: code(i.name), available: names(i.available) });
      case "BadCondition":
        return t("issue.BadCondition", { condition: code(i.condition) });
      case "NotInCircuit":
        return t("issue.NotInCircuit", { name: code(i.name) });
      case "ComponentRepeated":
        return t("issue.ComponentRepeated", { count: i.count });
      case "NoSuchQuantity":
        return t("issue.NoSuchQuantity", { name: code(i.name), available: maths(i.available) });
      case "NoSuchElement":
        return t("issue.NoSuchElement", { label: code(i.label), available: maths(i.available) });
      case "DuplicateLabel":
        return t("issue.DuplicateLabel", { label: math(i.label) });
      case "BadExpression":
        return t("issue.BadExpression", { expression: code(i.expression) });
      case "BadName":
        return t("issue.BadName", { name: code(i.name) });
      case "BadValue":
      case "NotAValue":
      case "NotACircuit":
        return t(`issue.${i.type}`, { value: code(i.value) });
      case "SeriesMismatch":
        return t("issue.SeriesMismatch", {
          left: code(i.left),
          right: code(i.right),
          outputs: i.outputs,
          inputs: i.inputs,
        });
      case "ParallelMismatch":
        return t("issue.ParallelMismatch", {
          first: code(i.first),
          firstShape: i.first_shape,
          other: code(i.other),
          otherShape: i.other_shape,
        });
      case "ShuntNeedsOneToOne":
        return t("issue.ShuntNeedsOneToOne", { part: code(i.part), shape: i.shape });
      case "CloseNeedsNToN":
      case "NotAPort":
        return t(`issue.${i.type}`, { shape: i.shape });
      case "WrongNodeCount":
        return t("issue.WrongNodeCount", { part: code(i.part), terminals: i.terminals, nodes: names(i.nodes) });
      case "NotLinear":
      case "NoThevenin":
      case "EmptySchematic":
        return t(`issue.${i.type}`);
      case "CannotLayOut":
        return t("issue.CannotLayOut", { circuit: code(i.circuit) });
      case "CannotLayOutElement":
        return t("issue.CannotLayOutElement", { element: code(i.element), shape: i.shape });
      case "CannotLayOutParallel":
      case "CannotLayOutLoop":
        return t(`issue.${i.type}`, { shape: i.shape });
      case "NoKindFor":
        return t("issue.NoKindFor", { component: code(i.component) });
      case "UnknownKind":
        return t("issue.UnknownKind", { kind: code(i.kind), available: names(i.available) });
      case "BadRotation":
        return t("issue.BadRotation", { rotation: i.rotation });
      case "SkewedWire":
        return t("issue.SkewedWire", { start: `(${i.start.join(", ")})`, end: `(${i.end.join(", ")})` });
      case "NotOnSchematic":
        return t("issue.NotOnSchematic", { id: code(i.id) });
      case "NoCircuitInCode":
        return t("issue.NoCircuitInCode", { variable: i.variable });
      case "UnknownPart":
        return t("issue.UnknownPart", { part: code(i.part) });
      case "PartInItself":
        return t("issue.PartInItself", { part: code(i.part) });
      case "PartsNotInCode":
        return t("issue.PartsNotInCode");
      case "OnlyValuesInCode":
        return t("issue.OnlyValuesInCode", { cause: issue(i.cause) });
      case "NoSuchSchematic":
        return t("issue.NoSuchSchematic", { name: code(i.name), available: names(i.available) });
      case "NoSweepRange":
        return t("issue.NoSweepRange", { element: code(i.element) });
      case "NoInput":
      case "NoOutput":
        return t(`issue.${i.type}`);
      default:
        return code((i as { type: string }).type); // a kernel newer than the page
    }
  }

  /** A worked solution: the data, assumptions, numbered steps (each with its law), the answer. */
  function steps(s: Steps): string {
    const out: string[] = [];
    if (s.data.length) out.push(`**${t("steps.data")}** ${maths(s.data)}`);
    if (s.assumed.length) out.push(`**${t("steps.assumed")}** ${t("steps.assumedHint")} ${maths(s.assumed)}`);
    const lines = s.steps.map((step, i) => {
      if (step.type === "FormulaStep") return `${i + 1}. ${math(step.chain)} — ${reason(step.reason)}`;
      const rows = step.equations.map((e) => e.replace(/ = 0$/, " &= 0")).join(String.raw` \\ `);
      return `${i + 1}. ${t("steps.system")}\n\n   $$\\begin{aligned} ${rows} \\end{aligned}$$\n\n   ${t("steps.hence")} ${maths(step.results)}`;
    });
    if (lines.length) out.push(`**${t("steps.solution")}**\n\n${lines.join("\n")}`);
    if (s.answer) out.push(`**${t("steps.answer")}** ${maths(s.answer)}`);
    else if (s.missing) out.push(`**${t("steps.missing")}** ${issue(s.missing)}`);
    return `${out.join("\n\n")}\n`;
  }

  /** "line 2: " before what went wrong in a cell. */
  const line = (n?: number) => (n ? t("line", { line: n }) : "");

  return { issue, reason, steps, line };
}

/** The words in the page's language. */
export function useSay(): Say {
  const {
    t,
    i18n: { language },
  } = useTranslation("solution");
  return useMemo(() => sayer(t, language), [t, language]);
}

/** The words in a given language (outside React: the PDF). */
export const sayIn = (lang: string): Say => sayer(i18n.getFixedT(lang, "solution"), lang);
