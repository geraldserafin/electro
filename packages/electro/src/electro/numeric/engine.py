"""The engine every frame runs on: numbers only, no algebra — plain Python, so that the page gets it as
JavaScript printed from this very file (``scripts/engine_js.py``, by pscript). ``Machine`` is a circuit in
time, one function with memory: frame after frame from rest, Newton's method on a frame's equations
(compiled from its formula: ``code``), a p-n junction approached along its exponential as SPICE does.

How long a step is follows from one rule: the error it makes. A change is read by trapezoids, whose error
over a step is dt³/12 times the third derivative; after a jump, back over the step, dt²/2 times the second.
Both are read off what is remembered at the last few frames (divided differences, as SPICE does) — never off
the slopes, which a stiff junction makes ring, step after step, while what it remembers stands still. A step
whose error is over the tolerance is taken again shorter; the next is as long as keeps it under.

A frame's equations are a ``System``: their Jacobian sparse, eliminated in an order ``code`` chose once
(``sparse``). Its entries that the unknowns do not change (a resistor's, a capacitor's C/dt) are worked out
once a frame and eliminated first, and that is kept while they stay the same: Newton then eliminates only
what the unknowns move (what a diode's exponential touches); a circuit with none is solved in one go. An
update is ``update(x, p, out)``: what is remembered after a step into ``out``.

Written for the printing: no imports but ``math``; printed as JavaScript's own operators, so ``+`` and ``*``
on numbers only, and nothing empty tested as false.
"""

import math

RELTOL = 1e-6
VNTOL = 1e-6
MAX_NEWTON = 60
EXP_LIMIT = 80.0
ROUGH = 2
"""Steps back over the step (θ = 1) after a jump, before trapezoids."""
GUESSES = 64
"""Input combinations whose circuit is remembered as Newton's first guess (the most recent)."""
TRTOL, TRABS = 1e-3, 1e-6
"""The error a step may make in what it remembers: this part of it, and this much more."""


class NoConvergence(Exception):
    """The circuit's state at ``time`` (seconds) could not be found, even in tiny steps."""

    def __init__(self, time):
        super().__init__("NoConvergence at " + str(time))
        self.time = time


