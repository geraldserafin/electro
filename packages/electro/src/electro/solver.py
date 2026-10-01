"""Solver: constraint propagation (step by step, like on paper), then a global solve.

Every step keeps the law it used (and the law its reason), so the solution can be explained.
What goes wrong is an ``issues`` type, never a sentence.
"""

from __future__ import annotations

import itertools
import warnings
from dataclasses import dataclass

import sympy as sp
from sympy.polys.matrices import DomainMatrix
from sympy.solvers.solveset import NonlinearError

from .circuit import Circuit
from .components import OPEN, Component, Context, Hole, Law, notation
from .issues import (
    Ambiguous,
    BadCondition,
    CircuitError,
    ComponentRepeated,
    ConflictingData,
    Contradiction,
    Equals,
    HoleUndetermined,
    IsZero,
    LawBroken,
    MissingData,
    NoSolutionFor,
    NoSystemSolution,
    NotInCircuit,
    Underdetermined,
    Undetermined,
)
from .reasons import Given
from .semantics import KIND_ORDER, Placed, System, compile_circuit
from .values import expression, fmt, parse

# --------------------------------------------------------------------------- references


def I(label: str) -> sp.Symbol:
    """Current through a component, e.g. ``I("R_1")``."""
    return sp.Symbol(f"I_{label}")


def U(label: str) -> sp.Symbol:
    """Voltage across a component, e.g. ``U("R_1")``."""
    return sp.Symbol(f"U_{label}")


def V(node: str) -> sp.Symbol:
    """Potential of a named node, e.g. ``V("A")``."""
    return sp.Symbol(f"V_{node}")


def P(label: str) -> sp.Symbol:
    """Power of a component (``U·I``), e.g. ``P("R_1")``."""
    return sp.Symbol(f"P_{label}")


# --------------------------------------------------------------------------- trace


@dataclass
class Step:
    targets: dict[sp.Symbol, sp.Expr]
    laws: list[Law]
    formula: sp.Expr | None = None  # for single-target steps: target = formula(knowns)


# --------------------------------------------------------------------------- missing data


@dataclass
class Diagnosis:
    """Why ``targets`` cannot be determined and which extra givens would fix it."""

    targets: list[sp.Symbol]
    needed: int | None  # how many more independent givens; None = more than we searched for
    options: list[tuple[sp.Symbol, ...]]  # minimal sets of quantities that would suffice

    def fields(self) -> dict:
        return {"targets": self.targets, "needed": self.needed, "options": self.options}


def _diagnose(targets, param_map, free, candidates, max_size=3, max_options=6) -> Diagnosis | None:
    """``param_map`` expresses every quantity through the ``free`` parameters left after solving.

    A set S of extra givens determines X iff ∇X lies in the span of {∇s : s ∈ S}.
    """

    def grad(s):
        return sp.Matrix([[sp.simplify(sp.diff(param_map[s], t)) for t in free]])

    undetermined = [(x, grad(x)) for x in targets]
    undetermined = [(x, g) for x, g in undetermined if not g.is_zero_matrix]
    if not undetermined:
        return None
    gs = [g for _, g in undetermined]
    cands = [(c, grad(c)) for c in candidates if c not in targets]
    cands = [(c, g) for c, g in cands if not g.is_zero_matrix]
    for size in range(1, min(len(free), max_size) + 1):
        options = []
        for combo in itertools.combinations(cands, size):
            S = sp.Matrix.vstack(*(g for _, g in combo))
            rank = S.rank(simplify=True)
            if rank == size and all(sp.Matrix.vstack(S, g).rank(simplify=True) == rank for g in gs):
                options.append(tuple(c for c, _ in combo))
                if len(options) == max_options:
                    break
        if options:
            return Diagnosis([x for x, _ in undetermined], size, options)
    return Diagnosis([x for x, _ in undetermined], None, [])


# --------------------------------------------------------------------------- results


