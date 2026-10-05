"""SPICE netlists both ways on the core: ``to_spice`` then ``from_spice`` gives the same netlist back, and
LTspice's netlists are read. And against ngspice: the same circuits, the same numbers — point potentials in
DC, AC and in time, linear and not (skipped where there is no ngspice; it is in devenv)."""

import math
import re
import shutil
import subprocess

import pytest
from electro import AC, V, from_spice, simulate, solve, to_netlist, to_spice
from electro.problem.netlist import from_netlist

NGSPICE = shutil.which("ngspice")
needs_ngspice = pytest.mark.skipif(NGSPICE is None, reason="no ngspice on PATH")


def circuit(*items):
    """A netlist as data: each ``(id, kind, value, nodes…)``; a value a dict gives its parameters too."""
    elements = []
    for id, kind, value, *nodes in items:
        params = value if isinstance(value, dict) else {"": value}
        main = params.pop("", None)
        elements.append({"id": id, "kind": kind, "value": main, "params": params, "nodes": list(nodes)})
    return from_netlist({"elements": elements})


def ngspice(net, analysis: str, nodes: list[str], tmp_path) -> dict[str, complex]:
    """``nodes``' potentials after ``analysis`` (``op``, ``ac lin 1 f f``), as ngspice prints them."""
    deck = tmp_path / "deck.cir"
    shown = " ".join(f"v({n})" for n in nodes)
    deck.write_text(to_spice(net.problem) + f".control\nset numdgt=12\n{analysis}\nprint {shown}\n.endc\n.end\n")
    out = subprocess.run([NGSPICE, "-b", str(deck)], capture_output=True, text=True, timeout=60).stdout
    values = {}
    for name, re_, im in re.findall(r"^v\((\w+)\) = ([-+\d.e]+)(?:,([-+\d.e]+))?$", out, re.M):
        values[name] = complex(float(re_), float(im or 0))
    assert set(values) == {n.lower() for n in nodes}, out
    return values


def ngspice_tran(net, t_end: float, node: str, at: list[float], tmp_path) -> list[float]:
    deck, data = tmp_path / "deck.cir", tmp_path / "out.txt"
    step = t_end / 2000
    deck.write_text(
        to_spice(net.problem) + f".control\ntran {step} {t_end} uic\nwrdata {data} v({node})\n.endc\n.end\n"
    )
    subprocess.run([NGSPICE, "-b", str(deck)], capture_output=True, timeout=60, check=True)
    rows = [tuple(map(float, line.split()[:2])) for line in data.read_text().splitlines() if line.strip()]
    return [min(rows, key=lambda r: abs(r[0] - t))[1] for t in at]


def grid(n: int):
    items = [("E", "voltage_source", 10, "GND", "n0_0")]
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                items.append((f"Rv{i}{j}", "resistor", 100 + 7 * i, f"n{i}_{j}", f"n{i + 1}_{j}"))
            if j + 1 < n:
                items.append((f"Rh{i}{j}", "resistor", 220 + 13 * j, f"n{i}_{j}", f"n{i}_{j + 1}"))
    return circuit(*items, ("R_end", "resistor", 50, f"n{n - 1}_{n - 1}", "GND"))


