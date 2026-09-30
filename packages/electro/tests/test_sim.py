"""Simulation in time: the step-by-step results against what the textbook says."""

import math

import pytest
from electro import (
    DS1307,
    LCD1602,
    LCD1602I2C,
    LED,
    NMOS,
    NPN,
    PMOS,
    RGBLED,
    SSD1306,
    Arduino,
    Button,
    Buzzer,
    Capacitor,
    Counter,
    DFlipFlop,
    Inductor,
    JKFlipFlop,
    PassiveBuzzer,
    Photoresistor,
    Potentiometer,
    Resistor,
    Servo,
    SevenSegment,
    SineSource,
    SquareSource,
    Switch,
    Thermistor,
    Timer555,
    Ultrasonic,
    VoltageSource,
    Zener,
    code,
    ground,
    net,
    node,
    simulate,
    supply,
)
from electro.issues import NeedsSimulation, NoSuchInput, ValueNeeded
from electro.sim import compile_sim


def test_rc_charges_like_the_exponential():
    trace = simulate(supply(5) + Resistor(1000) + node("A") + Capacitor(1e-3) + ground, t=5)
    for t in (0.5, 1, 2, 5):
        assert trace.at(t)["V_A"] == pytest.approx(5 * (1 - math.exp(-t)), abs=0.05)


def test_rl_current_rises_like_the_exponential():
    trace = simulate(supply(10) + Resistor(10) + Inductor(1) + ground, t=0.5)  # τ = L/R = 0.1 s
    assert trace.at(0.1)["I_L_1"] == pytest.approx(1 - math.exp(-1), abs=0.02)
    assert trace.at(0.5)["I_L_1"] == pytest.approx(1, abs=0.02)


def test_led_with_its_resistor():
    trace = simulate(supply(5) + Resistor(150) + LED() + ground, t=1e-3)
    end = trace.at(1e-3)
    assert end["U_LED_1"] == pytest.approx(2.0, abs=0.02)  # red: 2 V at 20 mA
    assert end["I_LED_1"] == pytest.approx(0.02, abs=5e-4)
    blue = simulate(supply(5) + Resistor(150) + LED("blue") + ground, t=1e-3).at(1e-3)
    assert blue["U_LED_1"] > 3


