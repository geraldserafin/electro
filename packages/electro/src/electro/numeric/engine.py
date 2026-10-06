"""The engine every frame runs on: numbers only, no algebra — plain Python, so that the page gets it as
JavaScript printed from this very file (``scripts/engine_js.py``, by pscript). ``Machine`` is a circuit in
time, one function with memory: frame after frame from rest, each step as long as what is remembered
allows, Newton's method on a frame's equations (compiled from its formula: ``code``), a p-n junction
approached along its exponential as SPICE does.

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


class NoConvergence(Exception):
    """The circuit's state at ``time`` (seconds) could not be found, even in tiny steps."""

    def __init__(self, time):
        super().__init__("NoConvergence at " + str(time))
        self.time = time


class Machine:
    """A circuit in time. ``program``: ``initial`` (the parameters at rest: dt, t, how a change is read —
    θ: 1 back over the step, ½ trapezoids —, what is remembered, what the world sets), ``states`` (each remembered value's parameter and the most it may move in a step, None:
    it jumps), ``inputs`` (name → parameter), ``junctions`` (unknown, scale, bend) and the unknowns' count
    ``n``. Its memory: the time ``t``, the unknowns ``x``, the parameters ``p``, the next step's length."""

    def __init__(self, program, system, update):
        self.system = system
        self.update = update
        self.n = program["n"]
        self.states = program["states"]
        self.junctions = program["junctions"]
        self.inputs = program["inputs"]
        self.places = sorted([self.inputs[k] for k in self.inputs])
        self.x = [0.0 for _ in range(self.n)]
        self.p = [v for v in program["initial"]]
        self.after = [0.0 for _ in self.states]
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

    def advance(self, dt, jump):
        """Try one step of ``dt``: [taken, how much of its allowed move a remembered value used]; ``jump``:
        taken whatever the move, as long as Newton got there."""
        x = self.frame(dt)
        if x is None:
            return [False, math.inf]
        self.update(x, self.p, self.after)
        change = 0.0
        for k in range(len(self.states)):
            i, most = self.states[k]
            if most is not None:
                change = max(change, abs(self.after[k] - self.p[i]) / most)
        if change > 1 and not jump:
            return [False, change]
        self.x = x
        self.t += dt
        self.switched = False
        self.rough = max(0, self.rough - 1)
        for k in range(len(self.states)):
            i, most = self.states[k]
            if most is None and self.after[k] != self.p[i]:
                self.switched = True
                self.rough = ROUGH
            self.p[i] = self.after[k]
        return [True, change]

    def advance_to(self, target, dt_max, schedule=None, on_frame=None):
        """Steps up to ``target``, at most ``dt_max``: shorter while what is remembered moves fast, after
        something jumped, or when Newton did not get there; in the shortest step a value may jump for real (a
        capacitor put across an ideal source)."""
        dt_min = dt_max * 1e-9
        self.step = min(self.step if self.step > 0 else min(dt_max, 1e-6), dt_max)
        while self.t < target - 1e-15:
            h = min(self.step, target - self.t)
            if schedule is not None:
                for pair in schedule(self.t):
                    if self.p[pair[0]] != pair[1]:
                        self.p[pair[0]] = pair[1]
                        self.rough = ROUGH
            taken, change = self.advance(h, h <= dt_min)
            if not taken:
                if h <= dt_min:
                    raise NoConvergence(self.t)
                self.step = h / 4 if change == math.inf else h / 2
                continue
            if on_frame is not None:
                on_frame(self)
            if self.switched:
                self.step = max(dt_min, h / 8)
            elif change < 0.25 and h >= self.step * 0.999:
                self.step = min(dt_max, h * 2)

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


def homotopy(find, n):
    """A root at λ = 1 of what ``find(x0, λ)`` finds near ``x0``, the sources raised from λ = 0, where
    everything is zero. Each raise starts where the last ended; a raise Newton does not finish is halved."""
    x = find([0.0 for _ in range(n)], 0.0)
    lam = 0.0
    raise_by = 0.25
    while x is not None and lam < 1:
        to = min(1.0, lam + raise_by)
        found = find(x, to)
        if found is None:
            raise_by = raise_by / 2
            if raise_by < 1e-6:
                return None
            continue
        x = found
        lam = to
        raise_by = min(1.0, raise_by * 2)
    return x


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
