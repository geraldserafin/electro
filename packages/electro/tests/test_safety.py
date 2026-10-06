"""Text from a drawing, a query or a netlist never runs as code: labels, point names and expressions come
from notes other people send (a link, a course), so nothing in them may reach eval or exec."""

import pytest
import sympy as sp
from electro import GND, BadName, I, Node, Resistor, VoltageSource

RUN = "__import__('os').system('echo pwned')"
BAD = [f"a+{RUN}", f"x)+{RUN}+(1", "R 1", "R'", "1R", "\\href{javascript:alert(1)}{x}"]


@pytest.mark.parametrize("name", BAD)
def test_a_name_that_is_not_a_name_is_refused(name):
    with pytest.raises(BadName):
        Resistor(name)
    if not name[0].isdigit():
        with pytest.raises(BadName):
            Node(name)


def test_names_as_people_write_them_still_work():
    e, r1, r2, out = (VoltageSource("V_zas"), Resistor("R1"), Resistor("R_2"), Node("wyjście"))
    assert (GND >> e >> r1 >> out >> r2 >> GND).final({e: 12, r1: 10, r2: 20})(I(r1)) == sp.Rational(2, 5)
