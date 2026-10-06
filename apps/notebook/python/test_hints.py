"""What would help when the data do not do, and that names and expressions people write are read, never run."""

import pytest
from electro import GND, Contradiction, CurrentSource, I, MissingData, Node, Parameter, Resistor, U, VoltageSource
from electro_notebook.hints import clashing, pinning
from electro_notebook.names import BadExpression, evaluated, expression

RUN = "__import__('os').system('echo pwned')"


def test_contradiction_names_the_clashing_data():
    e, r = (VoltageSource("E"), Resistor("R"))
    with pytest.raises(Contradiction) as err:
        (~(e >> r)).final({e: 12, r: 10, I(r): 5})
    assert {e, r, I(r)} == set(clashing(err.value))


def test_missing_data_says_what_would_help():
    circuit, given, (r1, r2, r3, e2) = _three_unknowns()
    s = circuit.final({**given, I(r1): 2, U(r2): 8})
    with pytest.raises(MissingData) as err:
        s.answers(Parameter(r1), Parameter(r3), Parameter(e2))
    assert U(r3) in pinning(err.value)


@pytest.mark.parametrize(
    "text",
    [RUN, "().__class__", "a.b", "f(x)", "x[0]", "lambda: 1", "9**9**9", "'s'", "True", "(" * 400 + "1" + ")" * 400],
)
def test_an_expression_is_read_not_run(text):
    with pytest.raises(BadExpression):
        expression(text)


def test_queries_as_people_write_them_still_work():
    e, r = (VoltageSource("E"), Resistor("R_1"))
    s = (~(e >> r)).final({e: 12, r: 10})
    assert evaluated("U_R_1 / I_R_1", s) == 10 and evaluated("sqrt(P_R_1 * R_1)", s) == 12
    with pytest.raises(BadExpression):
        evaluated(RUN, s)


def _three_unknowns():
    e1, e2, j, r1, r2, r3 = (
        VoltageSource("E_1"),
        VoltageSource("E_2"),
        CurrentSource("J"),
        Resistor("R_1"),
        Resistor("R_2"),
        Resistor("R_3"),
    )
    top, mid = (Node("TOP"), Node("MID"))
    circuit = (
        (GND >> e1 >> Node() >> r1 >> top)
        @ (top >> r2 >> GND)
        @ (mid >> r3 >> GND)
        @ (GND >> j >> mid)
        @ (top >> e2 >> mid)
    )
    return (circuit, {e1: 12, r2: 4, j: 1}, (r1, r2, r3, e2))