class Machine:
    """A circuit in time. ``program``: ``initial`` (the parameters at rest: dt, t, how a change is read —
    θ: 1 back over the step, ½ trapezoids —, what is remembered, what the world sets), ``states`` (each
    remembered value's parameter, in the order ``update`` gives them), ``changing`` (the places in ``states``
    of what changes, under ``D``: what a step's error is read from), ``jumps`` (those that jump: a
    flip-flop's state, a switch in time), ``longest`` (the longest a step may be, or None), ``inputs`` (name → parameter), ``junctions`` (unknown, scale,
    bend) and the unknowns' count ``n``. Its memory: the time ``t``, the unknowns ``x``, the parameters
    ``p``, the next step's length."""

    def __init__(self, program, system, update):
        self.system = system
        self.update = update
        self.n = program["n"]
        self.states = program["states"]
        self.changing = program["changing"]
        self.jumps = program["jumps"]
        self.longest = program["longest"]
        self.junctions = program["junctions"]
        self.inputs = program["inputs"]
        self.places = sorted([self.inputs[k] for k in self.inputs])
        self.x = [0.0 for _ in range(self.n)]
        self.p = [v for v in program["initial"]]
        self.after = [0.0 for _ in self.states]
        # what changes at the frames before this one, and how long the steps between them were: since the last
        # jump only (a slope is no slope across one)
        self.back = [[0.0, 0.0] for _ in self.changing]
        self.steps = [0.0, 0.0]
        self.known = 0
        self.t = 0.0
        self.step = 0.0
        self.switched = False
        # the two steps after a jump (the start, something switched, the world set something) go back over the
        # step (θ = 1): trapezoids across a jump ring, every slope after it flipping sign, and the first step's
        # slope is the jump's; the second's is how things then move. The rest by trapezoids
        self.rough = ROUGH
        # Newton's first guess when the inputs change: the circuit as it last was with those inputs. A PWM pin,
        # a multiplexed display go back and forth between a few of them; from its own last state a step
        # converges in two iterations instead of fifteen (a LED turning on, walked up its exponential)
        self.guesses = {}
        self.changed = False

    def set(self, name, value):
        """What the world sets, by name, from now on."""
        self.put(self.inputs[name], value)

    def put(self, i, value):
        if self.p[i] == value:
            return
        if not self.changed:
            key = self.key()
            self.guesses.pop(key, None)
            self.guesses[key] = [v for v in self.x]
            if len(list(self.guesses.keys())) > GUESSES:
                del self.guesses[list(self.guesses.keys())[0]]
            self.changed = True
        self.rough = ROUGH
        self.p[i] = value

    def key(self):
        return ",".join([str(self.p[i]) for i in self.places])

    def frame(self, dt):
        """The unknowns ``dt`` after now, or None: Newton did not get there."""
        self.p[0] = dt
        self.p[1] = self.t + dt
        self.p[2] = 1.0 if self.rough > 0 else 0.5
        x0 = self.x
        if self.changed:
            x0 = self.guesses.get(self.key(), self.x)
        self.changed = False
        return newton(self.system, x0, self.p, self.junctions)

    def error(self, dt):
        """How far over the tolerance the step's error is (1: at it); 0 when too few frames since the last
        jump tell."""
        if self.rough == ROUGH:
            self.known = 0
        if self.known < 1:
            return 0.0
        h1, h2 = self.steps[0], self.steps[1]
        worst = 0.0
        for k in range(len(self.changing)):
            v = self.changing[k]
            x1, x0, xa, xb = self.after[v], self.p[self.states[v]], self.back[k][0], self.back[k][1]
            d1 = (x1 - x0) / dt
            second = (d1 - (x0 - xa) / h1) / (dt + h1)
            if self.p[2] == 1.0 or self.known < 2:
                err = dt * dt * abs(second)
            else:
                third = (second - ((x0 - xa) / h1 - (xa - xb) / h2) / (h1 + h2)) / (dt + h1 + h2)
                err = dt * dt * dt * abs(third) / 2
            worst = max(worst, err / (TRTOL * max(abs(x0), abs(x1)) + TRABS))
        return worst

    def advance(self, dt, jump):
        """Try one step of ``dt``: [taken, its error against the tolerance]; ``jump``: taken whatever the
        error, as long as Newton got there."""
        x = self.frame(dt)
        if x is None:
            return [False, math.inf]
        self.update(x, self.p, self.after)
        err = self.error(dt)
        if err > 1 and not jump:
            return [False, err]
        for k in range(len(self.changing)):
            self.back[k][1] = self.back[k][0]
            self.back[k][0] = self.p[self.states[self.changing[k]]]
        self.steps[1] = self.steps[0]
        self.steps[0] = dt
        self.known += 1
        self.x = x
        self.t += dt
        self.switched = False
        self.rough = max(0, self.rough - 1)
        for k in self.jumps:
            if self.after[k] != self.p[self.states[k]]:
                self.switched = True
                self.rough = ROUGH
        for k in range(len(self.states)):
            self.p[self.states[k]] = self.after[k]
        return [True, err]

    def advance_to(self, target, dt_max, schedule=None, on_frame=None):
        """Steps up to ``target`` (``walk``), at most ``dt_max``; shorter after something jumped; in the shortest
        step a value may jump for real (a capacitor put across an ideal source)."""
        if self.longest is not None:
            dt_max = min(dt_max, self.longest)
        machine = self

        def attempt(t, h, last):
            if schedule is not None:
                for pair in schedule(t):
                    if machine.p[pair[0]] != pair[1]:
                        machine.p[pair[0]] = pair[1]
                        machine.rough = ROUGH
            done = machine.advance(h, last)
            if not done[0]:
                return [done[1], dt_max]
            if on_frame is not None:
                on_frame(machine)
            return [min(done[1], 1.0), max(dt_max * 1e-9, h / 8) if machine.switched else dt_max]

        h = walk(self.t, target, self.step if self.step > 0 else min(dt_max, 1e-6), dt_max, attempt)
        if h is None:
            raise NoConvergence(self.t)
        self.step = h

    def run(self, until, dt_max, schedule=None, on_frame=None):
        """From rest to ``until``; ``on_frame`` gets every frame, at t = 0 too, after a first tiny step (the
        circuit the instant it starts)."""
        if schedule is not None:
            for pair in schedule(0.0):
                self.p[pair[0]] = pair[1]
        self.advance_to(min(1e-9, until), dt_max, schedule)
        self.t = 0.0
        if on_frame is not None:
            on_frame(self)
        self.advance_to(until, dt_max, schedule, on_frame)