def test_555_astable_blinks_at_the_textbook_period():
    astable = net(
        (VoltageSource(9), "GND", "vcc"),
        (Timer555(), "GND", "tc", "out", "vcc", "ctrl", "tc", "dis", "vcc"),
        (Resistor(1000), "vcc", "dis"),
        (Resistor(10000), "dis", "tc"),
        (Capacitor(100e-6), "tc", "GND"),
        (Resistor(330), "out", "a"),
        (LED("green"), "a", "GND"),
    )
    trace = simulate(astable, t=5)
    out = trace.V("out")
    rising = [trace.t[i] for i in range(1, len(out)) if out[i - 1] < 4 <= out[i]]
    period = rising[2] - rising[1]
    assert period == pytest.approx(0.693 * (1000 + 2 * 10000) * 100e-6, rel=0.05)
    settled = trace.V("tc")[len(out) // 2 :]
    assert min(settled) == pytest.approx(3, abs=0.1) and max(settled) == pytest.approx(6, abs=0.1)  # ⅓, ⅔ of 9 V


def test_two_transistor_multivibrator_takes_turns():
    multi = net(
        (VoltageSource(9), "GND", "vcc"),
        (Resistor(470), "vcc", "a1"),
        (LED("red"), "a1", "c1"),
        (Resistor(470), "vcc", "a2"),
        (LED("green"), "a2", "c2"),
        (Resistor(47000), "vcc", "b2"),
        (Resistor(47000), "vcc", "b1"),
        (Capacitor(47e-6), "c1", "b2"),
        (Capacitor(33e-6), "c2", "b1"),
        (NPN(), "b1", "c1", "GND"),
        (NPN(), "b2", "c2", "GND"),
    )
    trace = simulate(multi, t=3.5)
    # at first both conduct while the capacitors charge; then they take turns
    lit = [(s["I_LED_1"] > 0.005, s["I_LED_2"] > 0.005) for s in map(trace.at, (1.25, 1.75, 2.25, 2.75, 3.25))]
    assert sum(a != b for a, b in lit) >= 4  # (nearly) always exactly one lit
    assert {(True, False), (False, True)} <= set(lit)  # and both get a turn


def test_arduino_pins_switches_and_potentiometer():
    board = net(
        (Arduino(), *[f"d{i}" for i in range(14)], *[f"a{i}" for i in range(6)], "5V", "GND"),
        (Resistor(220), "d13", "x"),
        (LED(), "x", "GND"),
        (Button(), "d2", "GND"),
        (Potentiometer(10000), "5V", "GND", "a0"),
    )
    trace = simulate(
        board,
        t=2,
        dt=0.01,
        inputs={
            "ARD_1.D13": lambda t: "high" if t % 1 < 0.5 else "low",
            "ARD_1.D2": "pullup",
            "B_1": lambda t: t > 1.5,
            "P_1": 0.25,
        },
    )
    assert trace.at(0.2)["I_LED_1"] == pytest.approx(0.0124, abs=5e-4)  # (5 − 2) V / (220 + 25) Ω
    assert trace.at(0.7)["I_LED_1"] == pytest.approx(0, abs=1e-6)
    assert trace.at(1.2)["V_d2"] == pytest.approx(5, abs=0.01)  # pulled up
    assert trace.at(1.7)["V_d2"] == pytest.approx(0, abs=0.01)  # the button pressed
    assert trace.at(1)["V_a0"] == pytest.approx(3.75, abs=0.01)  # a quarter of the way from 5 V
    with pytest.raises(NoSuchInput):
        simulate(board, t=0.1, inputs={"S_9": 1})


def test_on_paper_switches_work_and_semiconductors_ask_for_a_simulation():
    closed = (supply(5) + Resistor(100) + Switch(closed=True) + Resistor(100) + ground).solve()
    assert closed["R_1"].I == pytest.approx(0.025)
    with pytest.raises(NeedsSimulation):
        (supply(5) + Resistor(100) + LED() + ground).solve()
    with pytest.raises(ValueNeeded):
        compile_sim(supply(5) + Resistor() + ground)


def test_code_writes_the_new_elements_back():
    c = supply(5) + Resistor(100) + LED("green") + Switch(closed=True) + ground
    assert "LED('green')" in code(c) and "Switch(closed=True)" in code(c)
    scope: dict = {}
    exec("from electro import *\n" + code(c), scope)
    assert code(scope["uklad"]) == code(c)


def test_the_program_in_javascript_is_the_same_program():
    program = compile_sim(supply(5) + Resistor(150) + LED() + ground)
    data = program.to_json()
    assert "limexp(" in data and "F[" in data and "J[" in data


def test_sine_source_through_an_rc_low_pass():
    # f = 1/(2π·RC): the capacitor gets 1/√2 of the amplitude, a quarter period behind at most
    R, C = 1000, 1e-6
    f = 1 / (2 * math.pi * R * C)
    trace = simulate(
        net((SineSource(10, frequency=f), "GND", "in"), (Resistor(R), "in", "out"), (Capacitor(C), "out", "GND")),
        t=10 / f,
    )
    settled = [v for t, v in zip(trace.t, trace.V("out")) if t > 5 / f]
    assert max(settled) == pytest.approx(10 / math.sqrt(2), rel=0.03)
    assert max(v for t, v in zip(trace.t, trace.V("in")) if t > 5 / f) == pytest.approx(10, rel=0.01)


def test_square_source_has_its_frequency_and_duty():
    trace = simulate(net((SquareSource(5, frequency=1000, duty=0.25), "GND", "a"), (Resistor(100), "a", "GND")), t=0.01)
    v = trace.V("a")
    rising = [trace.t[i] for i in range(1, len(v)) if v[i - 1] < 2.5 <= v[i]]
    assert rising[3] - rising[2] == pytest.approx(1e-3, rel=0.02)
    high = sum(t1 - t0 for t0, t1, u in zip(trace.t, trace.t[1:], v[1:]) if u > 2.5)
    assert high / trace.t[-1] == pytest.approx(0.25, abs=0.02)


def test_sine_source_on_paper_is_a_phasor_and_the_square_needs_time():
    sine = net((SineSource(10, frequency=50), "GND", "a"), (Resistor(5), "a", "GND"))
    assert complex(sine.solve(omega=100 * math.pi)["R_1"].I) == pytest.approx(2)
    assert complex(sine.solve()["R_1"].I) == pytest.approx(2)  # no omega: its own frequency's
    shifted = net((SineSource(10, frequency=50, phase=90), "GND", "a"), (Resistor(5), "a", "GND"))
    assert complex(shifted.solve()["R_1"].I) == pytest.approx(2j)
    assert max(simulate(shifted, t=0.001)["V_a"][:3]) == pytest.approx(10, rel=0.01)  # sin(90°) at t = 0
    with pytest.raises(NeedsSimulation):
        net((SquareSource(5), "GND", "a"), (Resistor(5), "a", "GND")).solve()


def test_sources_in_time_come_back_as_code():
    assert "SineSource(10, frequency=50)" in code(net((SineSource(10), "GND", "a"), (Resistor(5), "a", "GND")))
    square = SquareSource.from_schematic("5", "2 kHz 25%", "E_1")
    assert (square.frequency, square.duty) == (2000, 0.25)
    assert square.options() == ["frequency=2000", "duty=0.25"]


def test_zener_holds_its_voltage_whatever_the_load():
    for load in (1e6, 1000):  # no load; a 1 kΩ load taking a third of the current
        regulator = net(
            (VoltageSource(12), "GND", "in"),
            (Resistor(470), "in", "out"),
            (Zener(5.1), "GND", "out"),
            (Resistor(load), "out", "GND"),
        )
        assert simulate(regulator, t=1e-3).at(1e-3)["V_out"] == pytest.approx(5.1, abs=0.1)


def test_zener_forward_is_a_diode():
    end = simulate(supply(5) + Resistor(1000) + Zener(5.1) + ground, t=1e-3).at(1e-3)
    assert 0.55 < end["U_DZ_1"] < 0.75


def test_zener_clips_a_sine_between_its_forward_drop_and_breakdown():
    clipper = net(
        (SineSource(10, frequency=50), "GND", "in"), (Resistor(1000), "in", "out"), (Zener(5.1), "GND", "out")
    )
    out = simulate(clipper, t=0.04).V("out")
    assert max(out) == pytest.approx(5.1, abs=0.15)
    assert min(out) == pytest.approx(-0.7, abs=0.1)


def test_nmos_as_a_low_side_switch():
    def switch(gate):
        return net(
            (VoltageSource(12), "GND", "vcc"),
            (Resistor(10), "vcc", "d"),
            (VoltageSource(gate), "GND", "in"),
            (Resistor(100), "in", "g"),
            (NMOS(), "g", "d", "GND"),
        )

    on = simulate(switch(5), t=1e-4).at(1e-4)
    rds = 1 / (NMOS.K * (5 - NMOS.VTH))
    assert on["I_Q_1_D"] == pytest.approx(12 / (10 + rds), rel=0.05)
    assert on["I_Q_1_G"] == pytest.approx(0, abs=1e-6)  # charged: the gate takes no current
    assert simulate(switch(0), t=1e-4).at(1e-4)["I_Q_1_D"] == pytest.approx(0, abs=1e-6)


def test_nmos_saturates_at_the_square_law():
    end = simulate(
        net((VoltageSource(10), "GND", "d"), (VoltageSource(3), "GND", "g"), (NMOS(), "g", "d", "GND")), t=1e-5
    ).at(1e-5)
    assert end["I_Q_1_D"] == pytest.approx(NMOS.K / 2 * (3 - NMOS.VTH) ** 2 * (1 + NMOS.LAMBDA * 10), rel=1e-3)


def test_pmos_as_a_high_side_switch():
    def switch(gate):
        return net(
            (VoltageSource(5), "GND", "vcc"),
            (VoltageSource(gate), "GND", "g"),
            (PMOS(), "g", "out", "vcc"),
            (Resistor(100), "out", "GND"),
        )

    assert simulate(switch(0), t=1e-4).at(1e-4)["V_out"] > 4.8
    assert simulate(switch(5), t=1e-4).at(1e-4)["V_out"] == pytest.approx(0, abs=1e-3)


def test_nmos_body_diode_conducts_backwards():
    end = simulate(
        net((VoltageSource(5), "GND", "a"), (Resistor(1000), "a", "s"), (NMOS(), "s", "GND", "s")), t=1e-4
    ).at(1e-4)
    assert 0.55 < end["V_s"] < 0.75


def test_nmos_follows_a_square_on_its_gate():
    pwm = net(
        (VoltageSource(12), "GND", "vcc"),
        (Resistor(100), "vcc", "d"),
        (SquareSource(5, frequency=1000), "GND", "g"),
        (NMOS(), "g", "d", "GND"),
    )
    trace = simulate(pwm, t=3e-3)
    assert trace.at(0.2e-3)["V_d"] < 1 and trace.at(0.7e-3)["V_d"] > 11.9


def test_a_capacitor_across_an_ideal_source_charges_at_once():
    assert simulate(net((VoltageSource(5), "GND", "a"), (Capacitor(1e-6), "a", "GND")), t=1e-3).at(1e-3)[
        "V_a"
    ] == pytest.approx(5)


def test_photoresistor_follows_the_light_on_paper_and_in_time():
    divider = lambda lux: supply(5) + Resistor(10000) + node("A") + Photoresistor(10000, lux=lux) + ground
    assert float(divider(10).solve()["LDR_1"].U) == pytest.approx(2.5)  # 10 kΩ at 10 lux: half
    darker = divider(1).solve()["LDR_1"].U
    assert float(darker) == pytest.approx(5 * 10000 * 10**0.7 / (10000 + 10000 * 10**0.7), rel=1e-3)
    trace = simulate(divider(100), t=1e-3, inputs={"LDR_1": lambda t: 10 if t > 5e-4 else 1000})
    assert trace.at(4e-4)["V_A"] < 0.5 and trace.at(1e-3)["V_A"] == pytest.approx(2.5, abs=0.01)


def test_thermistor_is_its_value_at_25_and_less_when_warm():
    for t, ratio in ((25, 1), (50, math.exp(3950 * (1 / 323.15 - 1 / 298.15)))):
        sol = (supply(1) + Thermistor(10000, temperature=t) + ground).solve()
        assert float(sol["RT_1"].I) == pytest.approx(1 / (10000 * ratio), rel=1e-3)
    assert "Thermistor(10000, temperature=50)" in code(supply(1) + Thermistor(10000, temperature=50) + ground)


def test_rgb_led_and_seven_segment_light_each_channel():
    rgb = net(
        (VoltageSource(5), "GND", "v"),
        (Resistor(150), "v", "r"),
        (Resistor(100), "v", "b"),
        (RGBLED(), "r", "GND", "b", "GND"),
    )  # green tied to the cathode: dark
    end = simulate(rgb, t=1e-4).at(1e-4)
    assert end["I_LED_1_r"] == pytest.approx(0.02, abs=2e-3)
    assert end["I_LED_1_b"] == pytest.approx(0.019, abs=2e-3)
    assert abs(end["I_LED_1_g"]) < 1e-9
    one = net(
        (VoltageSource(5), "GND", "v"),
        (Resistor(150), "v", "b"),
        (Resistor(150), "v", "c"),
        (SevenSegment(), "GND", "b", "c", "GND", "GND", "GND", "GND", "GND", "GND"),
    )
    end = simulate(one, t=1e-4).at(1e-4)
    assert end["I_DS_1_b"] == end["I_DS_1_c"] == pytest.approx(0.02, abs=2e-3)
    assert end["I_DS_1_a"] == pytest.approx(0, abs=1e-9)


def test_buzzers_and_servo_are_their_loads():
    assert (supply(5) + Buzzer() + ground).solve()["BZ_1"].I == pytest.approx(5 / 160)
    assert (supply(5) + PassiveBuzzer() + ground).solve()["BZ_1"].I == pytest.approx(5 / 16)
    servo = net((VoltageSource(5), "GND", "vcc"), (VoltageSource(3), "GND", "s"), (Servo(), "s", "vcc", "GND")).solve()
    assert servo["M_1"].I == pytest.approx(0.01) and servo["M_1"].U == 5


def test_ultrasonic_echo_is_a_source_set_from_outside():
    sensor = net(
        (VoltageSource(5), "GND", "vcc"),
        (VoltageSource(5), "GND", "trig"),
        (Resistor(10000), "echo", "GND"),
        (Ultrasonic(distance=50), "vcc", "trig", "echo", "GND"),
    )
    quiet = sensor.solve()
    assert quiet["US_1"].I == pytest.approx(5 / 333) and quiet["US_1"].U == 5
    trace = simulate(sensor, t=1e-3, inputs={"US_1_echo": lambda t: 1 if t > 5e-4 else 0})
    assert trace.at(4e-4)["V_echo"] == pytest.approx(0, abs=1e-6)
    assert trace.at(1e-3)["V_echo"] == pytest.approx(5 * 10000 / 10100, rel=1e-3)
    assert "Ultrasonic(distance=50)" in code(sensor)


def test_lcd_senses_its_inputs_and_lights_its_backlight():
    pins = {p: "GND" for p in ("rs", "rw", "e", "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7")}
    pins |= {"e": "vcc", "d7": "vcc"}
    lcd = net(
        (VoltageSource(5), "GND", "vcc"),
        (Resistor(100), "vcc", "a"),
        (LCD1602(), "GND", "vcc", "GND", *pins.values(), "a", "GND"),
    )
    end = simulate(lcd, t=1e-4).at(1e-4)
    assert end["U_LCD_1_e"] == end["U_LCD_1_d7"] == pytest.approx(5)
    assert end["U_LCD_1_rs"] == pytest.approx(0)
    assert end["I_LCD_1_a"] == pytest.approx(0.02, abs=3e-3)  # 3 V backlight behind 100 Ω
    assert end["I_LCD_1"] == pytest.approx(1e-3)


def test_i2c_modules_pull_their_lines_up_and_load_the_supply():
    bus = net(
        (VoltageSource(5), "GND", "vcc"),
        (LCD1602I2C(), "GND", "vcc", "sda", "scl"),
        (SSD1306(address=0x3D), "GND", "vcc", "scl", "sda"),
        (DS1307(), "GND", "vcc", "sda", "scl"),
        (Resistor(10000), "sda", "GND"),
    )
    sol = bus.solve()
    assert sol["LCD_1"].I == pytest.approx(5 / 200) and sol["RTC_1"].I == pytest.approx(5 / 3300)
    three = 4700 / 3  # three modules' pull-ups in parallel, against the 10 kΩ to ground
    assert float(sol["R_1"].U) == pytest.approx(5 * 10000 / (10000 + three))
    assert "SSD1306(address=0x3D)" in code(bus)


def test_pico_drives_its_pins_at_3v3_and_supplies_both_rails():
    from electro import Pico

    board = ["GND" if p == "GP1" else ("led" if p == "GP15" else f"free_{p}") for p in Pico.PINS]
    blink = net(
        (Pico(), *board, "vbus", "v33", "GND"),
        (Resistor(100), "led", "a"),
        (LED(), "a", "GND"),
        (Resistor(1000), "v33", "GND"),
    )
    lit = simulate(blink, t=1e-4, inputs={"PICO_1.GP15": "high"}).at(1e-4)
    assert lit["I_LED_1"] == pytest.approx((3.3 - 2.0) / 140, rel=0.15)  # 100 Ω + the pin's 40 Ω, a red LED's 2 V
    assert lit["V_v33"] == pytest.approx(3.3) and lit["V_vbus"] == pytest.approx(5)
    dark = simulate(blink, t=1e-4, inputs={"PICO_1.GP15": "pulldown"}).at(1e-4)
    assert dark["I_LED_1"] == pytest.approx(0, abs=1e-6)
    rail = net((Pico(), *board, "vbus", "v33", "GND"), (Resistor(1000), "v33", "GND"))
    assert rail.solve()["R_1"].I == pytest.approx(3.3e-3)  # on paper: the 3V3 rail


def test_ili9341_loads_the_3v3_rail_and_its_backlight_pin():
    from electro import ILI9341, Pico

    wired = {"GP17": "cs", "GP18": "sck", "GP19": "mosi", "GP20": "dc", "GP21": "rst", "GP22": "bl"}
    board = [wired.get(p, f"free_{p}") for p in Pico.PINS]
    tft = net(
        (Pico(), *board, "vbus", "v33", "GND"),
        (ILI9341(), "v33", "GND", "cs", "rst", "dc", "mosi", "sck", "bl", "miso"),
    )
    assert "ILI9341()" in code(tft)
    solved = tft.solve()  # on paper: the pins float, the module takes its load off the 3V3 rail
    assert solved["TFT_1"].I == pytest.approx(3.3 / 150)
    lit = simulate(tft, t=1e-4, inputs={"PICO_1.GP22": "high"}).at(1e-4)
    assert lit["V_bl"] == pytest.approx(3.3 * 1000 / 1040, rel=1e-3)  # the pin's 40 Ω, the backlight driver's 1 kΩ


def test_spectrum_of_a_square_wave():
    """Odd harmonics only, 4/(πn) of the half swing each; the mean at 0 Hz."""
    trace = simulate(ground.transpose() + SquareSource(1, frequency=100) + Resistor(1) + ground, t=0.1)
    s = trace.spectrum("U_R_1", f_max=1000)
    at = lambda f: s["U_R_1"][round(f / s.t[1])]  # noqa: E731
    assert at(0) == pytest.approx(0.5, abs=0.01)
    for n in (1, 3, 5):
        assert at(100 * n) == pytest.approx(2 / (math.pi * n), rel=0.02)
    assert at(200) < 0.01 and at(400) < 0.01


CLOCK = (SquareSource(5, frequency=1000), "GND", "CLK")  # rising edges at 0, 1, 2, … ms


def test_counter_counts_rising_edges_and_resets():
    loads = [(Resistor("10k"), f"Q{k}", "GND") for k in range(4)]
    c = net(CLOCK, (Resistor(1), "RST", "GND"), (Counter(), "CLK", "RST", "Q0", "Q1", "Q2", "Q3"), *loads)
    trace = simulate(c, t=0.0055)
    assert trace["U_U_1_count"][-1] == 6
    assert [round(trace.at(0.0055)[f"V_Q{k}"]) for k in range(4)] == [0, 5, 5, 0]  # 6 = 0b0110
    held = net(CLOCK, (VoltageSource(5), "GND", "RST"), (Counter(), "CLK", "RST", "Q0", "Q1", "Q2", "Q3"), *loads)
    assert simulate(held, t=0.0055)["U_U_1_count"][-1] == 0


def test_jk_flip_flop_toggles_with_both_high():
    c = net(CLOCK, (VoltageSource(5), "GND", "H"), (JKFlipFlop(), "H", "CLK", "H", "Q", "NQ"))
    trace = simulate(c, t=0.0045)
    assert [round(trace.at(t)["V_Q"]) for t in (0.0005, 0.0015, 0.0025, 0.0035)] == [5, 0, 5, 0]
    assert round(trace.at(0.0015)["V_NQ"]) == 5


def test_d_flip_flop_takes_d_on_the_edge_only():
    c = net(CLOCK, (SquareSource(5, frequency=300), "GND", "D"), (DFlipFlop(), "D", "CLK", "Q", "NQ"))
    trace = simulate(c, t=0.01)
    # D is high until 1.67 ms: the edges at 0 and 1 ms give 1, the one at 2 ms gives 0
    assert [round(trace.at(t)["V_Q"]) for t in (0.0005, 0.0015, 0.0025)] == [5, 5, 0]