@dataclass
class PartResult:
    label: str
    component: Component
    value: sp.Expr | None
    U: sp.Expr | None
    I: sp.Expr | None
    realized: Circuit | None = None  # for a Hole: the element it turned out to be
    ac: bool = False  # U and I are phasors (amplitudes), P is the average power ½·Re(U·I*)

    @property
    def P(self):
        if self.U is None or self.I is None:
            return None
        if self.ac:
            return sp.simplify(sp.re(sp.expand_complex(self.U * sp.conjugate(self.I))) / 2)
        return sp.simplify(self.U * self.I)

    def __repr__(self):
        if isinstance(self.component, Hole):
            head = f"{self.label} → {'?' if self.realized is None else notation(self.realized)}"
            return f"{head}   U = {fmt(self.U, 'V')}   I = {fmt(self.I, 'A')}"
        head = f"{self.label} = {fmt(self.value, self.component.unit)}" if self.component.has_value else self.label
        fields = [f"U = {fmt(self.U, 'V')}", f"I = {fmt(self.I, 'A')}"]
        if self.P is not None and not self.P.has(sp.I):
            fields.append(f"P = {fmt(self.P, 'W')}")
        return head.ljust(17) + " " + "   ".join(fields)


class Solution:
    def __init__(self, system: System, values, steps, given, missing, find=(), parametric=None, assumed=None):
        self.system = system
        self.values: dict[sp.Symbol, sp.Expr] = values
        self.steps: list[Step] = steps
        self.given: dict[sp.Symbol, sp.Expr] = given
        self.missing: list[sp.Symbol] = missing
        self.find: list[sp.Symbol] = list(find)
        self._parametric = parametric  # (param_map, free parameters) when underdetermined
        self.assumed: dict[sp.Symbol, sp.Expr] = assumed or {}  # "simplest filling" of holes

    @property
    def answers(self) -> dict[str, sp.Expr]:
        """Values of the quantities passed as ``find``."""
        return {s.name: self._value(s) for s in self.find}

    def diagnose(self, targets=None) -> Diagnosis | None:
        """Explain what is missing to determine ``targets`` (default: everything undetermined)."""
        if self._parametric is None:
            return None
        targets = self.missing if targets is None else [_target(self.system, t) for t in targets]
        param_map, free = self._parametric
        return _diagnose(targets, param_map, free, _measurable(self.system))

    # lookups
    def _placed(self, key) -> Placed:
        parts = self.system.parts
        if isinstance(key, str):
            return self.system.part(key)
        if isinstance(key, Component):
            found = [p for p in parts.values() if p.component is key]
            if len(found) == 1:
                return found[0]
            if found:
                raise ComponentRepeated(len(found))
        raise NotInCircuit(repr(key))

    def __getitem__(self, key) -> PartResult:
        p = self._placed(key)
        get = lambda role: self._value(p.model.variables[role]) if role in p.model.variables else None
        param = p.model.param
        value = None if param is None else self._value(param)
        return PartResult(
            p.label, p.component, value, get("U"), get("I"), self.realize(p.label), self.system.ctx.omega is not None
        )

    def realize(self, label: str) -> Circuit | None:
        """For a ``Hole``: the simplest element matching the solution (None if undetermined)."""
        p = self._placed(label)
        if not isinstance(p.component, Hole):
            return None
        E, Z, I = (self._value(p.model.variables[k]) for k in ("E", "Z", "I"))
        if p.model.variables["Z"] not in self.values and I == 0:
            return OPEN  # no current through it and nothing else to say: a break
        return None if E is None or Z is None else Hole.realize(E, Z)

    def realize_component(self, component: Component) -> Circuit:
        """``fill`` hook: holes become their realization, everything else stays."""
        if not isinstance(component, Hole):
            return component
        placed = [p for p in self.system.parts.values() if p.component is component]
        if not placed:
            raise NotInCircuit(repr(component))
        result = self.realize(placed[0].label)
        if result is None:
            raise HoleUndetermined(sp.Symbol(placed[0].label))
        return result

    def _value(self, s: sp.Symbol):
        if s in self.values:
            return self.values[s]
        if s in self.missing:
            return None
        return s  # symbolic parameter

    def V(self, node: str):
        return self(V(node))

    def U(self, a: str, b: str):
        """Voltage between nodes ``a`` and ``b`` (``V_a − V_b``)."""
        return self(V(a) - V(b))

    def __call__(self, expr):
        """Evaluate any expression of references, e.g. ``sol(U("R1") / I("R1"))``."""
        expr = _resolve(expression(expr) if isinstance(expr, str) else sp.sympify(expr, strict=True), self.system)
        result = sp.simplify(expr.xreplace(self.values))
        unknown = result.free_symbols & set(self.missing)
        if unknown:
            raise Undetermined(sorted(unknown, key=lambda s: s.name))
        return result

    # presentation
    def unit(self, s: sp.Symbol) -> str:
        return _unit(self.system, s)

    @property
    def data(self) -> dict[sp.Symbol, sp.Expr]:
        """Everything given up front: component values and the givens of the problem."""
        return {**{k: v for k, v in self.system.known.items() if not k.name.startswith("V_")}, **self.given}

    def shown_steps(self) -> list[Step]:
        """The trace; with ``find``, only the steps needed for the answers."""
        if not self.find:
            return self.steps
        needed, kept = set(self.find), []
        for step in reversed(self.steps):
            if needed & set(step.targets):
                kept.append(step)
                deps = (
                    step.formula.free_symbols
                    if step.formula is not None
                    else set().union(*(law.expr.free_symbols for law in step.laws))
                )
                needed |= deps
        return kept[::-1]

    def __repr__(self):
        if self.find:
            return "\n".join(f"{s.name} = {fmt(self._value(s), self.unit(s))}" for s in self.find)
        rows = [repr(self[label]) for label in self.system.parts]
        nodes = [
            f"V_{name} = {fmt(self._value(sym), 'V')}"
            for name, sym in self.system.potentials.items()
            if not name.startswith("n") or name == "GND"
        ]
        return "\n".join(rows + ([", ".join(nodes)] if nodes else []))