class System:
    """Equations F(x) = 0 over ``n`` unknowns and their Jacobian, sparse. ``jconst(p, A)`` fills the
    entries the unknowns do not change, ``jdyn(x, p, F, A)`` the residuals and the rest; ``shape`` (from
    ``sparse.shape``) says where each entry is and how to eliminate them: the pivots in order, the first
    ``k1`` of them on entries that never change."""

    def __init__(self, shape, jconst, jdyn):
        self.jconst = jconst
        self.jdyn = jdyn
        self.n = shape["n"]
        self.m = shape["m"]
        self.rows = shape["rows"]
        self.cols = shape["cols"]
        self.constant = shape["constant"]
        self.linear = shape["linear"]
        self.pivots = shape["pivots"]
        self.prow = shape["prow"]
        self.pcol = shape["pcol"]
        self.k1 = shape["k1"]
        self.low = shape["low"]
        self.low_row = shape["low_row"]
        self.low_at = shape["low_at"]
        self.upd = shape["upd"]
        self.upd_at = shape["upd_at"]
        self.up = shape["up"]
        self.up_col = shape["up_col"]
        self.up_at = shape["up_at"]
        self.head = shape["head"]
        self.trail = shape["trail"]
        self.A = [0.0 for _ in range(self.m)]
        self.W = [0.0 for _ in range(self.m)]
        self.D = [0.0 for _ in range(self.m)]
        self.kept = [0.0 for _ in self.constant]
        self.fresh = False
        self.F = [0.0 for _ in range(self.n)]
        self.dx = [0.0 for _ in range(self.n)]
        self.dense = [0.0 for _ in range(self.n * self.n)]

    def begin(self, p):
        """A frame's parameters in: its unchanging entries; what was eliminated of them kept while they are
        the same."""
        self.jconst(p, self.A)
        for k in range(len(self.constant)):
            v = self.A[self.constant[k]]
            if v != self.kept[k]:
                self.kept[k] = v
                self.fresh = False

    def step(self, x, p):
        """Newton's step from ``x`` into ``dx``; False: no step (the Jacobian singular)."""
        self.jdyn(x, p, self.F, self.A)
        for i in range(self.n):
            self.F[i] = -self.F[i]
        if self.factor():
            self.solve()
            return True
        self.fresh = False
        return self.solve_dense()

    def factor(self):
        A, W, D = self.A, self.W, self.D
        if not self.fresh:
            for pos in self.head:
                W[pos] = A[pos]
            for pos in self.trail:
                D[pos] = 0.0
            for k in range(self.k1):
                if not self.pivot(k, True):
                    return False
            self.fresh = True
        for pos in self.trail:
            W[pos] = A[pos] + D[pos]
        for k in range(self.k1, self.n):
            if not self.pivot(k, False):
                return False
        return True

    def pivot(self, k, first):
        """The ``k``-th pivot's column eliminated below it; in the first part, what falls on entries that
        change kept apart (``D``), to be added to them anew."""
        W = self.W
        at = self.pivots[k]
        top = abs(W[at])
        big = top
        for q in range(self.low_at[k], self.low_at[k + 1]):
            big = max(big, abs(W[self.low[q]]))
        if top == 0 or top < 1e-13 * big:
            return False
        inv = 1.0 / W[at]
        for q in range(self.low_at[k], self.low_at[k + 1]):
            W[self.low[q]] *= inv
        upd = self.upd
        for q in range(self.upd_at[k], self.upd_at[k + 1], 4):
            if first and upd[q + 3] == 1:
                self.D[upd[q]] -= W[upd[q + 1]] * W[upd[q + 2]]
            else:
                W[upd[q]] -= W[upd[q + 1]] * W[upd[q + 2]]
        return True

    def solve(self):
        W, b, x = self.W, self.F, self.dx
        for k in range(self.n):
            v = b[self.prow[k]]
            for q in range(self.low_at[k], self.low_at[k + 1]):
                b[self.low_row[q]] -= W[self.low[q]] * v
        for k in range(self.n - 1, -1, -1):
            s = b[self.prow[k]]
            for q in range(self.up_at[k], self.up_at[k + 1]):
                s -= W[self.up[q]] * x[self.up_col[q]]
            x[self.pcol[k]] = s / W[self.pivots[k]]

    def solve_dense(self):
        """When a pivot the order chose is nothing here (a switch open): elimination with partial pivoting."""
        n, J = self.n, self.dense
        for k in range(n * n):
            J[k] = 0.0
        for q in range(len(self.rows)):
            J[self.rows[q] * n + self.cols[q]] += self.A[q]
        if not solve_linear(J, self.F, n):
            return False
        for i in range(n):
            self.dx[i] = self.F[i]
        return True


