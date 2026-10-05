// What the kernel says without words (python/electro_notebook/kernel.py): what went wrong
// (electro.issues and friends), why a step of a solution holds (electro.reasons), a worked
// solution (electro_render.Steps). Each is its type's name and its fields; features/solution
// says them in the reader's language. Tex: LaTeX without the $ (a quantity, a value, an equation).

export type Tex = string;

/** A law in an issue: its equation (`… = 0`) and why it holds. */
export interface LawData {
  equation: Tex;
  reason: Reason;
}

type Labelled =
  | "OhmsLaw"
  | "CapacitorOpenDC"
  | "CapacitorImpedance"
  | "InductorShortDC"
  | "InductorImpedance"
  | "SourceVoltage"
  | "SourceCurrent"
  | "IdealAmmeter"
  | "AmmeterReading"
  | "IdealVoltmeter"
  | "VoltmeterReading"
  | "IdealOpAmp"
  | "TransformerVoltage"
  | "TransformerCurrent"
  | "WindingShortDC"
  | "MutualInductance"
  | "UnknownElement"
  | "VoltageAcross"
  | "ControlVoltage"
  | "ControlCurrent"
  | "ControlledSource"
  | "CapacitorStep"
  | "InductorStep"
  | "SwitchClosed"
  | "SwitchOpen"
  | "PotentiometerDivider"
  | "DeviceModel";

export type Reason =
  | { type: "Given" }
  | { type: Labelled; label: Tex }
  | { type: "Terminal"; side: "in" | "out"; index: number }
  | { type: "KirchhoffCurrent"; node: Tex };

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
  // solving (electro.issues)
  | { type: "ConflictingData"; conditions: Tex[]; values: Tex[] }
  | { type: "LawBroken"; law: LawData; rest: Tex }
  | { type: "NoSolutionFor"; variable: Tex; law: LawData }
  | { type: "NoSystemSolution"; laws: LawData[] }
  | { type: "Ambiguous"; options: Tex[][] }
  | ({ type: "MissingData" | "Underdetermined" } & Diagnosis)
  | { type: "Undetermined"; symbols: Tex[] }
  | { type: "HoleUndetermined"; label: Tex }
  | { type: "BadCondition"; condition: string }
  | { type: "NotInCircuit"; name: string }
  | { type: "ComponentRepeated"; count: number }
  | { type: "NoSuchQuantity"; name: string; available: Tex[] }
  | { type: "NoSuchElement"; label: string; available: Tex[] }
  | { type: "DuplicateLabel"; label: Tex }
  | { type: "BadValue" | "NotAValue" | "NotACircuit"; value: string }
  | { type: "BadExpression"; expression: string }
  | { type: "BadName"; name: string }
  | { type: "SeriesMismatch"; left: string; right: string; outputs: number; inputs: number }
  | { type: "ParallelMismatch"; first: string; first_shape: string; other: string; other_shape: string }
  | { type: "ShuntNeedsOneToOne"; part: string; shape: string }
  | { type: "CloseNeedsNToN" | "NotAPort"; shape: string }
  | { type: "WrongNodeCount"; part: string; terminals: number; nodes: string[] }
  | { type: "NotLinear" | "NoThevenin" }
  | { type: "NoSpice"; element: string }
  // in time (electro.sim)
  | { type: "NeedsSimulation" | "NotSimulated" | "ValueNeeded"; label: Tex }
  | { type: "NoConvergence"; time: number }
  | { type: "NoSuchInput"; name: string; available: string[] }
  // drawings (electro_schematic.issues)
  | { type: "CannotLayOut"; circuit: string }
  | { type: "CannotLayOutElement"; element: string; shape: string }
  | { type: "CannotLayOutParallel" | "CannotLayOutLoop"; shape: string }
  | { type: "NoKindFor"; component: string }
  | { type: "UnknownKind"; kind: string; available: string[] }
  | { type: "BadRotation"; rotation: number }
  | { type: "SkewedWire"; start: [number, number]; end: [number, number] }
  | { type: "NotOnSchematic"; id: string }
  | { type: "EmptySchematic" }
  | { type: "UnknownPart"; part: string }
  | { type: "PartInItself"; part: string }
  // the notebook's kernel
  | { type: "NoCircuitInCode"; variable: string }
  | { type: "NoSweepRange"; element: string }
  | { type: "NoInput" | "NoOutput" }
  | { type: "OnlyValuesInCode"; cause: Issue }
  | { type: "PartsNotInCode" }
  | { type: "BadDataEntry"; entry: string }
  | { type: "NoSuchSchematic"; name: string; available: string[] };

/** Something that went wrong, as outputs and the code view carry it: our issue (else Python's
 *  own words in `data`), and the cell's line it came from. Older notes have `data` alone. */
export interface Failure {
  data: string;
  issue?: Issue;
  line?: number;
}
