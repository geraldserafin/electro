"""In time: the library's simulation tests (test_sim.py), each again on the core, with the same numbers."""

import json
import math

import pytest
import sympy as sp
from electro import (
    AND,
    BJT_PARTS,
    DIODE_PARTS,
    DS1307,
    GND,
    ILI9341,
    LCD1602,
    LCD1602I2C,
    LED,
    LED_COLORS,
    NMOS,
    NPN,
    OPAMP_PARTS,
    PMOS,
    RGBLED,
    SSD1306,
    Arduino,
    Button,
    Buzzer,
    Capacitor,
    Counter,
    DFlipFlop,
    Diode,
    I,
    Inductor,
    JKFlipFlop,
    Node,
    NoSuchInput,
    NotSimulated,
    OpAmpModel,
    P,
    PassiveBuzzer,
    Photoresistor,
    Pico,
    Potentiometer,
    Problem,
    Resistor,
    Servo,
    SevenSegment,
    SineSource,
    SquareSource,
    Switch,
    Thermistor,
    Timer555,
    U,
    Ultrasonic,
    Undetermined,
    V,
    ValueNeeded,
    VoltageSource,
    Zener,
    at,
    beside,
    compile_program,
    simulate,
    solve,
)


def net(*items):
    """Elements between points named as in a netlist (``"GND"`` is ground), and those points by name."""
    points: dict[str, object] = {"GND": GND}
    for _, *names in items:
        for n in names:
            points.setdefault(n, Node(n))
    return beside(*(at(e, *(points[n] for n in names)) for e, *names in items)), points


def test_rc_charges_like_the_exponential():
    e, r, c = VoltageSource(), Resistor(), Capacitor()
    circuit, n = net((e, "GND", "A"), (r, "A", "B"), (c, "B", "GND"))
    trace = simulate(Problem(circuit, {e: 5, r: 1000, c: "1m"}), until=5)
    for t in (0.5, 1, 2, 5):
        assert trace.at(V(n["B"]), t) == pytest.approx(5 * (1 - math.exp(-t)), abs=0.05)


def test_rl_current_rises_like_the_exponential():
    e, r, coil = VoltageSource(), Resistor(), Inductor()
    circuit, _ = net((e, "GND", "A"), (r, "A", "B"), (coil, "B", "GND"))
    trace = simulate(Problem(circuit, {e: 10, r: 10, coil: 1}), until=0.5)
    assert trace.at(I(coil), 0.1) == pytest.approx(1 - math.exp(-1), abs=0.02)
    assert trace.at(I(coil), 0.5) == pytest.approx(1, abs=0.02)


def _led_circuit(color=None):
    e, r, d = VoltageSource(), Resistor(), LED()
    circuit, _ = net((e, "GND", "A"), (r, "A", "B"), (d, "B", "GND"))
    given = {e: 5, r: 150} | ({d: LED_COLORS[color]} if color else {})
    return Problem(circuit, given), d


def test_led_with_its_resistor():
    red, d = _led_circuit()
    trace = simulate(red, until=1e-3)
    assert trace.at(U(d), 1e-3) == pytest.approx(2.0, abs=0.02)
    assert trace.at(I(d), 1e-3) == pytest.approx(0.02, abs=5e-4)
    blue, d = _led_circuit("blue")
    assert simulate(blue, until=1e-3).at(U(d), 1e-3) > 3


def test_on_paper_a_led_is_where_it_settles():
    red, d = _led_circuit()
    assert float(solve(red)(I(d))) == pytest.approx(0.02, abs=5e-4)