# --------------------------------------------------------------------------- solving


def _resolve(expr: sp.Expr, system: System) -> sp.Expr:
    """Map user references (plain symbols) onto the system's variables by name."""
    mapping = {}
    for s in expr.free_symbols:
        if s.name.startswith("P_"):
            model = system.part(s.name[2:]).model
            mapping[s] = model.variables["U"] * model.variables["I"]
        else:
            mapping[s] = system.symbol(s.name)
    return expr.xreplace(mapping)


def _target(system: System, name) -> sp.Symbol:
    """What ``find`` means: a component label gives its value, anything else is a quantity name."""
    if isinstance(name, sp.Symbol):
        name = name.name
    try:
        placed = system.part(name)
    except KeyError:
        return system.symbol(name)
    model = placed.model
    return model.param if model.param is not None else model.variables.get("I") or system.symbol(name)


def _measurable(system: System) -> list[sp.Symbol]:
    """Quantities one could be given: component values, voltages, currents, named potentials."""
    out = []
    for p in system.parts.values():
        out += [s for s in (p.model.param, p.model.variables.get("U"), p.model.variables.get("I")) if s is not None]
    out += [s for name, s in system.potentials.items() if not (name.startswith("n") and name[1:].isdigit())]
    return list(dict.fromkeys(out))


def _given_laws(equations, given, system) -> list[Law]:
    items: list[tuple[sp.Expr, sp.Expr]] = []
    for eq in equations:
        if isinstance(eq, dict):
            items += [
                (sp.sympify(k, strict=True) if not isinstance(k, str) else sp.Symbol(k), parse(v))
                for k, v in eq.items()
            ]
        elif isinstance(eq, sp.Equality):
            items.append((eq.lhs, eq.rhs))
        else:
            raise BadCondition(repr(eq))
    items += [(sp.Symbol(name), parse(v)) for name, v in given.items()]
    return [Law(_resolve(lhs - rhs, system), Given(), "given") for lhs, rhs in items]


def _admissible(var: sp.Symbol, value: sp.Expr) -> bool:
    """Respect sign assumptions (R > 0, Z ≥ 0) and reject non-finite values."""
    if value.has(sp.zoo, sp.oo, -sp.oo, sp.nan):
        return False
    if var.is_positive and value.is_positive is False:
        return False
    return not (var.is_nonnegative and value.is_nonnegative is False)


def _unit(system: System, s: sp.Symbol) -> str:
    for p in system.parts.values():
        if s == p.model.param:
            return p.component.unit
    return {"U": "V", "V": "V", "I": "A", "P": "W", "E": "V", "Z": "Ω"}.get(s.name.split("_")[0], "")


def _data_items(system: System, laws: list[Law]) -> list[tuple[tuple, Equals | IsZero]]:
    """Every single piece of data, as (key for _solve's ``drop``, the datum)."""
    items = [
        (("param", s.name), Equals(s, v, _unit(system, s)))
        for s, v in system.known.items()
        if not s.name.startswith("V_")
    ]
    for i, law in enumerate(laws):
        free = list(law.expr.free_symbols)
        if len(free) == 1 and sp.diff(law.expr, free[0]) == 1:
            datum = Equals(free[0], free[0] - law.expr, _unit(system, free[0]))
        else:
            datum = IsZero(law.expr)
        items.append((("given", i), datum))
    return items


