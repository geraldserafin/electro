"""Notebook kernel: runs cells in one shared namespace and turns results into outputs.

Every cell sees what earlier cells defined, like in Jupyter. The value of the last
expression is shown; objects with ``_repr_svg_`` / ``_repr_markdown_`` show as a
picture / formatted text, a worked solution (``steps(sol)``) as data. Schematic cells are
available as ``schemat("name")``.

Nothing here is said in words: what goes wrong is an issue type (``electro.issues``), sent
as JSON — ``{"type": "MissingData", "targets": ["R_{2}"], …}``, math in LaTeX — and the
notebook says it in the reader's language. Python's own errors (NameError, …) stay as
Python says them.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import traceback
import warnings
from dataclasses import fields, is_dataclass

import sympy as sp
from electro.analysis import bode, sweep, tolerance
from electro.components import Law
from electro.issues import Equals, Issue, IsZero, issue
from electro.task import Task
from electro_render import Steps, symbol_library
from electro_schematic import Schematic
from electro_schematic.issues import Unsupported
from sympy import I as sp_I

CELL = "<cell>"
PRELUDE = """
from electro import *
from electro_render import schematic, steps
from electro_schematic import Schematic, layout
"""

namespace: dict = {}


@issue
class NoSweepRange(Issue, ValueError):
    """A sweep of an element with no number for its value needs its range typed."""

    element: str


@issue
class NoCircuitInCode(Issue, ValueError):
    """The code view defines no circuit: it should assign one, e.g. ``variable = loop(...)``."""

    variable: str


@issue
class OnlyValuesInCode(Issue, ValueError):
    """The code view made a circuit layout() cannot draw: in code, change only the values
    (add elements on the drawing)."""

    cause: Unsupported


@issue
class PartsNotInCode(Issue, ValueError):
    """A drawing with one's own components edited in its code view: there they are taken apart
    already (their insides are plain elements), so the drawing would lose them."""


@issue
class BadDataEntry(Issue, ValueError):
    """An entry of a schematic's data that is not ``name = value`` (e.g. ``I_R_1 = 0,5``)."""

    entry: str


@issue
class NoSuchSchematic(Issue, KeyError):
    name: str
    available: list


def reset() -> None:
    """Forget everything the cells defined."""
    namespace.clear()
    exec(PRELUDE, namespace)


def symbols() -> str:
    return json.dumps(symbol_library(), ensure_ascii=False)


def variable(name: str) -> str:
    """A schematic's name as the Python variable cells see it: ``"Układ 1"`` → ``układ1``."""
    v = re.sub(r"\W", "", name.lower())
    if not v:
        return "uklad"
    return f"_{v}" if v[0].isdigit() else v


def code(schematic_json: str, name: str) -> str:
    """A drawing as plain electro code, for the code view."""
    return Schematic.from_json(schematic_json).to_code(variable(name))