def newton(system, x0, p, junctions):
    """A root near ``x0``, or None; ``junctions``: each one's unknown, the scale it moves on, where it bends.
    A linear system in one step."""
    n = len(x0)
    x = [v for v in x0]
    system.begin(p)
    for iteration in range(1, MAX_NEWTON + 1):
        try:
            if not system.step(x, p):
                return None
        except OverflowError:
            return None
        dx = system.dx
        done = True
        for k in range(n):
            moved = x[k] + dx[k]
            if math.isnan(moved):
                return None
            dx[k] = moved
        for junction in junctions:
            i = junction[0]
            dx[i] = junction_step(dx[i], x[i], junction[1], junction[2])
        for k in range(n):
            if abs(dx[k] - x[k]) > RELTOL * max(abs(dx[k]), abs(x[k])) + VNTOL:
                done = False
            x[k] = dx[k]
        if system.linear or (done and iteration > 1):
            return x
    return None


def walk(at, to, h, longest, attempt):
    """Continuation: from ``at`` to ``to`` — in time, or raising the sources — each step from where the last
    ended. ``attempt(at, h, last)`` takes a step: its error against what it may be (1: at it; inf: Newton did
    not get there), and the longest the next may be. A step over is taken again shorter; the next is as long
    as keeps the error under. ``last``: the shortest a step may be, taken whatever its error. The next step's
    length; None: not even the shortest got there."""
    shortest = longest * 1e-9
    h = min(h, longest)
    while at < to - 1e-15:
        step = min(h, to - at)
        done = attempt(at, step, step <= shortest)
        err = done[0]
        if err > 1:
            if step <= shortest:
                return None
            h = step / 4 if err == math.inf else step * max(0.1, 0.9 * math.exp(-math.log(err) / 3))
            continue
        at += step
        if step >= h * 0.999:
            h = step * (2.0 if err < 0.1 else min(2.0, 0.9 * math.exp(-math.log(err) / 3)))
        h = min(h, done[1], longest)
    return h


def homotopy(find, n):
    """A root at λ = 1 of what ``find(x0, λ)`` finds near ``x0``, walked from λ = 0, where everything is
    zero."""
    x = [find([0.0 for _ in range(n)], 0.0)]

    def attempt(lam, h, last):
        found = find(x[0], lam + h)
        if found is None:
            return [math.inf, 1.0]
        x[0] = found
        return [0.0, 1.0]

    if x[0] is None or walk(0.0, 1.0, 0.25, 1.0, attempt) is None:
        return None
    return x[0]


def junction_step(to, old, nvt, vcrit):
    """SPICE's: along the exponential, never far past its bend in one go."""
    if to > vcrit and abs(to - old) > 2 * nvt:
        if old > 0:
            arg = 1 + (to - old) / nvt
            return old + nvt * math.log(arg) if arg > 0 else vcrit
        return nvt * math.log(to / nvt)
    return to


def solve_linear(A, b, n):
    """``A·x = b`` in place, ``x`` into ``b`` (``A`` flat, row by row), by elimination with partial pivoting,
    each row scaled to its largest entry first, so laws in volts and in amperes pivot alike. False: singular."""
    for i in range(n):
        big = 0.0
        for j in range(n):
            big = max(big, abs(A[i * n + j]))
        if big == 0:
            big = 1.0
        for j in range(n):
            A[i * n + j] /= big
        b[i] /= big
    for col in range(n):
        pivot = col
        for r in range(col + 1, n):
            if abs(A[r * n + col]) > abs(A[pivot * n + col]):
                pivot = r
        if abs(A[pivot * n + col]) < 1e-300:
            return False
        if pivot != col:
            for j in range(col, n):
                t = A[col * n + j]
                A[col * n + j] = A[pivot * n + j]
                A[pivot * n + j] = t
            t = b[col]
            b[col] = b[pivot]
            b[pivot] = t
        inv = 1.0 / A[col * n + col]
        for r in range(col + 1, n):
            f = A[r * n + col] * inv
            if f != 0:
                for j in range(col, n):
                    A[r * n + j] -= f * A[col * n + j]
                b[r] -= f * b[col]
    for i in range(n - 1, -1, -1):
        s = b[i]
        for j in range(i + 1, n):
            s -= A[i * n + j] * b[j]
        b[i] = s / A[i * n + i]
    return True


def limited_exp(x):
    """``exp``, continued along its tangent beyond ``EXP_LIMIT``: Newton's first guesses never overflow."""
    return math.exp(x) if x <= EXP_LIMIT else math.exp(EXP_LIMIT) * (1 + x - EXP_LIMIT)


def limited_exp_slope(x):
    return math.exp(min(x, EXP_LIMIT))