def _explain_contradiction(circuit, equations, omega, find, given, err: Contradiction) -> ConflictingData:
    """Which data clash: those whose removal alone makes everything else consistent."""
    ctx = Context(None if omega is None else parse(omega))
    system = compile_circuit(circuit, ctx=ctx)
    conditions, values = [], []  # culprits: given conditions / component values
    for key, datum in _data_items(system, _given_laws(equations, given, system)):
        try:
            _solve(circuit, equations, omega, find, given, {}, drop=frozenset([key]))
        except CircuitError:
            continue
        (conditions if key[0] == "given" else values).append(datum)
    return ConflictingData(conditions, values, err)


def _check_zero(expr, law: Law, known):
    rest = sp.simplify(expr.xreplace(known))
    if rest != 0:
        raise LawBroken(law, rest)


def _sine_omega(circuit: Circuit):
    """Sine sources all at one frequency: their ω = 2πf, to solve with phasors; else None (DC)."""
    from .devices import SineSource

    freqs = {c.frequency for c, _ in circuit.netlist.parts if isinstance(c, SineSource) and c.on_paper}
    return 2 * sp.pi * freqs.pop() if len(freqs) == 1 else None


def solve(circuit: Circuit, *equations, omega=None, find=None, **given) -> Solution:
    """Solve a circuit.

    Givens: ``I_R_1=0.5``, ``{I("R_1"): "500m"}``, ``Eq(U("R_1"), 2*U("R_2"))``.
    ``find=["R_1", "I_R_2"]``: the quantities asked for (a label means the component's value);
    the result shows only those, and ``MissingData`` says what is missing if they are not determined.
    A ``Hole`` the data does not pin down is filled with the simplest element that fits:
    a resistor (E = 0), else a source (Z = 0). Sine sources at one frequency and no ``omega``:
    phasors at theirs.
    """
    if not isinstance(circuit, Circuit) and hasattr(circuit, "to_circuit"):
        circuit = circuit.to_circuit()  # a drawing (electro_schematic.Schematic)
    if omega is None:
        omega = _sine_omega(circuit)
    try:
        solution = _solve(circuit, equations, omega, find, given, {})
    except Contradiction as err:
        raise _explain_contradiction(circuit, equations, omega, find, given, err) from None
    holes = [p for p in solution.system.parts.values() if isinstance(p.component, Hole)]
    open_holes = [p for p in holes if {p.model.variables["E"], p.model.variables["Z"]} & set(solution.missing)]
    if open_holes:
        # simplest first: a resistor (E = 0), a break (I = 0), a source (Z = 0)
        for choice in itertools.product(("E", "I", "Z"), repeat=len(open_holes)):
            assumed = {p.model.variables[k]: sp.Integer(0) for p, k in zip(open_holes, choice)}
            try:
                attempt = _solve(circuit, equations, omega, find, given, assumed)
            except CircuitError:
                continue
            # a break only pins down E (= −U); its Z does not matter
            needed = {
                p.model.variables[v] for p, k in zip(open_holes, choice) for v in (("E",) if k == "I" else ("E", "Z"))
            }
            if not needed & set(attempt.missing):
                ignored = {p.model.variables["Z"] for p, k in zip(open_holes, choice) if k == "I"}
                attempt.missing = [s for s in attempt.missing if s not in ignored]
                solution = attempt
                break
    return _report(solution)


def _report(solution: Solution) -> Solution:
    if solution.find:
        lacking = [t for t in solution.find if t in solution.missing]
        if lacking:
            raise MissingData(**solution.diagnose(lacking).fields(), solution=solution)
    elif solution.missing:
        diagnosis = solution.diagnose()
        if diagnosis is not None:  # (None: only nodes nothing is wired to — a board's free pins — are not known)
            warnings.warn(Underdetermined(**diagnosis.fields()), stacklevel=3)
    return solution


