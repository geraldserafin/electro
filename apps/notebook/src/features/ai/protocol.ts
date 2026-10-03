// The circuit as the model writes it (agent.ts: draw_circuit), and reading what a model wrote as JSON:
// elements with their nodes and where their terminals are drawn, wires. (No tasks: a note is for notes;
// a test's tasks are its author's.)
export const CIRCUIT_FORMAT = `ELEMENT: {"id": "R1", "kind": KIND, "value": "4.7k", "text": null, "nodes": ["A", "0"], "at": [[0, 0], [8, 0]]}
  id: its label as the picture names it, letters, digits and _ only (R1, R_W, E1, J1, A1). Node names:
  letters, digits, _; "0" is ground.
  value: as given — a number with an optional SI prefix and no unit ("10", "4.7k", "100n", "2.2u", "1M"); null
    when it is not given (asked for, or unknown): the solver works it out from what is.
  KIND and its nodes, in this order:
    resistor, capacitor, inductor, lamp: [a, b]     (U_X = V_a − V_b, I_X flows a → b through it)
    voltage_source: [minus, plus]                   (value: its EMF, V; the arrow points to plus)
    current_source: [from, to]                      (value: A, pushed into "to"; the arrow points to "to")
    sine_source: [minus, plus]                      (value: amplitude, V; text: frequency, Hz, e.g. "50")
    ammeter: [a, b]                                 (value: its reading, A, when known — else null)
    voltmeter: [a, b]                               (value: its reading, V, when known — else null)
    diode, led: [anode, cathode]; zener: [anode, cathode] (value: breakdown voltage)
    switch, button: [a, b]; potentiometer: [a, b, wiper] (value: Ω)
    npn, pnp: [base, collector, emitter]; nmos, pmos: [gate, drain, source]
    opamp: [plus, minus, out]                       (ideal, no value)
    hole: [a, b]                                    (an unknown element: the solver finds the simplest that fits)
    terminal: [a]                                   (an open end — a small circle or a bare wire end where the
                                                     picture leaves the circuit open; "at" one point)
    current_arrow: []                               (a current's arrow as the picture marks it, I_2 by R2: "at" its tail
                                                     and head on the wire, 1 apart, the way it points)
    voltage_arrow: []                               (a voltage's arrow beside what it is across, U_1 by R1: "at" its
                                                     tail and head, as long as drawn, the way it points — to "+")
  An arrow: "text" its name as the picture writes it, its subscript after _ ("I_2", "U_1", "U"); "of" the
  element whose current or voltage it is ("R2"; null for one across several, as U across a divider); "value"
  the amount the problem gives for it ("2" for I_2 = 2 A; null when not given — the solver shows it). A given
  is the solver's data: a problem's measured current or voltage of an element ("the voltage across R_5 is
  125 V") goes on its arrow — one the picture has, else one you add beside that element. Arrows are marks,
  not of the circuit: no nodes.
  Ground is node "0", not an element: its symbol is drawn there.
THE DRAWING: lay every circuit out exactly as the picture (or PDF) draws it — the same places, directions and
corners: a source on the left stays on the left, a resistor standing up stays standing, a branch on the right
stays on the right. Coordinates are grid units, x to the right, y down; about 4 units per resistor's length.
  at: where the element's terminals are, in the order of its nodes. A two-terminal element's two points are on
  one row or one column, 4 or more apart (it is drawn in the middle, wires out to them).
  WIRE: [[x, y], [x, y], ...], a line along rows and columns (each corner a point), as the picture's wires go.
  What touches is joined (a wire's end, a terminal lying on a wire); lines that only cross are not.
  The drawing must join exactly what "nodes" say — the solver checks it. With no picture, draw it as a
  textbook would. Use node "0" only where the picture has ground, or for the source's minus.`;

/** LaTeX commands that begin as a JSON escape does (\frac: \f, \text: \t, \neq: \n…). */
const COMMANDS =
  /^(b(eta|ar|f|ig|igg|oldsymbol|ullet|egin|ot)|f(rac|orall)|n(e|eq|u|abla|ot|eg|ewline|olimits)|r(ho|ight|ightarrow|m|angle|brace|vert)|t(ext|extbf|extrm|extit|imes|heta|au|an|anh|frac|o|ilde|riangle|op))$/;

/** The JSON object in what a model wrote (a code fence around it, say), its LaTeX as meant: models write
 *  \frac, \Omega with one backslash in a JSON string (\f a form feed then, \O no escape at all) — those
 *  doubled; the escapes JSON means (\n, \", \\, \u00e9, \n before a word) kept. */
export function jsonOf<A>(content: string): A {
  const start = content.indexOf("{");
  if (start < 0) throw new Error("no JSON object");
  // where it closes (what comes after it — a model's stray brackets — left out)
  let end = content.lastIndexOf("}");
  for (let i = start, depth = 0, inString = false; i < content.length; i++) {
    const c = content[i];
    if (inString) {
      if (c === "\\") i++;
      else if (c === '"') inString = false;
    } else if (c === '"') inString = true;
    else if (c === "{" || c === "[") depth++;
    else if ((c === "}" || c === "]") && --depth === 0) {
      end = i;
      break;
    }
  }
  const fixed = content
    .slice(start, end + 1)
    .replace(/\\(\\|["/]|u[0-9a-fA-F]{4}|[a-zA-Z]+)?/g, (m, next: string | undefined) => {
      if (next === undefined) return "\\\\"; // \, \{ \;: LaTeX's, doubled
      if (!/^[a-zA-Z]/.test(next) || /^u[0-9a-fA-F]{4}$/.test(next)) return m; // \\ \" \/ \u00e9
      if (/^[bfnrt]/.test(next) && (next.length === 1 || !COMMANDS.test(next))) return m; // \n, \nWord
      return `\\${m}`;
    });
  return JSON.parse(fixed) as A;
}