LINEAR_DC = {
    "divider": (
        circuit(
            ("E", "voltage_source", 12, "GND", "T"),
            ("R_1", "resistor", "1k", "T", "A"),
            ("R_2", "resistor", "2.2k", "A", "GND"),
        ),
        ["A"],
    ),
    "bridge": (
        circuit(
            ("E", "voltage_source", 10, "GND", "T"),
            ("R_1", "resistor", 100, "T", "A"),
            ("R_2", "resistor", 220, "T", "B"),
            ("R_3", "resistor", 330, "A", "GND"),
            ("R_4", "resistor", 470, "B", "GND"),
            ("R_5", "resistor", 1000, "A", "B"),
        ),
        ["A", "B"],
    ),
    "grid": (grid(4), ["n3_3", "n1_2", "n2_1"]),
    "current source": (
        circuit(
            ("J", "current_source", "10m", "GND", "A"),
            ("R_1", "resistor", 1000, "A", "B"),
            ("R_2", "resistor", 500, "B", "GND"),
        ),
        ["A", "B"],
    ),
    "inverting amplifier": (
        circuit(
            ("E", "voltage_source", 1, "GND", "IN"),
            ("R_1", "resistor", "1k", "IN", "X"),
            ("R_2", "resistor", "10k", "X", "OUT"),
            ("OA", "opamp", None, "GND", "X", "OUT"),
            ("R_L", "resistor", "2k", "OUT", "GND"),
        ),
        ["OUT"],
    ),
    "controlled sources": (
        circuit(
            ("E", "voltage_source", 2, "GND", "A"),
            ("R_1", "resistor", 100, "A", "GND"),
            ("K_1", "vcvs", 3, "A", "GND", "GND", "B"),
            ("R_2", "resistor", 200, "B", "GND"),
            ("K_2", "vccs", "10m", "A", "GND", "GND", "C"),
            ("R_3", "resistor", 300, "C", "GND"),
        ),
        ["B", "C"],
    ),
    "current-controlled sources": (
        circuit(
            ("E", "voltage_source", 2, "GND", "A"),
            ("F_1", "cccs", 3, "A", "X", "GND", "B"),
            ("R_1", "resistor", 10, "X", "GND"),
            ("R_2", "resistor", 200, "B", "GND"),
            ("H_1", "ccvs", 50, "B", "Y", "GND", "C"),
            ("R_3", "resistor", 40, "Y", "GND"),
            ("R_4", "resistor", 300, "C", "GND"),
        ),
        ["B", "C", "X"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", LINEAR_DC)
def test_dc_matches_ngspice(name, tmp_path):
    net, nodes = LINEAR_DC[name]
    sol = solve(net.problem)
    spice = ngspice(net, "op", nodes, tmp_path)
    for n in nodes:
        rel = 5e-5 if "amplifier" in name else 1e-9  # ngspice's op-amp: a gain of 10⁶, not ∞
        assert float(sol(V(net.points[n]))) == pytest.approx(spice[n.lower()].real, rel=rel, abs=1e-12)


AC_CIRCUITS = {
    "rc": (
        circuit(
            ("E", "voltage_source", 1, "GND", "T"),
            ("R", "resistor", "1k", "T", "A"),
            ("C", "capacitor", "1u", "A", "GND"),
        ),
        ["A"],
    ),
    "rlc": (
        circuit(
            ("E", "voltage_source", 1, "GND", "T"),
            ("R", "resistor", 10, "T", "A"),
            ("L", "inductor", "10m", "A", "B"),
            ("C", "capacitor", "1u", "B", "GND"),
        ),
        ["A", "B"],
    ),
    "coupled": (
        circuit(
            ("E", "voltage_source", 1, "GND", "A"),
            ("R_1", "resistor", 1, "A", "B"),
            ("M", "coupled", {"": "1m", "L1": "2m", "L2": "3m"}, "B", "GND", "GND", "C"),
            ("R_2", "resistor", 100, "C", "GND"),
        ),
        ["B", "C"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", AC_CIRCUITS)
@pytest.mark.parametrize("f", [50, 1591.55, 20_000])
def test_ac_matches_ngspice(name, f, tmp_path):
    net, nodes = AC_CIRCUITS[name]
    sol = solve(net.problem, AC(2 * math.pi * f))
    spice = ngspice(net, f"ac lin 1 {f} {f}", nodes, tmp_path)
    for n in nodes:
        assert complex(sol(V(net.points[n]))) == pytest.approx(spice[n.lower()], rel=1e-6, abs=1e-12)


@needs_ngspice
def test_rc_in_time_matches_ngspice(tmp_path):
    net = circuit(
        ("E", "voltage_source", 5, "GND", "T"), ("R", "resistor", "1k", "T", "A"), ("C", "capacitor", "1u", "A", "GND")
    )
    at = [0.2e-3, 1e-3, 3e-3]
    ours = simulate(net.problem, until=4e-3)
    for t, s in zip(at, ngspice_tran(net, 4e-3, "A", at, tmp_path)):
        assert ours.at("V_A", t) == pytest.approx(s, rel=0.01)


NONLINEAR = {
    "1N4148 and a resistor": (
        [("E", "voltage_source", 5, "GND", "T"), ("R", "resistor", 430, "T", "A"), ("D", "diode", None, "A", "GND")],
        {"D": "1N4148"},
        ["A"],
    ),
    "BC547B with a base resistor": (
        [
            ("E", "voltage_source", 9, "GND", "VCC"),
            ("R_B", "resistor", "100k", "VCC", "B"),
            ("R_C", "resistor", "1k", "VCC", "C"),
            ("Q", "npn", None, "B", "C", "GND"),
        ],
        {"Q": "BC547B"},
        ["B", "C"],
    ),
}


@needs_ngspice
@pytest.mark.parametrize("name", NONLINEAR)
def test_nonlinear_operating_point_matches_ngspice(name, tmp_path):
    """Ours settle in time (no DC solve of a diode); theirs is the operating point."""
    items, parts, nodes = NONLINEAR[name]
    data = {
        "elements": [
            {"id": id, "kind": kind, "value": value, "nodes": list(ns), **({"part": parts[id]} if id in parts else {})}
            for id, kind, value, *ns in items
        ]
    }
    net = from_netlist(data)
    trace = simulate(net.problem, until=5e-3)
    spice = ngspice(net, "op", nodes, tmp_path)
    for n in nodes:
        assert trace(f"V_{n}")[-1] == pytest.approx(spice[n.lower()].real, rel=2e-3, abs=2e-3)


def test_netlist_round_trip():
    elements = [
        ("E_1", "voltage_source", ["GND", "IN"], {"value": "12"}),
        ("R_1", "resistor", ["IN", "A"], {"value": "4.7k"}),
        ("C_1", "capacitor", ["A", "GND"], {"value": "100n"}),
        ("L_1", "inductor", ["A", "B"], {"value": "1m"}),
        ("D_1", "diode", ["B", "GND"], {"part": "1N4148"}),
        ("Q_1", "npn", ["A", "B", "GND"], {"part": "2N3904"}),
        ("J_1", "current_source", ["GND", "B"], {"value": "1m"}),
        ("M", "coupled", ["A", "GND", "GND", "C"], {"value": "1m", "params": {"L1": "2m", "L2": "3m"}}),
        ("G_1", "vccs", ["A", "GND", "GND", "C"], {"value": "10m"}),
        ("E_2", "vcvs", ["A", "GND", "GND", "D"], {"value": "3"}),
        ("S", "sine_source", ["GND", "X"], {"value": "1", "params": {"f": "1k", "phase": "90"}}),
        ("P", "square_source", ["GND", "Y"], {"value": "5", "params": {"f": "1k", "duty": "0.25"}}),
        ("A_1", "ammeter", ["X", "Y"], {}),
    ]
    data = {"elements": [{"id": id, "kind": kind, "nodes": nodes, **rest} for id, kind, nodes, rest in elements]}
    netlist = to_spice(from_netlist(data).problem)
    assert to_spice(from_spice(netlist)) == netlist  # the parts' names too
    assert "Q1 B A 0 Q1_2N3904" in netlist and "KM LMa LMb 0.408248290464" in netlist


def test_reads_an_ltspice_netlist():
    text = """* C:\\\\users\\\\me\\\\rc.asc
V1 N001 0 SINE(0 1 1k) AC 1
R1 N001 out 1.5k
C1 out 0 100n
D1 out 0 1N4148
D2 out 0 Dx
.model D D
.model Dx D(Is=2.52n Rs=.568 N=1.752 Cjo=4p M=.4 tt=20n Iave=200m Vpk=75 mfg=OnSemi type=silicon)
.tran 5m
.backanno
.end
"""
    got = {e["id"]: e for e in to_netlist(from_spice(text))["elements"]}
    assert got["R1"]["value"] == "1500" and got["C1"]["value"] == "100n"
    assert got["V1"]["kind"] == "sine_source" and got["V1"]["params"]["f"] == "1000"
    assert got["D1"]["part"] == "1N4148" and got["D2"]["params"] == {"I_S": "2.52n", "n": "1.752"}
    assert got["V1"]["nodes"] == ["GND", "N001"]  # its + on its second end
