// What the kernel says without words (python/electro_notebook): what went wrong (electro_notebook/issues.py,
// the kernel's errors), why a step of a solution holds and a worked solution (electro_notebook/steps.py). Each
// is its type's name and its fields; features/solution says them in the reader's language. Tex: LaTeX
// without the $ (a quantity, a value, an equation).

export type Tex = string;

type Labelled =
  | "OhmsLaw"
  | "CapacitorOpenDC"
  | "CapacitorImpedance"
  | "InductorShortDC"
  | "InductorImpedance"
  | "SourceVoltage"
  | "SourceCurrent"
  | "IdealAmmeter"
  | "IdealVoltmeter"
  | "IdealOpAmp"
  | "ControlledSource"
  | "UnknownElement"
  | "DeviceModel";

export type Reason = { type: "Given" } | { type: Labelled; label: Tex } | { type: "KirchhoffCurrent"; node: Tex };

export interface FormulaStep {
  type: "FormulaStep";
  chain: Tex;
  reason: Reason;
}
export interface SystemStep {
  type: "SystemStep";
  equations: Tex[];
  results: Tex[];
}

export type Diagnosis = { targets: Tex[]; needed: number | null; options: Tex[][] };

export interface Steps {
  type: "Steps";
  data: Tex[];
  assumed: Tex[]; // how holes were filled: the simplest element that fits
  steps: (FormulaStep | SystemStep)[];
  answer: Tex[] | null; // what find= asked for
  missing: ({ type: "Underdetermined" } & Diagnosis) | null;
}

export type Issue =
  // solving (electro_notebook/issues.py)
  | { type: "ConflictingData"; conditions: Tex[]; values: Tex[] }
  | { type: "Ambiguous"; options: Tex[][] }
  | ({ type: "MissingData" | "Underdetermined" } & Diagnosis)
  | { type: "NoSuchQuantity"; name: string; available: Tex[] }
  | { type: "BadValue" | "NotAValue"; value: string }
  | { type: "BadExpression"; expression: string }
  | { type: "BadName"; name: string }
  | { type: "WrongNodeCount"; part: string; terminals: number; nodes: string[] }
  | { type: "UnknownKind"; kind: string; available: string[] }
  | { type: "UnknownPart"; part: string }
  // in time (electro.simulation)
  | { type: "NotSimulated" | "ValueNeeded"; label: Tex }
  | { type: "NoConvergence"; time: number }
  | { type: "NoSuchInput"; name: string; available: string[] }
  // drawings (schematic/)
  | { type: "CannotLayOut"; circuit: string }
  | { type: "PartInItself"; part: string }
  // the notebook's kernel
  | { type: "NoCircuitInCode"; variable: string }
  | { type: "NoSweepRange"; element: string }
  | { type: "NoInput" | "NoOutput" }
  | { type: "OnlyValuesInCode"; cause: Issue }
  | { type: "PartsNotInCode" }
  | { type: "NoSuchSchematic"; name: string; available: string[] };

/** Something that went wrong, as outputs and the code view carry it: our issue (else Python's
 *  own words in `data`), and the cell's line it came from. Older notes have `data` alone. */
export interface Failure {
  data: string;
  issue?: Issue;
  line?: number;
}
