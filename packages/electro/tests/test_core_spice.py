"""SPICE netlists both ways on the core: ``to_spice`` then ``from_spice`` gives the same netlist back, and
LTspice's netlists are read."""

from electro.core import from_spice, to_netlist, to_spice
from electro.core.problem.netlist import from_netlist


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
