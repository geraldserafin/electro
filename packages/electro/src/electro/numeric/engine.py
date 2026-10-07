"""The engine every frame runs on: numbers only, plain Python, so the page gets it as JavaScript printed from
this very file (``scripts/engine_js.py``, by pscript).

``Machine`` runs a circuit in time: frame after frame from rest, Newton's method on each frame's equations
(compiled by ``code``), a p-n junction approached along its bend as SPICE does.

A step is as long as its error allows. Trapezoids err by dt³/12 times the third derivative; a step back over
the frame (after a jump) by dt²/2 times the second. Both are read off the remembered values of the last few
frames (divided differences, as SPICE does), never off the slopes: a stiff junction makes those ring while the
values stand still. A step over the tolerance is taken again shorter; the next is as long as keeps under it.

A frame's equations are a ``System``: a sparse Jacobian, eliminated in an order ``sparse`` chose once. Its
entries the unknowns do not change (a resistor's, a capacitor's C/dt) are eliminated first and kept while they
stay the same, so Newton eliminates only what a diode's exponential touches; a linear circuit is one step.

Written for the printing: no imports but ``math``; ``+`` and ``*`` on numbers only; nothing empty tested as
false.
"""

import math

RELTOL = 1e-6
VNTOL = 1e-6
MAX_NEWTON = 60
EXP_LIMIT = 80.0
ROUGH = 2
"""Steps back over the frame (θ = 1) after a jump, before trapezoids again."""
GUESSES = 64
"""Input combinations whose circuit is remembered as Newton's first guess."""
TRTOL, TRABS = 1e-3, 1e-6
"""The error a step may make in what it remembers: this fraction of it, plus this much."""


class NoConvergence(Exception):
    """The circuit's state at ``time`` (seconds) could not be found, even in tiny steps."""

    def __init__(self, time):
        super().__init__("NoConvergence at " + str(time))
        self.time = time


class History:
    """The values of what changes (under ``D``) at the last two frames, and the steps between them, since the
    last jump: what a step's error is read off."""

    def __init__(self, n):
        self.back = [[0.0, 0.0] for _ in range(n)]
        self.steps = [0.0, 0.0]
        self.count = 0

    def forget(self):
        """After a jump: a slope across it is no slope."""
        self.count = 0

    def remember(self, now, dt):
        """The values now, before a step of ``dt``."""
        for k in range(len(now)):
            self.back[k][1] = self.back[k][0]
            self.back[k][0] = now[k]
        self.steps[1] = self.steps[0]
        self.steps[0] = dt
        self.count += 1

    def error(self, now, after, dt, back_over):
        """How far over the tolerance a step of ``dt`` from ``now`` to ``after`` errs (1: at it); 0 when too
        few frames since the last jump tell. ``back_over``: the step went back over the frame (θ = 1)."""
        if self.count < 1:
            return 0.0
        h1, h2 = self.steps[0], self.steps[1]
        worst = 0.0
        for k in range(len(now)):
            x1, x0, xa, xb = after[k], now[k], self.back[k][0], self.back[k][1]
            second = ((x1 - x0) / dt - (x0 - xa) / h1) / (dt + h1)
            if back_over or self.count < 2:
                err = dt * dt * abs(second)
            else:
                third = (second - ((x0 - xa) / h1 - (xa - xb) / h2) / (h1 + h2)) / (dt + h1 + h2)
                err = dt * dt * dt * abs(third) / 2
            worst = max(worst, err / (TRTOL * max(abs(x0), abs(x1)) + TRABS))
        return worst


class Guesses:
    """Newton's first guess when the inputs change: the circuit as it last was with those inputs. A PWM pin or
    a multiplexed display goes back and forth between a few of them; from its own last state a step converges
    in two iterations instead of fifteen."""

    def __init__(self, places):
        self.places = places
        self.seen = {}
        self.changed = False

    def key(self, p):
        return ",".join([str(p[i]) for i in self.places])

    def leave(self, p, x):
        """The inputs are about to change: remember the circuit as it is with them."""
        if self.changed:
            return
        key = self.key(p)
        self.seen.pop(key, None)
        self.seen[key] = [v for v in x]
        if len(list(self.seen.keys())) > GUESSES:
            del self.seen[list(self.seen.keys())[0]]
        self.changed = True

    def start(self, p, x):
        """Where Newton starts: as the circuit was with these inputs, if it was; else ``x``."""
        x0 = self.seen.get(self.key(p), x) if self.changed else x
        self.changed = False
        return x0


class Machine:
    """A circuit in time. ``program``: ``initial`` (the parameters at rest: dt, t, θ, what is remembered, the
    inputs), ``states`` (each remembered value's parameter, in the order ``update`` gives them), ``changing``
    (places in ``states`` of what moves under ``D``), ``jumps`` (places of what jumps: a flip-flop's state, a
    switch in time), ``longest`` (the longest step, or None), ``inputs`` (name → parameter), ``junctions``
    (unknown, scale, bend) and ``n``, the unknowns' count. Its memory: the time ``t``, the unknowns ``x``, the
    parameters ``p`` and the next step's length."""

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
        self.x = [0.0 for _ in range(self.n)]
        self.p = [v for v in program["initial"]]
        self.after = [0.0 for _ in self.states]
        self.t = 0.0
        self.step = 0.0
        self.switched = False
        self.history = History(len(self.changing))
        self.guesses = Guesses(sorted([self.inputs[k] for k in self.inputs]))
        self.jump()

    def jump(self):
        """Something jumped (the start, a switch, an input): two steps back over the frame — trapezoids ring
        across a jump — and the error read afresh."""
        self.rough = ROUGH
        self.history.forget()

    def set(self, name, value):
        """Set an input, by name, from now on."""
        self.put(self.inputs[name], value)

    def put(self, i, value):
        if self.p[i] == value:
            return
        self.guesses.leave(self.p, self.x)
        self.jump()
        self.p[i] = value

    def frame(self, dt):
        """The unknowns ``dt`` after now, or None when Newton does not get there."""
        self.p[0] = dt
        self.p[1] = self.t + dt
        self.p[2] = 1.0 if self.rough > 0 else 0.5
        return newton(self.system, self.guesses.start(self.p, self.x), self.p, self.junctions)

    def advance(self, dt, last):
        """Try a step of ``dt``: [taken, its error against the tolerance]. ``last``: the shortest step, taken
        whatever its error as long as Newton got there."""
        x = self.frame(dt)
        if x is None:
            return [False, math.inf]
        self.update(x, self.p, self.after)
        err = self.history.error(
            self.remembered(self.p, self.states), self.remembered(self.after, None), dt, self.p[2] == 1.0
        )
        if err > 1 and not last:
            return [False, err]
        self.accept(x, dt)
        return [True, err]

    def remembered(self, values, places):
        """What moves under ``D``: from the parameters (``places``: where each is) or from ``after``."""
        if places is None:
            return [values[k] for k in self.changing]
        return [values[places[k]] for k in self.changing]

    def accept(self, x, dt):
        """The step taken: now is ``dt`` later, at ``x``, what is remembered as it is after it."""
        self.history.remember(self.remembered(self.p, self.states), dt)
        self.x = x
        self.t += dt
        self.rough = max(0, self.rough - 1)
        self.switched = False
        for k in self.jumps:
            if self.after[k] != self.p[self.states[k]]:
                self.switched = True
        if self.switched:
            self.jump()
        for k in range(len(self.states)):
            self.p[self.states[k]] = self.after[k]

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
                        machine.jump()
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
