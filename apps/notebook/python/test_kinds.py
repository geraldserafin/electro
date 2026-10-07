"""What a kind is, read off its laws alone."""

from electro import Current, Voltage
from electro_notebook.kinds import is_source, reading, stores


def test_what_a_kind_is_follows_from_its_laws():
    from electro.elements import ALL
    from electro.elements import BY_KIND as BY_NAME

    sources = {k.kind for k in ALL if len(k.terminals) == 2 and is_source(k())}
    assert sources == {"voltage_source", "current_source", "sine_source", "square_source"}
    assert {k.kind: reading(k()) for k in ALL if reading(k())} == {
        "wire": Current,
        "ammeter": Current,
        "open": Voltage,
        "voltmeter": Voltage,
    }
    assert stores(BY_NAME["capacitor"]()) and stores(BY_NAME["inductor"]()) and (not stores(BY_NAME["resistor"]()))
