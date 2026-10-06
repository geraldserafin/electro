"""What two windings on one core share: their voltages and currents, each winding its own loop."""


def windings(t):
    return t.across("p1", "p2"), t.across("s1", "s2"), t.I["p1"], t.I["s1"]


def own_loop(t):
    return t.I["p1"] + t.I["p2"]
