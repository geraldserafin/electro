"""The kinds of element: each its terminals and its laws, nothing else."""

from .boards.arduino import Arduino
from .boards.pico import Pico
from .capacitor import Capacitor
from .chips.opamp_model import OpAmpModel
from .chips.timer555 import Timer555
from .controlled.cccs import CCCS
from .controlled.ccvs import CCVS
from .controlled.vccs import VCCS
from .controlled.vcvs import VCVS
from .diodes.diode import Diode
from .diodes.diode_drop import DiodeDrop
from .diodes.led import LED
from .diodes.rgb_led import RGBLED
from .diodes.seven_segment import SevenSegment
from .diodes.zener import Zener
from .ideal.ammeter import Ammeter
from .ideal.hole import Hole
from .ideal.norator import Norator
from .ideal.nullator import Nullator
from .ideal.opamp import OpAmp
from .ideal.open import Open
from .ideal.voltmeter import Voltmeter
from .ideal.wire import Wire
from .inductor import Inductor
from .loads.buzzer import Buzzer
from .loads.lamp import Lamp
from .loads.motor import Motor
from .loads.passive_buzzer import PassiveBuzzer
from .loads.relay import Relay
from .loads.servo import Servo
from .logic.and_gate import AND
from .logic.counter import Counter
from .logic.dff import DFlipFlop
from .logic.jkff import JKFlipFlop
from .logic.nand_gate import NAND
from .logic.nor_gate import NOR
from .logic.not_gate import NOT
from .logic.or_gate import OR
from .logic.xor_gate import XOR
from .magnetic.coupled import Coupled
from .magnetic.transformer import Transformer
from .modules.addresses import I2C_ADDRESSES
from .modules.ds1307 import DS1307
from .modules.ili9341 import ILI9341
from .modules.lcd1602 import LCD1602
from .modules.lcd1602_i2c import LCD1602I2C
from .modules.ssd1306 import SSD1306
from .modules.ultrasonic import Ultrasonic
from .resistor import Resistor
from .sensors.photoresistor import Photoresistor
from .sensors.thermistor import Thermistor
from .sources.current import CurrentSource
from .sources.sine import SineSource
from .sources.square import SquareSource
from .sources.voltage import VoltageSource
from .switches.button import Button
from .switches.potentiometer import Potentiometer
from .switches.switch import Switch
from .transistors.nmos import NMOS
from .transistors.npn import NPN
from .transistors.pmos import PMOS
from .transistors.pnp import PNP

ALL = (
    Arduino,
    Pico,
    Capacitor,
    OpAmpModel,
    Timer555,
    CCCS,
    CCVS,
    VCCS,
    VCVS,
    Diode,
    DiodeDrop,
    LED,
    RGBLED,
    SevenSegment,
    Zener,
    Ammeter,
    Hole,
    Norator,
    Nullator,
    OpAmp,
    Open,
    Voltmeter,
    Wire,
    Inductor,
    Buzzer,
    Lamp,
    Motor,
    PassiveBuzzer,
    Relay,
    Servo,
    AND,
    Counter,
    DFlipFlop,
    JKFlipFlop,
    NAND,
    NOR,
    NOT,
    OR,
    XOR,
    Coupled,
    Transformer,
    DS1307,
    ILI9341,
    LCD1602,
    LCD1602I2C,
    SSD1306,
    Ultrasonic,
    Resistor,
    Photoresistor,
    Thermistor,
    CurrentSource,
    SineSource,
    SquareSource,
    VoltageSource,
    Button,
    Potentiometer,
    Switch,
    NMOS,
    NPN,
    PMOS,
    PNP,
)
"""Every kind."""

BY_KIND = {k.kind: k for k in ALL}
"""Each kind by its name, as a drawing calls it."""

__all__ = [
    "ALL",
    "BY_KIND",
    "I2C_ADDRESSES",
    "AND",
    "Ammeter",
    "Arduino",
    "Button",
    "Buzzer",
    "CCCS",
    "CCVS",
    "Capacitor",
    "Counter",
    "Coupled",
    "CurrentSource",
    "DFlipFlop",
    "DS1307",
    "Diode",
    "DiodeDrop",
    "Hole",
    "ILI9341",
    "Inductor",
    "JKFlipFlop",
    "LCD1602",
    "LCD1602I2C",
    "LED",
    "Lamp",
    "Motor",
    "NAND",
    "NMOS",
    "NOR",
    "NOT",
    "NPN",
    "Norator",
    "Nullator",
    "OR",
    "OpAmp",
    "OpAmpModel",
    "Open",
    "PMOS",
    "PNP",
    "PassiveBuzzer",
    "Photoresistor",
    "Pico",
    "Potentiometer",
    "RGBLED",
    "Relay",
    "Resistor",
    "SSD1306",
    "Servo",
    "SevenSegment",
    "SineSource",
    "SquareSource",
    "Switch",
    "Thermistor",
    "Timer555",
    "Transformer",
    "Ultrasonic",
    "VCCS",
    "VCVS",
    "VoltageSource",
    "Voltmeter",
    "Wire",
    "XOR",
    "Zener",
]