def _linear_solve(exprs, variables) -> list[dict] | None:
    """A linear system's solution as ``sp.solve(..., dict=True)`` gives it (pivots in terms of the
    free variables; ``[]`` for none), by exact row reduction — many times faster for a big circuit.
    ``None`` when it is not linear."""
    try:
        A, b = sp.linear_eq_to_matrix(exprs, variables)
    except NonlinearError:
        return None
    reduced, pivots = DomainMatrix.from_Matrix(A.row_join(b)).to_field().rref()
    reduced = reduced.to_Matrix()
    n = len(variables)
    if n in pivots:
        return []
    free = [k for k in range(n) if k not in pivots]
    return [
        {
            variables[j]: reduced[i, n] - sum((reduced[i, k] * variables[k] for k in free), sp.S.Zero)
            for i, j in enumerate(pivots)
        }
    ]


def _solve(circuit: Circuit, equations, omega, find, given, assumed, drop: frozenset = frozenset()) -> Solution:
    """``drop``: data to leave out — ("given", index) or ("param", name), see _data_items."""
    ctx = Context(None if omega is None else parse(omega))
    system = compile_circuit(circuit, ctx=ctx)
    if isinstance(find, (str, sp.Symbol)):
        find = [find]
    targets = [_target(system, name) for name in find or ()]
    known = dict(system.known) | assumed
    unknown = set(system.unknowns) - set(assumed)
    for kind, name in drop:
        if kind == "param":  # a component value treated as unknown
            sym = system.symbol(name)
            known.pop(sym, None)
            unknown.add(sym)
    given_values: dict[sp.Symbol, sp.Expr] = {}
    pending: list[Law] = []

    for i, law in enumerate(_given_laws(equations, given, system)):
        if ("given", i) in drop:
            continue
        free = law.expr.free_symbols & unknown
        sym = next(iter(free)) if len(free) == 1 else None
        if sym is not None and sp.diff(law.expr, sym) == 1 and not (law.expr - sym).free_symbols & unknown:
            given_values[sym] = value = -(law.expr - sym)
            known[sym] = value
            unknown.discard(sym)
        elif not free:
            _check_zero(law.expr, law, known)
        else:
            pending.append(law)
    pending += system.laws
    pending.sort(key=lambda law: KIND_ORDER[law.kind])

    steps: list[Step] = []
    parametric = None
    progress = True
    while progress:
        progress = False
        for law in pending:
            free = law.expr.free_symbols & unknown
            if not free:
                _check_zero(law.expr, law, known)
                pending.remove(law)
                progress = True
                break
            if len(free) != 1:
                continue
            (var,) = free
            values = [v for v in sp.solve(law.expr.xreplace(known), var) if _admissible(var, v)]
            if not values:
                raise NoSolutionFor(var, law)
            if len(set(values)) > 1:
                continue
            value = sp.simplify(values[0])
            formulas = sp.solve(law.expr, var)
            formula = formulas[0] if len(formulas) == 1 else var
            known[var] = value
            unknown.discard(var)
            steps.append(Step({var: value}, [law], formula))
            pending.remove(law)
            progress = True
            break

    if pending:
        exprs = [sp.simplify(law.expr.xreplace(known)) for law in pending]
        variables = sorted(set().union(*(e.free_symbols for e in exprs)) & unknown, key=lambda s: s.name)
        solutions = _linear_solve(exprs, variables)
        if solutions is None:  # not linear (an unknown element's value times a current): sympy's own
            solutions = sp.solve(exprs, variables, dict=True)
        if not solutions:
            raise NoSystemSolution(list(pending))
        if len(solutions) > 1:
            params = {p.model.param for p in system.parts.values()} & unknown
            shown = targets or sorted(params, key=lambda s: s.name) or variables[:3]
            raise Ambiguous([[Equals(s, sol[s], _unit(system, s)) for s in shown if s in sol] for sol in solutions])
        general = {k: sp.simplify(v) for k, v in solutions[0].items()}
        solved = {k: v for k, v in general.items() if k in unknown and not v.free_symbols & unknown}
        free = sorted(unknown - set(general), key=lambda s: s.name)
        if free:
            param_map = {s: known.get(s, general.get(s, s)) for s in system.unknowns}
            param_map |= {s: v for s, v in known.items()}
            parametric = (param_map, free)
        known.update(solved)
        unknown -= set(solved)
        steps.append(Step(solved, list(pending)))
        for law in pending:
            if not law.expr.free_symbols & unknown:
                _check_zero(law.expr, law, known)

    missing = [s for s in system.unknowns if s in unknown]
    return Solution(system, known, steps, given_values, missing, targets, parametric, assumed)
