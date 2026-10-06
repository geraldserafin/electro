"""The engine every frame runs on: numbers only, no algebra — plain Python, so that the page gets it as
JavaScript printed from this very file (``scripts/engine_js.py``, by pscript). ``Machine`` is a circuit in
time, one function with memory: frame after frame from rest, each step as long as what is remembered
allows, Newton's method on a frame's equations (compiled from its formula: ``code``), a p-n junction
approached along its exponential as SPICE does, a linear system solved by elimination.

A kernel is ``kernel(x, p, F, J)``: it fills ``F`` with the equations' values at the unknowns ``x`` and the
parameters ``p``, ``J`` (zeroed first) with their derivatives, n × n row by row. An update is
``update(x, p, out)``: what is remembered after a step into ``out``.

Written for the printing: no imports but ``math``; printed as JavaScript's own operators, so ``+`` and ``*``
on numbers only, and nothing empty tested as false.
"""

import math

RELTOL = 1e-6
VNTOL = 1e-6
MAX_NEWTON = 60
EXP_LIMIT = 80.0
GUESSES = 64
"""Input combinations whose circuit is remembered as Newton's first guess (the most recent)."""


class NoConvergence(Exception):
    """The circuit's state at ``time`` (seconds) could not be found, even in tiny steps."""

    def __init__(self, time):
        super().__init__("NoConvergence at " + str(time))
        self.time = time


class Machine:
    """A circuit in time. ``program``: ``initial`` (the parameters at rest: dt, t, what is remembered, what
    the world sets), ``states`` (each remembered value's parameter and the most it may move in a step, None:
    it jumps), ``inputs`` (name → parameter), ``junctions`` (unknown, scale, bend) and the unknowns' count
    ``n``. Its memory: the time ``t``, the unknowns ``x``, the parameters ``p``, the next step's length."""

    def __init__(self, program, kernel, update):
        self.kernel = kernel
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
        self.p[i] = value

    def key(self):
        return ",".join([str(self.p[i]) for i in self.places])

    def frame(self, dt):
        """The unknowns ``dt`` after now, or None: Newton did not get there."""
        self.p[0] = dt
        self.p[1] = self.t + dt
        x0 = self.x
        if self.changed:
            x0 = self.guesses.get(self.key(), self.x)
        self.changed = False
        return newton(self.kernel, x0, self.p, self.junctions)

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
        for k in range(len(self.states)):
            i, most = self.states[k]
            if most is None and self.after[k] != self.p[i]:
                self.switched = True
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
                    self.p[pair[0]] = pair[1]
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


def newton(kernel, x0, p, junctions):
    """A root near ``x0``, or None; ``junctions``: each one's unknown, the scale it moves on, where it bends."""
    n = len(x0)
    x = [v for v in x0]
    F = [0.0 for _ in range(n)]
    J = [0.0 for _ in range(n * n)]
    for iteration in range(1, MAX_NEWTON + 1):
        for k in range(n * n):
            J[k] = 0.0
        try:
            kernel(x, p, F, J)
        except OverflowError:
            return None
        for k in range(n):
            F[k] = -F[k]
        if not solve_linear(J, F, n):
            return None
        done = True
        for k in range(n):
            moved = x[k] + F[k]
            if math.isnan(moved):
                return None
            F[k] = moved
        for junction in junctions:
            i = junction[0]
            F[i] = junction_step(F[i], x[i], junction[1], junction[2])
        for k in range(n):
            if abs(F[k] - x[k]) > RELTOL * max(abs(F[k]), abs(x[k])) + VNTOL:
                done = False
        was = x
        x = F
        F = was
        if done and iteration > 1:
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