def test_555_astable_blinks_at_the_textbook_period():
    e, timer, r1, r2, c, r3, led = VoltageSource(), Timer555(), Resistor(), Resistor(), Capacitor(), Resistor(), LED()
    circuit, n = net(
        (e, "GND", "vcc"),
        (timer, "GND", "tc", "out", "vcc", "ctrl", "tc", "dis", "vcc"),
        (r1, "vcc", "dis"),
        (r2, "dis", "tc"),
        (c, "tc", "GND"),
        (r3, "out", "a"),
        (led, "a", "GND"),
    )
    given = {e: 9, r1: 1000, r2: 10000, c: "100u", r3: 330, led: LED_COLORS["green"]}
    trace = simulate(Problem(circuit, given), until=5)
    out = trace(V(n["out"]))
    rising = [trace.t[i] for i in range(1, len(out)) if out[i - 1] < 4 <= out[i]]
    assert rising[2] - rising[1] == pytest.approx(0.693 * (1000 + 2 * 10000) * 100e-6, rel=0.05)
    settled = trace(V(n["tc"]))[len(out) // 2 :]
    assert min(settled) == pytest.approx(3, abs=0.1) and max(settled) == pytest.approx(6, abs=0.1)


def test_two_transistor_multivibrator_takes_turns():
    e = VoltageSource()
    r = [Resistor() for _ in range(4)]
    led1, led2, c1, c2, q1, q2 = LED(), LED(), Capacitor(), Capacitor(), NPN(), NPN()
    circuit, _ = net(
        (e, "GND", "vcc"),
        (r[0], "vcc", "a1"),
        (led1, "a1", "c1"),
        (r[1], "vcc", "a2"),
        (led2, "a2", "c2"),
        (r[2], "vcc", "b2"),
        (r[3], "vcc", "b1"),
        (c1, "c1", "b2"),
        (c2, "c2", "b1"),
        (q1, "b1", "c1", "GND"),
        (q2, "b2", "c2", "GND"),
    )
    given = {e: 9, r[0]: 470, r[1]: 470, r[2]: 47000, r[3]: 47000, c1: "47u", c2: "33u", led2: 2.2}
    trace = simulate(Problem(circuit, given), until=3.5)
    lit = [(trace.at(I(led1), t) > 0.005, trace.at(I(led2), t) > 0.005) for t in (1.25, 1.75, 2.25, 2.75, 3.25)]
    assert sum(a != b for a, b in lit) >= 4
    assert {(True, False), (False, True)} <= set(lit)


def test_arduino_pins_a_button_and_a_potentiometer():
    board, r, led, button, pot = Arduino(), Resistor(), LED(), Button(), Potentiometer()
    pins = [f"d{i}" for i in range(14)] + [f"a{i}" for i in range(6)]
    circuit, n = net(
        (board, *pins, "5V", "GND"), (r, "d13", "x"), (led, "x", "GND"), (button, "d2", "GND"), (pot, "5V", "GND", "a0")
    )
    problem = Problem(circuit, {r: 220, pot: 10000})
    trace = simulate(
        problem,
        until=2,
        dt=0.01,
        inputs={
            (board, "D13"): lambda t: "high" if t % 1 < 0.5 else "low",
            (board, "D2"): "pullup",
            button: lambda t: t > 1.5,
            pot: 0.25,
        },
    )
    assert trace.at(I(led), 0.2) == pytest.approx(0.0124, abs=5e-4)
    assert trace.at(I(led), 0.7) == pytest.approx(0, abs=1e-6)
    assert trace.at(V(n["d2"]), 1.2) == pytest.approx(5, abs=0.01)
    assert trace.at(V(n["d2"]), 1.7) == pytest.approx(0, abs=0.01)
    assert trace.at(V(n["a0"]), 1) == pytest.approx(3.75, abs=0.01)
    with pytest.raises(NoSuchInput):
        simulate(problem, until=0.1, inputs={"S_9": 1})


def test_on_paper_a_switch_is_a_datum_and_a_simulation_needs_every_value():
    e, r1, s, r2 = VoltageSource(), Resistor(), Switch(), Resistor()
    circuit, _ = net((e, "GND", "a"), (r1, "a", "b"), (s, "b", "c"), (r2, "c", "GND"))
    assert solve(Problem(circuit, {e: 5, r1: 100, r2: 100, s: {"closed": 1}}))(I(r1)) == sp.Rational(1, 40)
    assert solve(Problem(circuit, {e: 5, r1: 100, r2: 100}))(I(r1)) == 0
    with pytest.raises(ValueNeeded):
        compile_program(Problem(circuit, {e: 5, r1: 100}))


def test_the_program_in_javascript_is_the_same_program():
    red, _ = _led_circuit()
    data = json.loads(compile_program(red).to_json())
    assert "limexp(" in data["kernel"] and "F[" in data["kernel"] and "J[" in data["kernel"]
    assert data["junctions"] and data["kinds"] == {"E_1": "voltage_source", "R_1": "resistor", "LED_1": "led"}
    assert set(data["parts"]["LED_1"]) == {"U", "I"}


def _sine_rc(f):
    e, r, c = SineSource(), Resistor(), Capacitor()
    circuit, n = net((e, "GND", "in"), (r, "in", "out"), (c, "out", "GND"))
    return Problem(circuit, {e: {"": 10, "f": f}, r: 1000, c: "1u"}), n


def test_sine_source_through_an_rc_low_pass():
    f = 1 / (2 * math.pi * 1000 * 1e-6)
    problem, n = _sine_rc(f)
    trace = simulate(problem, until=10 / f)
    late = [k for k, t in enumerate(trace.t) if t > 5 / f]
    assert max(trace(V(n["out"]))[k] for k in late) == pytest.approx(10 / math.sqrt(2), rel=0.03)
    assert max(trace(V(n["in"]))[k] for k in late) == pytest.approx(10, rel=0.01)


def test_square_source_has_its_frequency_and_duty():
    e, r = SquareSource(), Resistor()
    circuit, n = net((e, "GND", "a"), (r, "a", "GND"))
    trace = simulate(Problem(circuit, {e: {"": 5, "f": 1000, "duty": "0.25"}, r: 100}), until=0.01)
    v = trace(V(n["a"]))
    rising = [trace.t[i] for i in range(1, len(v)) if v[i - 1] < 2.5 <= v[i]]
    assert rising[3] - rising[2] == pytest.approx(1e-3, rel=0.02)
    high = sum(t1 - t0 for t0, t1, u in zip(trace.t, trace.t[1:], v[1:]) if u > 2.5)
    assert high / trace.t[-1] == pytest.approx(0.25, abs=0.02)


def test_a_sine_on_paper_is_its_phasor_and_a_square_needs_time():
    e, r = SineSource(), Resistor()
    circuit, n = net((e, "GND", "a"), (r, "a", "GND"))
    assert solve(Problem(circuit, {e: {"": 10, "f": 50}, r: 5}))(I(r)) == 2
    shifted = Problem(circuit, {e: {"": 10, "f": 50, "phase": 90}, r: 5})
    assert complex(solve(shifted)(I(r))) == pytest.approx(2j)
    assert max(simulate(shifted, until=0.001)(V(n["a"]))[:3]) == pytest.approx(10, rel=0.01)
    square, r = SquareSource(), Resistor()
    circuit, _ = net((square, "GND", "a"), (r, "a", "GND"))
    with pytest.raises(Undetermined, match="time"):
        solve(Problem(circuit, {square: 5, r: 5}))


def test_zener_holds_its_voltage_whatever_the_load():
    for load in (10**6, 1000):
        e, r, z, rl = VoltageSource(), Resistor(), Zener(), Resistor()
        circuit, n = net((e, "GND", "in"), (r, "in", "out"), (z, "GND", "out"), (rl, "out", "GND"))
        trace = simulate(Problem(circuit, {e: 12, r: 470, z: "5.1", rl: load}), until=1e-3)
        assert trace.at(V(n["out"]), 1e-3) == pytest.approx(5.1, abs=0.1)


def test_zener_forward_is_a_diode():
    e, r, z = VoltageSource(), Resistor(), Zener()
    circuit, _ = net((e, "GND", "a"), (r, "a", "b"), (z, "b", "GND"))
    assert 0.55 < simulate(Problem(circuit, {e: 5, r: 1000, z: "5.1"}), until=1e-3).at(U(z), 1e-3) < 0.75


def test_zener_clips_a_sine_between_its_forward_drop_and_breakdown():
    e, r, z = SineSource(), Resistor(), Zener()
    circuit, n = net((e, "GND", "in"), (r, "in", "out"), (z, "GND", "out"))
    out = simulate(Problem(circuit, {e: {"": 10, "f": 50}, r: 1000, z: "5.1"}), until=0.04)(V(n["out"]))
    assert max(out) == pytest.approx(5.1, abs=0.15)
    assert min(out) == pytest.approx(-0.7, abs=0.1)


def _low_side(gate):
    e, r, eg, rg, q = VoltageSource(), Resistor(), VoltageSource(), Resistor(), NMOS()
    circuit, n = net((e, "GND", "vcc"), (r, "vcc", "d"), (eg, "GND", "in"), (rg, "in", "g"), (q, "g", "d", "GND"))
    return Problem(circuit, {e: 12, r: 10, eg: gate, rg: 100}), q


def test_nmos_as_a_low_side_switch():
    on, q = _low_side(5)
    end = simulate(on, until=1e-4)
    rds = 1 / (0.5 * (5 - 2))
    assert end.at(I(q, "d"), 1e-4) == pytest.approx(12 / (10 + rds), rel=0.05)
    assert end.at(I(q, "g"), 1e-4) == pytest.approx(0, abs=1e-6)
    off, q = _low_side(0)
    assert simulate(off, until=1e-4).at(I(q, "d"), 1e-4) == pytest.approx(0, abs=1e-6)


def test_nmos_saturates_at_the_square_law():
    ed, eg, q = VoltageSource(), VoltageSource(), NMOS()
    circuit, _ = net((ed, "GND", "d"), (eg, "GND", "g"), (q, "g", "d", "GND"))
    end = simulate(Problem(circuit, {ed: 10, eg: 3}), until=1e-5)
    assert end.at(I(q, "d"), 1e-5) == pytest.approx(0.5 / 2 * (3 - 2) ** 2 * (1 + 0.01 * 10), rel=1e-3)


def test_pmos_as_a_high_side_switch():
    def out(gate):
        e, eg, q, r = VoltageSource(), VoltageSource(), PMOS(), Resistor()
        circuit, n = net((e, "GND", "vcc"), (eg, "GND", "g"), (q, "g", "out", "vcc"), (r, "out", "GND"))
        return simulate(Problem(circuit, {e: 5, eg: gate, r: 100}), until=1e-4).at(V(n["out"]), 1e-4)

    assert out(0) > 4.8
    assert out(5) == pytest.approx(0, abs=1e-3)


def test_nmos_body_diode_conducts_backwards():
    e, r, q = VoltageSource(), Resistor(), NMOS()
    circuit, n = net((e, "GND", "a"), (r, "a", "s"), (q, "s", "GND", "s"))
    assert 0.55 < simulate(Problem(circuit, {e: 5, r: 1000}), until=1e-4).at(V(n["s"]), 1e-4) < 0.75


def test_nmos_follows_a_square_on_its_gate():
    e, r, sq, q = VoltageSource(), Resistor(), SquareSource(), NMOS()
    circuit, n = net((e, "GND", "vcc"), (r, "vcc", "d"), (sq, "GND", "g"), (q, "g", "d", "GND"))
    trace = simulate(Problem(circuit, {e: 12, r: 100, sq: 5}), until=3e-3)
    assert trace.at(V(n["d"]), 0.2e-3) < 1 and trace.at(V(n["d"]), 0.7e-3) > 11.9


def test_a_capacitor_across_an_ideal_source_charges_at_once():
    e, c = VoltageSource(), Capacitor()
    circuit, n = net((e, "GND", "a"), (c, "a", "GND"))
    assert simulate(Problem(circuit, {e: 5, c: "1u"}), until=1e-3).at(V(n["a"]), 1e-3) == pytest.approx(5)


def _divider(sensor, **reading):
    e, r = VoltageSource(), Resistor()
    circuit, n = net((e, "GND", "in"), (r, "in", "A"), (sensor, "A", "GND"))
    return Problem(circuit, {e: 5, r: 10000, sensor: {"": 10000, **reading}}), n


def test_photoresistor_follows_the_light_on_paper_and_in_time():
    ldr = Photoresistor()
    at10, _ = _divider(ldr, lux=10)
    assert float(solve(at10)(U(ldr))) == pytest.approx(2.5)
    at1, _ = _divider(ldr, lux=1)
    assert float(solve(at1)(U(ldr))) == pytest.approx(5 * 10**0.7 / (1 + 10**0.7), rel=1e-3)
    room, n = _divider(ldr)
    trace = simulate(room, until=1e-3, inputs={ldr: lambda t: 10 if t > 5e-4 else 1000})
    assert trace.at(V(n["A"]), 4e-4) < 0.5 and trace.at(V(n["A"]), 1e-3) == pytest.approx(2.5, abs=0.01)


def test_thermistor_is_its_value_at_25_and_less_when_warm():
    for t, ratio in ((25, 1), (50, math.exp(3950 * (1 / 323.15 - 1 / 298.15)))):
        rt = Thermistor()
        problem, _ = _divider(rt, temperature=t)
        u = float(solve(problem)(U(rt)))
        assert u == pytest.approx(5 * ratio / (1 + ratio), rel=1e-3)


def test_rgb_led_and_seven_segment_light_each_channel():
    e, r1, r2, rgb = VoltageSource(), Resistor(), Resistor(), RGBLED()
    circuit, _ = net((e, "GND", "v"), (r1, "v", "r"), (r2, "v", "b"), (rgb, "r", "GND", "b", "GND"))
    end = simulate(Problem(circuit, {e: 5, r1: 150, r2: 100}), until=1e-4)
    assert end.at(I(rgb, "r"), 1e-4) == pytest.approx(0.02, abs=2e-3)
    assert end.at(I(rgb, "b"), 1e-4) == pytest.approx(0.019, abs=2e-3)
    assert abs(end.at(I(rgb, "g"), 1e-4)) < 1e-9
    e, r1, r2, digit = VoltageSource(), Resistor(), Resistor(), SevenSegment()
    pins = ["GND", "b", "c", "GND", "GND", "GND", "GND", "GND", "GND"]
    circuit, _ = net((e, "GND", "v"), (r1, "v", "b"), (r2, "v", "c"), (digit, *pins))
    end = simulate(Problem(circuit, {e: 5, r1: 150, r2: 150}), until=1e-4)
    assert end.at(I(digit, "b"), 1e-4) == pytest.approx(0.02, abs=2e-3)
    assert end.at(I(digit, "c"), 1e-4) == pytest.approx(0.02, abs=2e-3)
    assert end.at(I(digit, "a"), 1e-4) == pytest.approx(0, abs=1e-9)


def test_buzzers_and_servo_are_their_loads():
    for kind, current in ((Buzzer, sp.Rational(5, 160)), (PassiveBuzzer, sp.Rational(5, 16))):
        e, b = VoltageSource(), kind()
        circuit, _ = net((e, "GND", "a"), (b, "a", "GND"))
        assert solve(Problem(circuit, {e: 5}))(I(b)) == current
    e, es, servo = VoltageSource(), VoltageSource(), Servo()
    circuit, _ = net((e, "GND", "vcc"), (es, "GND", "s"), (servo, "s", "vcc", "GND"))
    assert solve(Problem(circuit, {e: 5, es: 3}))(I(servo, "vcc")) == sp.Rational(1, 100)


def test_ultrasonic_echo_is_set_from_outside():
    e, et, r, sonar = VoltageSource(), VoltageSource(), Resistor(), Ultrasonic()
    circuit, n = net((e, "GND", "vcc"), (et, "GND", "trig"), (r, "echo", "GND"), (sonar, "vcc", "trig", "echo", "GND"))
    problem = Problem(circuit, {e: 5, et: 5, r: 10000})
    assert solve(problem)(I(sonar, "vcc")) == sp.Rational(5, 333)
    trace = simulate(problem, until=1e-3, inputs={sonar: lambda t: 1 if t > 5e-4 else 0})
    assert trace.at(V(n["echo"]), 4e-4) == pytest.approx(0, abs=1e-6)
    assert trace.at(V(n["echo"]), 1e-3) == pytest.approx(5 * 10000 / 10100, rel=1e-3)


def test_lcd_senses_its_inputs_and_lights_its_backlight():
    e, r, lcd = VoltageSource(), Resistor(), LCD1602()
    bus = ["GND"] * 11
    bus[2], bus[10] = "vcc", "vcc"
    circuit, _ = net((e, "GND", "vcc"), (r, "vcc", "a"), (lcd, "GND", "vcc", "GND", *bus, "a", "GND"))
    trace = simulate(Problem(circuit, {e: 5, r: 100}), until=1e-4)
    assert trace.at("U_LCD_1_e", 1e-4) == trace.at("U_LCD_1_d7", 1e-4) == pytest.approx(5)
    assert trace.at("U_LCD_1_rs", 1e-4) == pytest.approx(0)
    assert trace.at(I(lcd, "a"), 1e-4) == pytest.approx(0.02, abs=3e-3)
    assert trace.at(I(lcd, "vdd"), 1e-4) == pytest.approx(1e-3)


def test_i2c_modules_pull_their_lines_up_and_load_the_supply():
    e, lcd, oled, rtc, r = VoltageSource(), LCD1602I2C(), SSD1306(), DS1307(), Resistor()
    circuit, _ = net(
        (e, "GND", "vcc"),
        (lcd, "GND", "vcc", "sda", "scl"),
        (oled, "GND", "vcc", "scl", "sda"),
        (rtc, "GND", "vcc", "sda", "scl"),
        (r, "sda", "GND"),
    )
    s = solve(Problem(circuit, {e: 5, r: 10000}))
    three = sp.Rational(4700, 3)
    assert s(U(r)) == 5 * 10000 / (10000 + three)


def test_pico_drives_its_pins_at_3v3_and_supplies_both_rails():
    pico, r, led, load = Pico(), Resistor(), LED(), Resistor()
    pins = ["GND" if p == "GP1" else ("led" if p == "GP15" else f"free_{p}") for p in Pico.terminals[:-3]]
    circuit, n = net((pico, *pins, "vbus", "v33", "GND"), (r, "led", "a"), (led, "a", "GND"), (load, "v33", "GND"))
    problem = Problem(circuit, {r: 100, load: 1000})
    lit = simulate(problem, until=1e-4, inputs={(pico, "GP15"): "high"})
    assert lit.at(I(led), 1e-4) == pytest.approx((3.3 - 2.0) / 140, rel=0.15)
    assert lit.at(V(n["v33"]), 1e-4) == pytest.approx(3.3) and lit.at(V(n["vbus"]), 1e-4) == pytest.approx(5)
    dark = simulate(problem, until=1e-4, inputs={(pico, "GP15"): "pulldown"})
    assert dark.at(I(led), 1e-4) == pytest.approx(0, abs=1e-6)


def test_ili9341_loads_the_3v3_rail_and_its_backlight_pin():
    pico, tft = Pico(), ILI9341()
    wired = {"GP17": "cs", "GP18": "sck", "GP19": "mosi", "GP20": "dc", "GP21": "rst", "GP22": "bl"}
    pins = [wired.get(p, f"free_{p}") for p in Pico.terminals[:-3]]
    circuit, n = net(
        (pico, *pins, "vbus", "v33", "GND"), (tft, "v33", "GND", "cs", "rst", "dc", "mosi", "sck", "bl", "miso")
    )
    problem = Problem(circuit)
    lit = simulate(problem, until=1e-4, inputs={(pico, "GP22"): "high"})
    assert lit.at(V(n["bl"]), 1e-4) == pytest.approx(3.3 * 1000 / 1040, rel=1e-3)
    assert lit.at(I(tft, "vcc"), 1e-4) == pytest.approx(3.3 / 150, rel=1e-3)


def test_spectrum_of_a_square_wave():
    e, r = SquareSource(), Resistor()
    circuit, _ = net((e, "GND", "a"), (r, "a", "GND"))
    trace = simulate(Problem(circuit, {e: {"": 1, "f": 100}, r: 1}), until=0.1)
    f, amplitude = trace.spectrum(U(r), f_max=1000)

    def at(x):
        return amplitude[round(x / f[1])]

    assert at(0) == pytest.approx(0.5, abs=0.01)
    for k in (1, 3, 5):
        assert at(100 * k) == pytest.approx(2 / (math.pi * k), rel=0.02)
    assert at(200) < 0.01 and at(400) < 0.01


def _clock():
    clock = SquareSource()
    return clock, {clock: {"": 5, "f": 1000}}


def test_counter_counts_rising_edges_and_resets():
    for reset, count in ((0, 6), (5, 0)):
        (clock, given), er, counter = _clock(), VoltageSource(), Counter()
        loads = [Resistor() for _ in range(4)]
        circuit, n = net(
            (clock, "GND", "CLK"),
            (er, "GND", "RST"),
            (counter, "CLK", "RST", "Q0", "Q1", "Q2", "Q3", "GND"),
            *((r, f"Q{k}", "GND") for k, r in enumerate(loads)),
        )
        trace = simulate(Problem(circuit, {**given, er: reset, **dict.fromkeys(loads, "10k")}), until=0.0055)
        assert round(trace("count_U_1")[-1]) == count
    assert [round(trace.at(V(n[f"Q{k}"]), 0.0055)) for k in range(4)] == [0, 0, 0, 0]


def test_jk_flip_flop_toggles_with_both_high():
    """Not at the first edge, at power-up: just before it, j and k were still at rest."""
    (clock, given), eh, ff = _clock(), VoltageSource(), JKFlipFlop()
    circuit, n = net((clock, "GND", "CLK"), (eh, "GND", "H"), (ff, "H", "CLK", "H", "Q", "NQ", "GND"))
    trace = simulate(Problem(circuit, {**given, eh: 5}), until=0.0045)
    assert [round(trace.at(V(n["Q"]), t)) for t in (0.0005, 0.0015, 0.0025, 0.0035)] == [0, 5, 0, 5]
    assert round(trace.at(V(n["NQ"]), 0.0015)) == 0


def test_d_flip_flop_takes_d_on_the_edge_only():
    """d as it was just before each edge: at power-up still at rest, then high until 1.67 ms."""
    (clock, given), d, ff = _clock(), SquareSource(), DFlipFlop()
    circuit, n = net((clock, "GND", "CLK"), (d, "GND", "D"), (ff, "D", "CLK", "Q", "NQ", "GND"))
    trace = simulate(Problem(circuit, {**given, d: {"": 5, "f": 300}}), until=0.01)
    assert [round(trace.at(V(n["Q"]), t)) for t in (0.0005, 0.0015, 0.0025)] == [0, 5, 0]


def test_gates_in_a_loop_keep_a_state():
    a, b, e = AND(), AND(), VoltageSource()
    circuit, n = net((e, "GND", "H"), (a, "H", "Y2", "Y1", "GND"), (b, "H", "Y1", "Y2", "GND"))
    trace = simulate(Problem(circuit, {e: 5}), until=1e-5)
    assert {round(trace.at(V(n["Y1"]), 1e-5)), round(trace.at(V(n["Y2"]), 1e-5))} <= {0, 5}


def test_real_parts():
    def drop(given):
        e, r, d = VoltageSource(), Resistor(), Diode()
        circuit, n = net((e, "GND", "a"), (r, "a", "A"), (d, "A", "GND"))
        return simulate(Problem(circuit, {e: 5, r: 430, **({d: given} if given else {})}), until=1e-3)(V(n["A"]))[-1]

    assert 0.6 < drop(DIODE_PARTS["1N4148"]) < drop(None) < 0.75
    e, amp = SineSource(), OpAmpModel()
    circuit, n = net((e, "GND", "IN"), (amp, "IN", "GND", "OUT", "GND"))
    trace = simulate(Problem(circuit, {e: {"": 1, "f": 100}, amp: OPAMP_PARTS["LM358"]}), until=0.02)
    v, t = trace(V(n["OUT"])), trace.t
    assert min(v) == pytest.approx(-15, abs=0.3) and max(v) == pytest.approx(13.5, abs=0.3)
    slope = max((v[i] - v[i - 1]) / (t[i] - t[i - 1]) for i in range(1, len(t)) if t[i] > t[i - 1])
    assert slope == pytest.approx(0.3e6, rel=0.1)
    e, amp, rf, rg = SineSource(), OpAmpModel(), Resistor(), Resistor()
    circuit, n = net((e, "GND", "IN"), (amp, "IN", "F", "OUT", "GND"), (rf, "OUT", "F"), (rg, "F", "GND"))
    trace = simulate(Problem(circuit, {e: {"": "0.1", "f": 1000}, rf: "9k", rg: "1k"}), until=0.005)
    out = trace(V(n["OUT"]))
    assert max(out[len(out) // 2 :]) == pytest.approx(1, rel=0.02)
    assert BJT_PARTS["BC547B"]["BF"] > 200


def test_the_textbook_diode_is_for_paper():
    from electro import DiodeDrop

    e, r, d = VoltageSource(), Resistor(), DiodeDrop()
    circuit, _ = net((e, "GND", "a"), (r, "a", "b"), (d, "b", "GND"))
    with pytest.raises(NotSimulated):
        compile_program(Problem(circuit, {e: 5, r: 1000}))


def test_power_of_a_lamp_in_time():
    from electro import Lamp

    e, h = VoltageSource(), Lamp()
    circuit, _ = net((e, "GND", "a"), (h, "a", "GND"))
    problem = Problem(circuit, {e: 6, h: 12})
    assert solve(problem)(P(h)) == 3
    assert simulate(problem, until=1e-3).at(P(h), 1e-3) == pytest.approx(3)
