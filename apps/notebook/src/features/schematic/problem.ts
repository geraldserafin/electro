// A drawing as a problem, as electro reads one (electro.core.problem.netlist): each element between
// named points with its value and parameters — what its text says read into them (a source's frequency,
// a switch's position), a real part or an LED's colour by its name — and what is given and sought, as
// quantities.
import type { ElementData, SchematicData, SymbolLibrary } from "@/shared/model/types";
import { kindInfo, wave } from "./model";
import { type NetElement, netlist, type Quantity, quantities } from "./netlist";

export interface ProblemElement {
  id: string;
  kind: string;
  nodes: string[];
  value: string | null;
  params: Record<string, string | number>;
  part?: string; // a real part's name (electro's catalogues), an LED's colour
  unit: string; // its value's, as written beside it
}

export interface ProblemData {
  elements: ProblemElement[];
  given: [Quantity, string][];
  find: Quantity[];
}

const READINGS: Record<string, string> = { potentiometer: "position", photoresistor: "lux", thermistor: "temperature" };
const PARTS = ["led", "diode", "npn", "pnp", "opamp"];

/** What its text says, as its parameters. */
function read(e: NetElement): Pick<ProblemElement, "params" | "part"> {
  const text = e.text?.trim() ?? "";
  if (PARTS.includes(e.kind)) return text ? { params: {}, part: text } : { params: {} };
  if (e.kind === "sine_source" || e.kind === "square_source") {
    const { frequency, duty, phase } = wave(text);
    const f = frequency.replace(/hz$/i, "").trim() || (e.kind === "sine_source" ? "50" : "1k");
    return { params: e.kind === "sine_source" ? { f, phase } : { f, duty: duty / 100 } };
  }
  if (e.kind === "switch" || e.kind === "button") return { params: { closed: text === "closed" ? 1 : 0 } };
  const reading = READINGS[e.kind];
  if (reading && text) return { params: { [reading]: text.replace(",", ".") } };
  return { params: {} };
}

/** The drawing's elements as data, and where on it each point's name is. */
export function elementsOf(sch: SchematicData, lib: SymbolLibrary) {
  const net = netlist(sch, lib);
  const elements = net.elements.map((e) => ({
    id: e.id,
    kind: e.kind,
    nodes: e.nodes,
    value: e.value?.trim() || null,
    unit: kindInfo(e.kind)?.unit ?? "",
    ...read(e),
  }));
  return { elements, names: net.names };
}

/** The drawing as a problem: its marks with a value given, those without sought. */
export function problemOf(sch: SchematicData, lib: SymbolLibrary): ProblemData & { marks: [ElementData, Quantity][] } {
  const { elements, names } = elementsOf(sch, lib);
  const marks = quantities(sch, lib, names);
  const given = marks.flatMap(([e, q]): [Quantity, string][] => (e.value?.trim() ? [[q, e.value.trim()]] : []));
  return { elements, given, find: [], marks };
}