def from_code(source: str, name: str, old_json: str = "") -> str:
    """The code view edited back into a drawing: run ``source`` and lay out its circuit.

    The circuit is the variable called like the schematic (``uklad``), else the last one the
    code defines. When only values changed, the old drawing (``old_json``) keeps its layout
    with the new values; otherwise the circuit is laid out anew.
    Returns JSON ``{"schematic": ...}`` or ``{"error": {...}}`` (an error output).
    """
    from electro import Circuit
    from electro_schematic import Unsupported, layout

    var = variable(name)
    if old_json and Schematic.from_json(old_json).parts:
        return json.dumps({"error": _error(PartsNotInCode())}, ensure_ascii=False)
    scope: dict = {}
    exec(PRELUDE, scope)
    prelude = set(scope)
    try:
        exec(compile(source, CELL, "exec"), scope)
        found = scope.get(var)
        if not isinstance(found, Circuit):
            defined = [v for k, v in scope.items() if k not in prelude and isinstance(v, Circuit)]
            if not defined:
                raise NoCircuitInCode(var)
            found = defined[-1]
        kept = _same_but_values(Schematic.from_json(old_json), found, var) if old_json else None
        if kept is not None:
            return json.dumps({"schematic": json.loads(kept.to_json())}, ensure_ascii=False)
        try:
            fresh = layout(found)
        except Unsupported as err:
            raise OnlyValuesInCode(err) from None
        return json.dumps({"schematic": json.loads(fresh.to_json())}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — any mistake in the code is shown to the user
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def _same_but_values(old: Schematic, circuit, variable: str) -> Schematic | None:
    """``old`` with the values from ``circuit``, if that makes it the same circuit (else None)."""
    from electro.codegen import code
    from electro.semantics import structure
    from electro.values import UNKNOWN, to_text

    parts = structure(circuit).parts
    ids = {e.id for e in old.elements}
    if not set(parts) <= ids:
        return None
    for e in old.elements:
        if e.id in parts:
            c = parts[e.id].component
            e.value = to_text(c.value) if c.has_value and c.value is not UNKNOWN else None
    try:
        return old if old.to_code(variable) == code(circuit, variable) else None
    except Exception:  # noqa: BLE001 — an unfinished old drawing: lay out the new circuit instead
        return None


def _parse_data(text: str) -> dict[str, str]:
    """``"I_R_1 = 0,5; U_R_2 = 4"`` (``;`` or new lines between entries) → keyword arguments for solve()."""
    given = {}
    for entry in text.replace("\n", ";").split(";"):
        if not entry.strip():
            continue
        name, sep, value = entry.partition("=")
        if not sep or not name.strip() or not value.strip():
            raise BadDataEntry(entry.strip())
        given[name.strip()] = value.strip()
    return given


def _givens(marks) -> list:
    """Its marks given a value (an arrow's, a point's, a loop's): each an equation for the solver."""
    import sympy as sp
    from electro.values import parse

    return [sp.Eq(q, parse(e.value.strip())) for e, q in marks if e.value and e.value.strip()]


def simulate(schematic_json: str, data: str = "") -> str:
    """The run button of a schematic cell: solve the drawing and report every element's values.

    Returns JSON ``{"results": {id: {...}}, "problems": [{"kind": "warning" | "error", "issue": {...}}]}``:
    ``results`` go on the drawing and in the table under it; ``problems`` behind the warning
    button on the board (``text`` instead of ``issue`` for an error that is not ours).
    """
    from electro.components import notation
    from electro.values import UNKNOWN, fmt

    sch = Schematic.from_json(schematic_json)
    results: dict[str, dict] = {}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            # what it marks (arrows, points, loops), given: the solver's data
            marks = sch.quantities()
            solution = sch.to_circuit().solve(*_givens(marks), **_parse_data(data))
        except (Issue, ValueError, KeyError) as err:
            return json.dumps({"results": {}, "problems": [_problem("error", err)]}, ensure_ascii=False)
    for label in solution.system.parts:
        r = solution[label]
        comp = r.component
        current = r.I if r.I is not None and r.I.is_real and r.I.is_number else None
        sign = -1 if current is not None and current < 0 else 1
        if r.realized is not None:
            value = notation(r.realized)
        elif comp.has_value:
            value = fmt(r.value, comp.unit) if r.value is not None else "?"
        else:
            value = ""
        results[label] = {
            "value": value,
            "solved": (comp.has_value and comp.value is UNKNOWN and r.value is not None) or r.realized is not None,
            "U": fmt(sign * r.U, "V") if r.U is not None else None,
            "I": fmt(sign * r.I, "A") if r.I is not None else None,
            "P": fmt(r.P, "W") if r.P is not None and not r.P.has(sp_I) else None,
            "reversed": sign < 0,  # the current really flows from the second pin to the first
        }
    # what it marks: what that comes to (or was given)
    for e, q in marks:
        try:
            v = solution(q)
        except Exception:  # noqa: BLE001 — not found by this circuit (a label on nothing): none
            continue
        if v is not None and v.is_number:
            results[e.id] = {
                "value": fmt(v, "A" if e.kind in ("current_arrow", "mesh_current") else "V"),
                "solved": not (e.value and e.value.strip()),
                "U": None,
                "I": None,
                "P": None,
                "reversed": False,
            }
    problems = [_problem("warning", w.message) for w in caught]
    return json.dumps({"results": results, "problems": problems}, ensure_ascii=False)


def frequency(schematic_json: str) -> str:
    """The frequency button of a schematic cell: ``bode()`` of the drawing (its named nodes, else its
    capacitors' and inductors' voltages). Returns JSON ``{"svg": "..."}`` or ``{"error": {...}}``."""
    try:
        return json.dumps({"svg": bode(Schematic.from_json(schematic_json).to_circuit())._repr_svg_()})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def sweep_plot(schematic_json: str, element: str, lo: str = "", hi: str = "") -> str:
    """The sweep in an element's inspector: the outputs as its value goes from ``lo`` to ``hi`` (by
    default a tenth of it to ten times it). Returns JSON ``{"svg": "..."}`` or ``{"error": {...}}``."""
    from electro.solver import _sine_omega

    try:
        circuit = Schematic.from_json(schematic_json).to_circuit()
        if not (lo.strip() and hi.strip()):
            from electro.semantics import structure

            value = structure(circuit).part(element).component.value
            if not isinstance(value, sp.Number):
                raise NoSweepRange(element)
            lo, hi = lo.strip() or value / 10, hi.strip() or value * 10
        svg = sweep(circuit, element, (lo, hi), omega=_sine_omega(circuit))._repr_svg_()
        return json.dumps({"svg": svg})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def spread(schematic_json: str, tol: float = 0.05) -> str:
    """The tolerance button: the named nodes over many builds with every R, C and L within ``tol``.
    Returns JSON ``{"svg": "..."}`` or ``{"error": {...}}``."""
    from electro.solver import _sine_omega

    try:
        circuit = Schematic.from_json(schematic_json).to_circuit()
        return json.dumps({"svg": tolerance(circuit, tol=tol, omega=_sine_omega(circuit))._repr_svg_()})
    except Exception as err:  # noqa: BLE001 — shown under the drawing
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def _task_values(circuit, steps: list[dict], given: list | None = None) -> dict[str, dict]:
    """Each step's value (its ``value``: a quantity or an expression of them) on ``circuit`` with
    ``given`` (its marks' equations): ``{"value": number}``, an AC one as its amplitude, or ``{"error": {...}}``."""
    solution = circuit.solve(*(given or []))
    out: dict[str, dict] = {}
    for step in steps:
        try:
            value = complex(sp.N(solution(step["value"])))
            amplitude = abs(value.imag) > 1e-12 * max(1.0, abs(value))
            out[step["id"]] = {"value": abs(value) if amplitude else value.real}
        except Exception as err:  # noqa: BLE001 — said by the step that has it
            out[step["id"]] = {"error": _error(err)}
    return out


def task_values(schematic_json: str, steps_json: str) -> str:
    """A task's steps on the drawing as it is (the author's, checked in the page). Returns JSON
    ``{"values": {step: {"value": x} | {"error": ...}}}`` or ``{"error": {...}}`` (the circuit)."""
    try:
        sch = Schematic.from_json(schematic_json)
        values = _task_values(sch.to_circuit(), json.loads(steps_json), _givens(sch.quantities()))
        return json.dumps({"values": values}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — shown by the task
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def _readable(value: str) -> str:
    """A number as one would write it on a drawing: ``2200`` → ``2.2k``, ``0.0001`` → ``100µ``;
    anything else (a symbol, a phasor) as it is."""
    from electro.values import fmt, parse

    try:
        number = parse(value)
        return fmt(number).replace(" ", "") if number.is_number and number.is_real else value
    except Exception:  # noqa: BLE001 — not a plain number: as written
        return value


def from_drawing(drawing_json: str, strict: bool = False) -> str:
    """A circuit described as data *and* as drawn — each element's terminals where the picture has them
    (``"at": [[x, y], …]``, grid units, x right, y down, in the kind's terminal order) and the wires as
    polylines (``"wires": [[[x, y], …], …]``) — drawn so: a two-terminal one in the middle between its
    terminals (on a row or a column, at least 4 apart), wires from its pins out to them; an op-amp by
    its + input. Anything touching connects (a wire's end or a pin on another wire's middle, too);
    wires only crossing do not. Ground (node ``0``/``GND``) gets its symbol under its lowest point.
    Its wires joining other than ``nodes`` says, they are laid anew (``"rerouted": true``), the elements
    where they are — or, ``strict``, that said (``{"error": {"mismatch": [...]}}``, each line a node
    split apart or two joined, for whoever drew it to mend); pins of two nodes on one point: the same. For what an AI writes: data, never code. Returns JSON
    ``{"schematic": ...}`` or ``{"error": {...}}``."""
    from electro.issues import BadName, WrongNodeCount
    from electro_schematic.issues import UnknownKind
    from electro_schematic.model import KINDS, MARKS, Element, Wire, on_segment

    def point(p) -> tuple[int, int]:
        x, y = p
        return (round(float(x)), round(float(y)))

    def path(a, b) -> list[tuple[int, int]]:
        """From ``a`` to ``b`` along the grid (one corner when they share no row or column)."""
        return [a, b] if a[0] == b[0] or a[1] == b[1] else [a, (b[0], a[1]), b]

    step = {(1, 0): 0, (0, 1): 90, (-1, 0): 180, (0, -1): 270}

    def polyline(w) -> list:
        """A wire as a model may write it: [[x, y], …], or "[x, y], [x, y]", or [x, y, x, y, …]."""
        if isinstance(w, str):
            w = json.loads(f"[{w}]")
        if w and all(isinstance(v, (int, float)) for v in w):
            w = [w[i : i + 2] for i in range(0, len(w) - 1, 2)]
        return [p for p in w if isinstance(p, (list, tuple)) and len(p) == 2]

    try:
        data = json.loads(drawing_json)
        for el in data["elements"]:  # (a label is a name, never anything else: said back at once)
            if not str(el.get("id")).isidentifier():
                raise BadName(str(el.get("id")))
        # its arrows (a current's, a voltage's: from tail to head, a name) apart: they measure nothing
        arrows = [el for el in data["elements"] if el.get("kind") in MARKS]
        data["elements"] = [el for el in data["elements"] if el.get("kind") not in MARKS]
        # drawn too small (a resistor 2 units long): the whole drawing scaled up, its shape kept
        spans = [
            max(abs(float(a[0]) - float(b[0])), abs(float(a[1]) - float(b[1])))
            for el in data["elements"]
            if len(el.get("at") or []) == 2
            for a, b in [el["at"]]
        ]
        spans = [s for s in spans if s > 0]
        scale = max(1, -(-4 // min(spans))) if spans else 1
        # side by side closer than 6 (their labels on each other): spread out, too
        columns = sorted(
            {
                float(el["at"][0][0])
                for el in data["elements"]
                if len(el.get("at") or []) == 2 and float(el["at"][0][0]) == float(el["at"][1][0])
            }
        )
        rows = sorted(
            {
                float(el["at"][0][1])
                for el in data["elements"]
                if len(el.get("at") or []) == 2 and float(el["at"][0][1]) == float(el["at"][1][1])
            }
        )
        gaps = [b - a for line in (columns, rows) for a, b in zip(line, line[1:]) if b > a]
        if gaps:
            scale = max(scale, -(-6 // min(gaps)))
        if scale > 1:
            for el in data["elements"] + arrows:
                el["at"] = [[float(x) * scale, float(y) * scale] for x, y in el["at"]]
                if el.get("between"):
                    el["between"] = [[float(x) * scale, float(y) * scale] for x, y in el["between"]]
            data["wires"] = [
                [[float(x) * scale, float(y) * scale] for x, y in polyline(w)] for w in data.get("wires") or []
            ]
        elements: list[Element] = []
        wires: list[list[tuple[int, int]]] = []
        terminals: list[tuple[str, int, str, tuple[int, int]]] = []  # element, terminal, node, point
        for el in arrows:  # along its longer side, from its tail; a voltage's as long as drawn
            given = el.get("value")
            if el["kind"] == "mesh_current":  # a loop's: at a point inside it, clockwise unless flipped
                elements.append(
                    Element(
                        str(el["id"]),
                        "mesh_current",
                        point(el["at"][0]),
                        0,
                        _readable(str(given)) if given not in (None, "") else None,
                        str(el.get("text") or ""),
                        flip=True if el.get("flip") else None,
                    )
                )
                continue
            (x1, y1), (x2, y2) = (point(p) for p in el["at"][:2])
            dx, dy = x2 - x1, y2 - y1
            d = ((dx > 0) - (dx < 0), 0) if abs(dx) >= abs(dy) else (0, (dy > 0) - (dy < 0))
            if d == (0, 0):
                raise ValueError(f"{el['id']}: its tail and head on one point")
            length = max(abs(dx), abs(dy))
            elements.append(
                Element(
                    str(el["id"]),
                    str(el["kind"]),
                    (x1, y1),
                    step[d],
                    _readable(str(given)) if given not in (None, "") else None,
                    str(el.get("text") or ""),
                    str(el["of"]) if el.get("of") else None,
                    length if el["kind"] == "voltage_arrow" else None,
                    [list(point(q)) for q in el["between"]][:2] if el.get("between") else None,
                )
            )
        for el in data["elements"]:
            kind = str(el["kind"])
            if kind == "terminal":  # an open end (a network with no source: the picture's own)
                node, there = str(el["nodes"][0]), point(el["at"][0])
                elements.append(Element(str(el["id"]), "terminal", there, 0))
                terminals.append((str(el["id"]), 0, node, there))
                continue
            if kind not in KINDS or KINDS[kind].component is None:
                raise UnknownKind(kind, sorted(k for k, v in KINDS.items() if v.component is not None))
            nodes = [str(n) for n in el["nodes"]]
            pins = KINDS[kind].pins
            if len(nodes) != len(pins):
                raise WrongNodeCount(kind, len(pins), nodes)
            at = [point(p) for p in el["at"]]
            if len(at) != len(pins):
                raise ValueError(f"{el['id']}: {len(pins)} terminal points, not {len(at)}")
            value, text = el.get("value"), el.get("text")
            value = None if value is None else _readable(str(value))
            if len(pins) == 2:
                (x1, y1), (x2, y2) = at
                if x1 != x2 and y1 != y2:  # askew: along its longer side, a wire round the corner to the rest
                    if abs(x2 - x1) >= abs(y2 - y1):
                        y2 = y1
                    else:
                        x2 = x1
                length = abs(x2 - x1) + abs(y2 - y1)
                if length < 4:
                    raise ValueError(f"{el['id']}: its terminals {at} less than 4 apart")
                d = ((x2 > x1) - (x2 < x1), (y2 > y1) - (y2 < y1))
                gap = (length - 4) // 2
                start = (x1 + d[0] * gap, y1 + d[1] * gap)
                e = Element(str(el["id"]), kind, start, step[d], value, text and str(text))
            else:  # an op-amp: as it stands, by its + input
                px, py = at[0]
                e = Element(str(el["id"]), kind, (px - pins[0][0], py - pins[0][1]), 0, value, text and str(text))
            e.component()  # (its name and value checked: BadName, …)
            elements.append(e)
            for i, (pin, there) in enumerate(zip(e.pins(), at)):
                if pin != there:
                    wires.append(path(pin, there))
                terminals.append((e.id, i, nodes[i], pin))
        for w in data.get("wires") or []:
            pts = [point(p) for p in polyline(w)]
            if len(pts) >= 2:  # (a slanted stretch: round its corner)
                wires.append([pts[0]] + [q for a, b in zip(pts, pts[1:]) for q in path(a, b)[1:]])
        # anything touching connects: a wire split where a pin or another wire's end is on its middle
        touch = {p for _, _, _, p in terminals} | {w[0] for w in wires} | {w[-1] for w in wires}
        split: list[list[tuple[int, int]]] = []
        for w in wires:
            cur = [w[0]]
            for a, b in zip(w, w[1:]):
                inner = sorted(
                    (p for p in touch if on_segment(p, a, b)),
                    key=lambda p: abs(p[0] - a[0]) + abs(p[1] - a[1]),
                )
                for p in inner:
                    cur.append(p)
                    split.append(cur)
                    cur = [p]
                cur.append(b)
            split.append(cur)
        # ground: its symbol under the lowest point of node 0
        for name in ("0", "GND"):
            at0 = [p for _, _, n, p in terminals if n == name]
            if at0:
                low = max(at0, key=lambda p: (p[1], -p[0]))
                elements.append(Element("GND1", "ground", low, 0))
                break

        # a node with one terminal only: a wire (or a node's name) left out — the circuit itself wrong,
        # whatever the drawing: said back, for another go
        count: dict[str, int] = {}
        for _, _, name, _ in terminals:
            count[name] = count.get(name, 0) + 1
        alone = [
            f"{eid}'s terminal {i + 1} (node {name}) is joined to nothing"
            for eid, i, name, _ in terminals
            if count[name] == 1
        ]
        if alone:
            return json.dumps({"error": {"type": "error", "data": "; ".join(alone), "dangling": alone}})

        def drawn_as(lines) -> tuple[Schematic, list[str]]:
            """The drawing with these wires, and where it joins other than the nodes say."""
            sch = Schematic(elements=elements, wires=[Wire(w) for w in lines if len(set(w)) > 1])
            nodes_of = sch.nodes()
            drawn: dict[str, set] = {}
            said: dict[object, set] = {}
            for _, _, name, p in terminals:
                drawn.setdefault("GND" if name == "0" else name, set()).add(nodes_of[p])
                said.setdefault(nodes_of[p], set()).add("GND" if name == "0" else name)
            return sch, [
                f"node {n} is drawn as {len(parts)} separate pieces" for n, parts in drawn.items() if len(parts) > 1
            ] + [f"nodes {', '.join(sorted(ns))} are drawn joined" for ns in said.values() if len(ns) > 1]

        sch, mismatch = drawn_as(split)
        rerouted = False
        if mismatch and not strict:
            # its wires not as its nodes: the elements kept where the picture has them, the wires laid
            # anew — each node's pins joined, the nearest first, along the grid (ends only on pins:
            # nothing else joined)
            routes: list[list[tuple[int, int]]] = []
            by_node: dict[str, list[tuple[int, int]]] = {}
            for _, _, name, p in terminals:
                by_node.setdefault("GND" if name == "0" else name, []).append(p)
            for pts in by_node.values():
                pts = list(dict.fromkeys(pts))
                joined, rest = [pts[0]], pts[1:]
                while rest:
                    a, b = min(
                        ((a, b) for a in joined for b in rest),
                        key=lambda ab: abs(ab[0][0] - ab[1][0]) + abs(ab[0][1] - ab[1][1]),
                    )
                    routes.append(path(a, b))
                    joined.append(b)
                    rest.remove(b)
            sch, mismatch = drawn_as(routes)
            rerouted = True
        if mismatch:  # (pins of two nodes on one point: no drawing of it here)
            return json.dumps({"error": {"type": "error", "data": "; ".join(mismatch), "mismatch": mismatch}})
        sch.to_circuit()  # (it solves as a circuit)
        return json.dumps({"schematic": json.loads(sch.to_json()), "rerouted": rerouted}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — said back to whoever described it
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def render_svg(schematic_json: str) -> str:
    """A drawing as a picture (SVG, its styles in it): to set beside the one it was read from."""
    from electro_render import schematic

    return schematic(Schematic.from_json(schematic_json))._repr_svg_()


def netlist_of(schematic_json: str) -> str:
    """A drawing as data, the way ``from_drawing`` takes it (ground ``0``): for an AI to read a
    note's circuits. Returns JSON ``{"elements": [...]}`` or ``{"error": {...}}``."""
    from electro.circuit import GROUND
    from electro_schematic.model import KINDS

    try:
        sch = Schematic.from_json(schematic_json)
        named = sch.node_names()
        elements = [
            {
                "id": e.id,
                "kind": e.kind,
                "value": e.value,
                "text": e.text,
                "nodes": ["0" if named.get(p) == GROUND else named.get(p, "?") for p in e.pins()],
            }
            for e in sch.elements
            if e.kind in KINDS and KINDS[e.kind].component is not None
        ]
        return json.dumps({"elements": elements}, ensure_ascii=False)
    except Exception as err:  # noqa: BLE001 — the AI is told it could not be read
        return json.dumps({"error": _error(err)}, ensure_ascii=False)


def live(schematic_json: str) -> str:
    """The play button of a schematic cell: the drawing compiled for the page's engine
    (``simulation/engine.ts``), and where on the drawing each node is.

    Returns JSON ``{"program": {...}, "wires": [node per wire], "pins": {id: [node per pin]}}``
    (``null`` for a wire that touches no element), or ``{"error": {...}}`` (an error output).
    """
    from electro.sim import compile_sim

    try:
        sch = Schematic.from_json(schematic_json)
        program = compile_sim(sch.to_circuit())
    except Exception as err:  # noqa: BLE001 — shown on the board
        return json.dumps({"error": _error(err)}, ensure_ascii=False)
    names = sch.node_names()
    return json.dumps(
        {
            "program": json.loads(program.to_json()),
            "wires": [names.get(w.points[0]) for w in sch.wires],
            "pins": {
                e.id: [names.get(p) for p in e.pins()]
                for e in sch.elements
                if e.kind == "part" or e in sch.components()
            },
        },
        ensure_ascii=False,
    )


def to_json(x):
    """An issue, a reason or a solution's steps as JSON: ``{"type": "OhmsLaw", "label": "R_{1}"}``.
    Quantities and expressions become LaTeX (``R_{1}``, ``\\frac{U}{I}``), the rest stays as it is."""
    from electro_render.trace import expr, name, value

    if isinstance(x, Law):
        return {"equation": f"{expr(x.expr)} = 0", "reason": to_json(x.reason)}
    if isinstance(x, Equals):
        return f"{name(x.symbol.name)} = {value(x.value, x.unit)}"
    if isinstance(x, IsZero):
        return f"{expr(x.expr)} = 0"
    if isinstance(x, Issue) or (is_dataclass(x) and not isinstance(x, type)):
        shown = [f for f in fields(x) if f.metadata.get("shown", True)] if is_dataclass(x) else []
        return {"type": type(x).__name__, **{f.name: to_json(getattr(x, f.name)) for f in shown}}
    if isinstance(x, sp.Symbol):
        return name(x.name)
    if isinstance(x, sp.Basic):
        return expr(x)
    if isinstance(x, (list, tuple)):
        return [to_json(v) for v in x]
    return x


def _problem(kind: str, err) -> dict:
    """For the board's warning button: our issue as data, anything else as its text."""
    return {"kind": kind, "issue": to_json(err)} if isinstance(err, Issue) else {"kind": kind, "text": str(err)}


def to_output(obj) -> dict:
    if isinstance(obj, Schematic):  # a schematic cell's variable on its own: show the drawing
        from electro_render import schematic

        obj = schematic(obj)
    if isinstance(obj, Steps):
        return {"type": "solution", "data": to_json(obj)}
    if isinstance(obj, Task):  # a field to answer in: the answer only as hashes (electro.task)
        from electro_render.trace import name

        return {
            "type": "task",
            "prompt": obj.prompt,
            "quantity": obj.quantity,
            "tex": name(obj.quantity),
            "unit": obj.unit,
            "tol": obj.tol,
            "hashes": list(obj.hashes),
            "amplitude": obj.amplitude,
        }
    if isinstance(obj, Issue):  # an error caught and shown on purpose: display(e)
        kind = "warning" if isinstance(obj, Warning) else "error"
        return {"type": "issue", "kind": kind, "data": repr(obj), "issue": to_json(obj)}
    for method, kind in (("_repr_svg_", "svg"), ("_repr_markdown_", "markdown"), ("_repr_latex_", "markdown")):
        data = getattr(obj, method, lambda: None)()  # sympy defines some of these and returns None
        if data is not None:
            return {"type": kind, "data": data}
    return {"type": "text", "data": repr(obj)}


def _error(err: BaseException) -> dict:
    """An error output: our issue as data (``issue``), anything else as Python says it; ``line``:
    the line of the cell it came from (not the library internals)."""
    lines = [frame.lineno for frame in traceback.extract_tb(err.__traceback__) if frame.filename == CELL]
    out: dict = {"type": "error", "data": repr(err) if isinstance(err, Issue) else f"{type(err).__name__}: {err}"}
    if isinstance(err, Issue):
        out["issue"] = to_json(err)
    if lines:
        out["line"] = lines[-1]
    return out


def _warning(message) -> dict:
    if isinstance(message, Issue):
        return {"type": "warning", "data": repr(message), "issue": to_json(message)}
    return {"type": "warning", "data": str(message)}


def run(code: str, schematics_json: str = "{}", standard: str = "iec") -> str:
    """Run one cell; returns a JSON list of outputs ``{"type": ..., "data": ...}``. Schematics are
    drawn with ``standard``'s symbols (the note's: "iec" or "ieee")."""
    from electro_render.symbols import use

    use(standard)
    outputs: list[dict] = []
    drawings = {name: Schematic.from_json(text) for name, text in json.loads(schematics_json).items()}

    def schemat(name: str) -> Schematic:
        if name not in drawings:
            raise NoSuchSchematic(name, list(drawings))
        return drawings[name]

    namespace["schemat"] = schemat
    for name, drawing in drawings.items():  # "Układ 1" is układ1 in code
        namespace[variable(name)] = drawing
    namespace["display"] = lambda *objects: outputs.extend(to_output(o) for o in objects)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.simplefilter("ignore", DeprecationWarning)  # the libraries' own (sympy's), not the reader's
        try:
            tree = ast.parse(code, CELL)
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            exec(compile(tree, CELL, "exec"), namespace)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), CELL, "eval"), namespace)
                if value is not None:
                    outputs.append(to_output(value))
        except Exception as err:  # noqa: BLE001 — every error is shown to the user
            outputs.append(_error(err))
    printed = stdout.getvalue()
    if printed:
        outputs.insert(0, {"type": "stream", "data": printed})
    outputs += [_warning(w.message) for w in caught]
    return json.dumps(outputs, ensure_ascii=False)


reset()
