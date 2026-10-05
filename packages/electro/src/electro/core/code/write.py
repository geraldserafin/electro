"""A problem as electro code: its elements, its named points, the circuit — series ``>>`` and parallel
``|`` where it is made of them (``structure``), else each element at its points — and its data."""

from __future__ import annotations

import keyword
from collections.abc import Mapping

from electro.values import to_text

from ..circuit import elements
from ..circuit.elements.parts import Part
from ..circuit.kind import Kind
from ..circuit.netlist import labels
from ..circuit.tree import Element, netlist
from ..problem.netlist import point_names, quantity_data
from ..problem.problem import Problem
from ..problem.quantities import Quantity
from .structure import Between, Leaf, Loop, Named, Parallel, Series, Shape, Tree, shape

CONSTRUCTORS: dict[str, str] = {
    kind.name: name for name in elements.__all__ if isinstance(kind := getattr(elements, name), Kind)
}
"""Each kind by the name it is made with: ``"voltage_source"`` → ``VoltageSource``."""

QUANTITIES = {"I": "I", "U": "U", "P": "P", "value": "Parameter", "V": "V"}


def code(problem: Problem, name: str = "uklad") -> str:
    net = netlist(problem.circuit)
    ids = labels(net)
    names = point_names(net)
    found = shape(problem)
    lines = [f'{_variable(id)} = {CONSTRUCTORS[e.kind.name]}("{id}")' for id, (e, _) in zip(ids, net.parts)]
    points = sorted({n for n in names if n != "GND"} & _points_used(found, names))
    lines += [f'{_point(n)} = Node("{n}")' for n in points]
    circuit = _circuit(found) if found is not None else _netlist(net, ids, names)
    data = _data(problem, dict(zip((e for e, _ in net.parts), ids)), {p: names[n] for n, p in net.named})
    lines.append(f"{name} = Problem({circuit}, {{{data}}})" if data else f"{name} = Problem({circuit})")
    return "\n".join(lines)


def _variable(id: str) -> str:
    return f"{id}_" if keyword.iskeyword(id) else id


def _point(name: str) -> str:
    return "GND" if name == "GND" else f"node_{name}"


def _points_used(found: Shape | None, names: list[str]) -> set[str]:
    if found is None:
        return set(names)
    used = {found.a, found.b} if isinstance(found, Between) else set()
    trees = list(found.parts) if isinstance(found, Loop) else [found.tree]
    while trees:
        t = trees.pop()
        if isinstance(t, Named):
            used.add(t.name)
        elif isinstance(t, Series | Parallel):
            trees += t.parts
    return used


def _circuit(found: Shape) -> str:
    if isinstance(found, Loop):
        return f"loop({', '.join(_tree(p, top=True) for p in found.parts)})"
    return f"{_point(found.a)} >> {_tree(found.tree)} >> {_point(found.b)}"


def _tree(t: Tree, top: bool = False) -> str:
    match t:
        case Leaf(_, id, kind, flipped):
            name = _variable(id)
            return f"flip({name})" if flipped and kind not in ("resistor", "capacitor", "inductor") else name
        case Named(name):
            return _point(name)
        case Series(parts):
            text = " >> ".join(_tree(p) for p in parts)
            return text if top else f"({text})"
        case Parallel(parts):
            return f"({' | '.join(_tree(p) for p in parts)})"
    raise TypeError(t)


def _netlist(net, ids: tuple[str, ...], names: list[str]) -> str:
    placed = [f"at({_variable(id)}, {', '.join(_point(names[n]) for n in ns)})" for id, (_, ns) in zip(ids, net.parts)]
    return "beside(\n    " + ",\n    ".join(placed) + ",\n)"


def _data(problem: Problem, ids: Mapping[Element, str], points: Mapping) -> str:
    out = []
    for key, value in problem.given.items():
        if isinstance(key, Element):
            out.append(f"{_variable(ids[key])}: {_value(value)}")
        elif isinstance(key, Quantity):
            out.append(f"{_quantity(quantity_data(key, ids, points))}: {_value(value)}")
        else:
            out.append(f"{key!r}: {_value(value)}")
    return ", ".join(out)


def _value(value: object) -> str:
    if isinstance(value, Part):
        return f"part({value.name!r})"
    if isinstance(value, Mapping):
        return "{" + ", ".join(f"{w!r}: {_value(v)}" for w, v in value.items()) + "}"
    text = to_text(value)
    try:
        float(text or "")
        return text or "None"
    except ValueError:
        return repr(text)


def _quantity(data: list) -> str:
    match data:
        case ["U_between", a, b]:
            return f"U({_point(a)}, {_point(b)})"
        case ["V", n]:
            return f"V({_point(n)})"
        case ["sum", terms]:
            return " + ".join(f"{k:g} * {_quantity(q)}" for k, q in terms)
        case [what, id]:
            return f"{QUANTITIES[what]}({_variable(id)})"
    raise TypeError(data)
