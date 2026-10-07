"""Values as text: stored exactly (``to_text``, the inverse of ``electro.values.parse``) and shown in
engineering notation (``fmt``)."""

from __future__ import annotations

import cmath
from decimal import Decimal
from typing import cast

import sympy as sp
from electro.values import UNKNOWN, parse


def to_text(value) -> str | None:
    """The inverse of ``parse``, for storing (JSON): exact, and readable where it can be."""
    if value is None or value is UNKNOWN:
        return None
    value = parse(value) if isinstance(value, str) else sp.sympify(value, strict=True)
    if isinstance(value, sp.Symbol):
        return value.name
    if isinstance(value, sp.Rational) and not isinstance(value, sp.Integer):
        return _decimal(value) if _terminates(value) else f"{value.p}/{value.q}"
    return str(value)


def _terminates(value: sp.Rational) -> bool:
    """Whether its decimal ends (0.5, 0.0047): its denominator has no factors but 2 and 5."""
    q = value.q
    for f in (2, 5):
        while q % f == 0:
            q //= f
    return q == 1


def _decimal(value: sp.Rational) -> str:
    """A decimal; below a thousandth, with its prefix (100n, 4.7µ)."""
    small = [(f, p) for f, p in _ENG if f < sp.Rational(1, 1000)]
    factor, prefix = (
        next(((f, p) for f, p in small if abs(value) >= f), (1, "")) if abs(value) < sp.Rational(1, 1000) else (1, "")
    )
    ratio = cast(sp.Rational, value / factor)
    return f"{(Decimal(int(ratio.p)) / Decimal(int(ratio.q))).normalize():f}{prefix}"


_ENG = [
    (10**9, "G"),
    (10**6, "M"),
    (10**3, "k"),
    (1, ""),
    (sp.Rational(1, 10**3), "m"),
    (sp.Rational(1, 10**6), "µ"),
    (sp.Rational(1, 10**9), "n"),
    (sp.Rational(1, 10**12), "p"),
]


def _eng_real(x: float, unit: str) -> str:
    if x == 0:
        return f"0 {unit}".strip()
    scale, prefix = next(((s, p) for s, p in _ENG if abs(x) >= float(s) * 0.9995), _ENG[-1])
    mantissa = x / float(scale)
    text = f"{mantissa:.4g}"
    return f"{text} {prefix}{unit}".strip()


def fmt(value, unit: str = "") -> str:
    """Human-friendly engineering notation: 0.5 -> '500 mA', 4700 -> '4.7 kΩ'."""
    if value is None:
        return "—"
    value = sp.nsimplify(value) if isinstance(value, (int, float)) else sp.sympify(value, strict=True)
    if value.free_symbols:
        text = sp.sstr(sp.simplify(value))
        return f"{text} {unit}".strip() if unit else text
    value = complex(value)
    if abs(value.imag) < 1e-12 * max(1.0, abs(value.real)):
        return _eng_real(value.real, unit)
    magnitude, phase = cmath.polar(value)
    return f"{_eng_real(magnitude, unit)} ∠ {phase * 180 / cmath.pi:.4g}°"
