"""Text from a drawing or a query never runs as code: labels, node names and quantity expressions
come from notes other people send (a link, a course), so nothing in them may reach eval or exec."""

import electro as e
import pytest
from electro.issues import BadExpression, BadName
from electro.values import expression

RUN = "__import__('os').system('echo pwned')"


@pytest.mark.parametrize("label", [f"a+{RUN}", f"x)+{RUN}+(1", "R 1", "R'", "1R", "\\href{javascript:alert(1)}{x}"])
def test_a_label_that_is_not_a_name_is_refused(label):
    c = e.supply(12) + e.Resistor(10, label=label) + e.Capacitor("1u") + e.ground
    for run in (c.solve, lambda: e.bode(c), lambda: e.tolerance(c, runs=2), lambda: e.code(c)):
        with pytest.raises(BadName):
            run()


def test_a_node_name_that_is_not_a_name_is_refused():
    c = e.net((e.VoltageSource(12), "0", f"A+{RUN}"), (e.Resistor(10), f"A+{RUN}", "0"))
    with pytest.raises(BadName):
        c.solve()


def test_names_as_people_write_them_still_work():
    c = e.net(
        (e.VoltageSource(12, label="V_zas"), "0", "3"),
        (e.Resistor(10, label="R1"), "3", "wyjście"),
        (e.Resistor(20), "wyjście", "0"),
    )
    assert c.solve().V("wyjście") == 8


@pytest.mark.parametrize(
    "text",
    [RUN, "().__class__", "a.b", "f(x)", "x[0]", "lambda: 1", "9**9**9", "'s'", "True", "(" * 400 + "1" + ")" * 400],
)
def test_an_expression_is_read_not_run(text):
    with pytest.raises(BadExpression):
        expression(text)


def test_queries_as_people_write_them_still_work():
    s = (e.supply(12) + e.Resistor(10) + e.ground).solve()
    assert s("U_R_1 / I_R_1") == 10
    assert s("sqrt(P_R_1 * R_1)") == 12
    with pytest.raises(BadExpression):
        s(RUN)
