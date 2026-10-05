"""Text from a drawing, a query or a netlist never runs as code: labels, point names and expressions come
from notes other people send (a link, a course), so nothing in them may reach eval or exec."""

import pytest
import sympy as sp
from electro import GND, BadName, I, Node, Problem, Resistor, VoltageSource, from_netlist, from_spice, loop, solve
from electro.values import BadExpression, expression

RUN = "__import__('os').system('echo pwned')"
BAD = [f"a+{RUN}", f"x)+{RUN}+(1", "R 1", "R'", "1R", "\\href{javascript:alert(1)}{x}"]


@pytest.mark.parametrize("name", BAD)
def test_a_name_that_is_not_a_name_is_refused(name):
    with pytest.raises(BadName):
        Resistor(name)
    if not name[0].isdigit():  # a point may be called "3", as SPICE calls them
        with pytest.raises(BadName):
            Node(name)
    loop_ = {"elements": [{"id": name, "kind": "resistor", "nodes": ["GND", "A"]}]}
    with pytest.raises(BadName):
        from_netlist(loop_)
    if not name[0].isdigit():
        with pytest.raises(BadName):
            from_netlist({"elements": [{"id": "R_1", "kind": "resistor", "nodes": ["GND", name]}]})


def test_a_spice_netlist_names_nothing_but_names():
    with pytest.raises(BadName):
        from_spice(f"* x\nR1+{RUN} a 0 1k\n")


def test_names_as_people_write_them_still_work():
    e, r1, r2, out = VoltageSource("V_zas"), Resistor("R1"), Resistor("R_2"), Node("wyjście")
    assert solve(Problem(GND >> e >> r1 >> out >> r2 >> GND, {e: 12, r1: 10, r2: 20}))(I(r1)) == sp.Rational(2, 5)


@pytest.mark.parametrize(
    "text",
    [RUN, "().__class__", "a.b", "f(x)", "x[0]", "lambda: 1", "9**9**9", "'s'", "True", "(" * 400 + "1" + ")" * 400],
)
def test_an_expression_is_read_not_run(text):
    with pytest.raises(BadExpression):
        expression(text)


def test_queries_as_people_write_them_still_work():
    e, r = VoltageSource("E"), Resistor("R_1")
    s = solve(Problem(loop(e, r), {e: 12, r: 10}))
    assert s("U_R_1 / I_R_1") == 10 and s("sqrt(P_R_1 * R_1)") == 12
    with pytest.raises(BadExpression):
        s(RUN)
