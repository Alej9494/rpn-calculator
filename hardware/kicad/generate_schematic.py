#!/usr/bin/env python3
"""Generate the rev C KiCad schematic for the RPN calculator, fully wired.

The drawing follows the Full Schematic doc: the same arrangement, scaled to
an A1 portrait sheet, with every connection drawn as a wire and a ground
symbol wherever the doc draws one. Parts, values, footprints and the
reference netlist are in netlist.py; after drawing, this script rebuilds
the connectivity from its own geometry and stops if it differs from that
netlist.

Writes rpn-calculator.kicad_sch, .kicad_sym, .kicad_pro and sym-lib-table.
Run:  python3 generate_schematic.py
"""
import os
import sys
import uuid as _uuid
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from netlist import PARTS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "rpn-calculator"
LIB = "rpn"
G = 2.54
SCALE, OFFSET = 0.45, 12.7      # doc units -> mm
_NS = _uuid.UUID("6f1c6c1e-6b8e-4c43-9a8e-7a1b0c2d3e4f")


def uid(*key):
    return str(_uuid.uuid5(_NS, "/".join(str(k) for k in key)))


def snap(v):
    return round(round(v / 1.27) * 1.27, 2)


def T(v):
    """Doc coordinate -> mm on the 1.27 mm grid."""
    return snap(v * SCALE + OFFSET)


def d(x, y):
    return (T(x), T(y))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


FONT = "(effects (font (size 1.27 1.27)))"
FONT_HIDE = "(effects (font (size 1.27 1.27)) hide)"
STROKE = "(stroke (width 0.254) (type default))"

# ---------------------------------------------------------------------------
# Library symbols. Pins: (number, name, type, x, y, angle, length), lib coords
# (y up). The pin's (x, y) is its connection end.
# ---------------------------------------------------------------------------
P_, PI, PO, BI, IN, OUT, NC = ("passive", "power_in", "power_out",
                               "bidirectional", "input", "output", "no_connect")
LIBSYM = {}       # name -> dict(pins, graphics, ref, desc, show_names, show_numbers, power)


def libsym(name, ref, pins, graphics, desc="", names=True, numbers=True, power=False):
    LIBSYM[name] = dict(ref=ref, pins=pins, gr=graphics, desc=desc, names=names,
                        numbers=numbers, power=power)


def pl(*pts, fill="none", w=0.254):
    xy = " ".join(f"(xy {f(a)} {f(b)})" for a, b in pts)
    return f"(polyline (pts {xy}) (stroke (width {w}) (type default)) (fill (type {fill})))"


def rect(x1, y1, x2, y2, fill="none"):
    return f"(rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) {STROKE} (fill (type {fill})))"


def circ(x, y, r, fill="none"):
    return f"(circle (center {f(x)} {f(y)}) (radius {f(r)}) {STROKE} (fill (type {fill})))"


# Two-pin parts, vertical (pin 1 top) and horizontal (pin 1 left)
def two_pin(name, ref, half, body_v, desc):
    libsym(name + "_V", ref, [("1", "~", P_, 0, half, 270, half - body_v[1]),
                              ("2", "~", P_, 0, -half, 90, half - body_v[1])],
           body_v[0](), desc, names=False, numbers=False)
    libsym(name + "_H", ref, [("1", "~", P_, -half, 0, 0, half - body_v[1]),
                              ("2", "~", P_, half, 0, 180, half - body_v[1])],
           [g.replace("@", "") for g in body_v[2]()], desc, names=False, numbers=False)


def swap_xy(gs):
    """Rotate vertical graphics a quarter turn for the horizontal version."""
    out = []
    for g in gs:
        out.append(g)
    return out


two_pin("R", "R", 5.08, (lambda: [rect(-1.016, 2.54, 1.016, -2.54)], 2.54,
                         lambda: [rect(-2.54, 1.016, 2.54, -1.016)]), "Resistor")
two_pin("FB", "FB", 5.08, (lambda: [rect(-1.016, 2.54, 1.016, -2.54, "outline")], 2.54,
                           lambda: [rect(-2.54, 1.016, 2.54, -1.016, "outline")]), "Ferrite bead")
two_pin("C", "C", 3.81, (lambda: [pl((-2.032, 0.508), (2.032, 0.508), w=0.508),
                                  pl((-2.032, -0.508), (2.032, -0.508), w=0.508)], 0.508,
                         lambda: [pl((-0.508, 2.032), (-0.508, -2.032), w=0.508),
                                  pl((0.508, 2.032), (0.508, -2.032), w=0.508)]), "Capacitor")


def coil_v():
    a = []
    for i in range(4):
        y0 = 2.54 - i * 1.27
        a.append(f"(arc (start 0 {f(y0)}) (mid 0.635 {f(y0 - 0.635)}) (end 0 {f(y0 - 1.27)}) "
                 f"{STROKE} (fill (type none)))")
    return a


def coil_h():
    a = []
    for i in range(4):
        x0 = -2.54 + i * 1.27
        a.append(f"(arc (start {f(x0)} 0) (mid {f(x0 + 0.635)} 0.635) (end {f(x0 + 1.27)} 0) "
                 f"{STROKE} (fill (type none)))")
    return a


two_pin("L", "L", 5.08, (coil_v, 2.54, coil_h), "Inductor")
two_pin("Y", "Y", 5.08, (lambda: [pl((-2.032, 1.524), (2.032, 1.524), w=0.508),
                                  rect(-1.524, 0.762, 1.524, -0.762),
                                  pl((-2.032, -1.524), (2.032, -1.524), w=0.508)], 1.524,
                         lambda: [pl((-1.524, 2.032), (-1.524, -2.032), w=0.508),
                                  rect(-0.762, 1.524, 0.762, -1.524),
                                  pl((1.524, 2.032), (1.524, -2.032), w=0.508)]), "Crystal")
two_pin("SW", "SW", 5.08, (lambda: [circ(0, 2.032, 0.508), circ(0, -2.032, 0.508),
                                    pl((0.254, 1.778), (1.778, -1.778)),
                                    pl((1.016, 0), (2.54, 0)), pl((2.54, 1.27), (2.54, -1.27))],
                           2.54,
                           lambda: [circ(-2.032, 0, 0.508), circ(2.032, 0, 0.508),
                                    pl((-1.778, 0.254), (1.778, 1.778)),
                                    pl((0, 1.016), (0, 2.54)), pl((-1.27, 2.54), (1.27, 2.54))]),
        "Push button")
two_pin("BAT", "BT", 5.08, (lambda: [pl((-2.54, 0.762), (2.54, 0.762), w=0.254),
                                     pl((-1.27, -0.762), (1.27, -0.762), w=0.508),
                                     pl((1.016, 2.286), (2.032, 2.286)),
                                     pl((1.524, 2.794), (1.524, 1.778))], 0.762,
                            lambda: []), "Coin cell holder, pin 1 +")

libsym("Y4", "Y",
       [("1", "~", P_, 0, 5.08, 270, 3.556), ("3", "~", P_, 0, -5.08, 90, 3.556),
        ("2", "~", P_, 5.08, 0, 180, 3.302), ("4", "~", P_, -5.08, 0, 0, 3.302)],
       [pl((-2.032, 1.524), (2.032, 1.524), w=0.508), rect(-1.524, 0.762, 1.524, -0.762),
        pl((-2.032, -1.524), (2.032, -1.524), w=0.508)],
       "Crystal, four pads (1, 3 crystal; 2, 4 case)", names=False, numbers=True)

# Keyswitch: pin 1 comes down from the row, pin 2 goes right to the column
libsym("KEY", "SW",
       [("1", "~", P_, -5.08, 5.08, 270, 2.54), ("2", "~", P_, 5.08, 0, 180, 2.54)],
       [pl((-5.08, 2.54), (-5.08, 0.508)), circ(-5.08, 0, 0.508), circ(2.032, 0, 0.508),
        pl((-4.572, 0.381), (2.286, 1.905))],
       "Kailh Choc V1 key switch", names=False, numbers=False)

# P-channel MOSFET: G left, D top, S bottom
libsym("PMOS", "Q",
       [("1", "G", P_, -7.62, 0, 0, 2.54), ("3", "D", P_, 0, 7.62, 270, 5.588),
        ("2", "S", P_, 0, -7.62, 90, 5.588)],
       [circ(0, 0, 4.572), pl((-2.54, -1.778), (-2.54, 1.778)),
        pl((-1.524, 2.54), (-1.524, 1.524)), pl((-1.524, 0.508), (-1.524, -0.508)),
        pl((-1.524, -1.524), (-1.524, -2.54)),
        pl((-1.524, 2.032), (0, 2.032)), pl((-1.524, -2.032), (0, -2.032)),
        pl((-1.524, 0), (0, 0), (0, -2.032)),
        pl((-0.508, 0), (-1.016, 0.381), (-1.016, -0.381), (-0.508, 0), fill="outline"),
        pl((0, 2.032), (1.524, 2.032), (1.524, 0.508)),
        pl((0.889, 0.508), (2.159, 0.508)),
        pl((0.889, -0.508), (2.159, -0.508), (1.524, 0.508), (0.889, -0.508), fill="outline"),
        pl((1.524, -0.508), (1.524, -2.032), (0, -2.032))],
       "P-channel MOSFET, SOT-23 (1 G, 2 S, 3 D)", names=False)

# Single buffer: A left, Y right, VCC top, GND bottom, pin 1 NC
libsym("BUF", "U",
       [("2", "A", IN, -7.62, 0, 0, 2.54), ("4", "Y", OUT, 7.62, 0, 180, 2.54),
        ("5", "VCC", PI, 0, 5.08, 270, 3.175), ("3", "GND", PI, 0, -5.08, 90, 3.175),
        ("1", "NC", NC, -2.54, -5.08, 90, 2.54)],
       [pl((-5.08, 3.81), (5.08, 0), (-5.08, -3.81), (-5.08, 3.81), fill="background")],
       "Single buffer SN74LV1T34, SOT-23-5 (1 NC, 2 A, 3 GND, 4 Y, 5 VCC)", names=False)

libsym("TestPoint", "TP", [("1", "1", P_, 0, 0, 90, 1.27)], [circ(0, 2.032, 0.762)],
       "Test point", names=False, numbers=False)
libsym("MountingHole", "H", [], [circ(0, 0, 2.54), circ(0, 0, 1.27)], "M2 mounting hole")

# ---------------------------------------------------------------------------
# Drawing state
# ---------------------------------------------------------------------------
PLACED = []        # dict(ref, lib, X, Y, rot, fields)
WIRES = []         # ((x1,y1),(x2,y2))
NCS = []           # points
LABELS = []        # (name, x, y, angle)
TEXTS = []         # (text, x, y, size, bold)
POWER = []         # (kind, x, y)  kind GND or PWR_FLAG
PINPOS = {}        # (ref, num) -> (x, y)


def pin_xy(X, Y, rot, px, py):
    return (round(X + px, 2), round(Y - py, 2)) if rot == 0 else (round(X - px, 2), round(Y + py, 2))


def place(ref, lib, X, Y, rot=0, fields=None):
    X, Y = round(X, 2), round(Y, 2)
    PLACED.append(dict(ref=ref, lib=lib, X=X, Y=Y, rot=rot, fields=fields or {}))
    for num, _n, _t, px, py, _a, _l in LIBSYM[lib]["pins"]:
        PINPOS[(ref, num)] = pin_xy(X, Y, rot, px, py)


def P(ref, num):
    return PINPOS[(ref, num)]


def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        a, b = (round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))
        if a == b:
            continue
        assert a[0] == b[0] or a[1] == b[1], f"diagonal wire {a} {b}"
        WIRES.append((a, b))


def gnd(pt):
    POWER.append(("GND", round(pt[0], 2), round(pt[1], 2)))


def flag(pt):
    POWER.append(("PWR_FLAG", round(pt[0], 2), round(pt[1], 2)))


def nc(pt):
    NCS.append(pt)


def label(name, pt, angle=0):
    LABELS.append((name, pt[0], pt[1], angle))


def text(s, pt, size=1.27, bold=False):
    TEXTS.append((s, pt[0], pt[1], size, bold))


def two(ref, kind, a, b, fields=None):
    """Two-pin part between points a (pin 1 end) and b (pin 2 end), with wires."""
    vertical = a[0] == b[0]
    assert vertical or a[1] == b[1]
    lib = kind + ("_V" if vertical else "_H")
    half = LIBSYM[lib]["pins"][0][3 if not vertical else 4]
    half = abs(half)
    i = 1 if vertical else 0
    lo, hi = sorted((a[i], b[i]))
    assert hi - lo >= 2 * half - 0.01, f"{ref}: no room ({hi - lo:.2f} mm)"
    c = snap((lo + hi) / 2)
    first = a[i] < b[i]           # pin 1 at the top / left
    rot = 0 if first else 180
    X, Y = (a[0], c) if vertical else (c, a[1])
    if fields is None:
        fields = ({"Reference": (2.54, -1.27, "left"), "Value": (2.54, 1.27, "left")}
                  if vertical else
                  {"Reference": (0, -2.54, None), "Value": (0, 2.54, None)})
    place(ref, lib, X, Y, rot, fields)
    wire(a, P(ref, "1"))
    wire(P(ref, "2"), b)


def capdown(ref, pt):
    two(ref, "C", pt, (pt[0], pt[1] + 10.16))
    gnd((pt[0], pt[1] + 10.16))


def resdown(ref, pt):
    two(ref, "R", pt, (pt[0], pt[1] + 12.7))
    gnd((pt[0], pt[1] + 12.7))


def box(ref, lib, desc, drect, pins, fields):
    """Box symbol from a doc rectangle. pins: (side, doc_pos | ('mm', v), [(num, name, type)...]);
    a group of several pins is stacked at 2.54 mm and joined by a wire."""
    x1, y1, x2, y2 = T(drect[0]), T(drect[1]), T(drect[2]), T(drect[3])
    X, Y = snap((x1 + x2) / 2), snap((y1 + y2) / 2)
    lp = []
    for side, pos, group in pins:
        base = pos[1] if isinstance(pos, tuple) else T(pos)
        ends = []
        for k, (num, name, typ) in enumerate(group):
            v = round(base + k * G, 2)
            ex, ey, ang = {"L": (x1, v, 0), "R": (x2, v, 180),
                           "T": (v, y1, 270), "B": (v, y2, 90)}[side]
            lp.append((num, name.replace(" ", "/"), typ, round(ex - X, 2), round(Y - ey, 2), ang, 2.54))
            ends.append((ex, ey))
        if len(ends) > 1:
            wire(ends[0], ends[-1])
    body = rect(x1 + G - X, Y - (y1 + G), x2 - G - X, Y - (y2 - G), "background")
    libsym(lib, ref.rstrip("0123456789"), lp, [body], desc)
    place(ref, lib, X, Y, 0, fields)
    return (x1, y1, x2, y2)


# Field placements are offsets from the symbol origin: (dx, dy, justify)
def box_fields(rect_mm, X, Y, where="above"):
    x1, y1, x2, y2 = rect_mm
    if where == "above":
        return {"Reference": (x1 - X, y1 - 3.81 - Y, "left"), "Value": (x1 - X, y1 - 1.27 - Y, "left")}
    return {"Reference": (x1 - X, y2 + 2.54 - Y, "left"), "Value": (x1 - X, y2 + 5.08 - Y, "left")}


def fields_for(drect, where="above"):
    x1, y1, x2, y2 = T(drect[0]), T(drect[1]), T(drect[2]), T(drect[3])
    X, Y = snap((x1 + x2) / 2), snap((y1 + y2) / 2)
    return box_fields((x1, y1, x2, y2), X, Y, where)


# ---------------------------------------------------------------------------
# The circuit, following the Full Schematic doc (doc coordinates via d()/T())
# ---------------------------------------------------------------------------
# U1 -------------------------------------------------------------------------
U1R = (490, 512, 730, 1150)
UNUSED = [("2", "PC13"), ("14", "PA0"), ("15", "PA1"), ("16", "PA2"), ("22", "PA6"),
          ("24", "PC4"), ("25", "PC5"), ("41", "PA8"), ("50", "PA15"), ("29", "PB10"),
          ("30", "PB11"), ("33", "PB12"), ("34", "PB13"), ("35", "PB14"), ("36", "PB15"),
          ("55", "PB3"), ("56", "PB4"), ("57", "PB5"), ("58", "PB6"), ("59", "PB7"),
          ("61", "PB8"), ("62", "PB9"), ("54", "PD2")]
u1_pins = [
    ("L", 540, [("42", "PA9 VBUS_SENSE", BI)]),
    ("L", 564, [("19", "VDD", PI), ("32", "VDD", PI), ("64", "VDD", PI)]),
    ("L", 588, [("1", "VBAT", PI)]),
    ("L", 612, [("13", "VDDA/VREF+", PI)]),
    ("L", 636, [("12", "VSSA/VREF-", PI)]),
    ("L", 660, [("18", "VSS", PI), ("31", "VSS", PI), ("47", "VSS", PI), ("63", "VSS", PI)]),
    ("L", 684, [("46", "PA13 SWDIO", BI)]),
    ("L", 708, [("49", "PA14 SWCLK", BI)]),
    ("L", 732, [("7", "NRST", BI)]),
    ("L", 780, [("60", "BOOT0", IN)]),
    ("L", 804, [("5", "PH0 OSC_IN", BI)]),
    ("L", 828, [("6", "PH1 OSC_OUT", BI)]),
    ("L", 852, [("3", "PC14 OSC32_IN", BI)]),
    ("L", 876, [("4", "PC15 OSC32_OUT", BI)]),
    ("L", 924, [("45", "PA12 USB_DP", BI)]),
    ("L", 948, [("44", "PA11 USB_DM", BI)]),
    ("L", 972, [("43", "PA10", BI)]),
    ("L", 996, [("17", "PA3", BI)]),
    ("L", 1020, [("52", "PC11", BI)]),
    ("R", 540, [("48", "VDDUSB", PI)]),
    ("R", 564, [("26", "PB0 boost EN", BI)]),
    ("R", 640, [("21", "PA5 SPI1_SCK", BI)]),
    ("R", 680, [("23", "PA7 SPI1_MOSI", BI)]),
    ("R", 720, [("20", "PA4 LCD_CS", BI)]),
    ("R", 760, [("28", "PB2 LPTIM1_OUT", BI)]),
    ("R", 800, [("27", "PB1 LCD_DISP", BI)]),
    ("R", 860, [("11", "PC3 COL4", BI)]),
    ("R", 880, [("10", "PC2 COL3", BI)]),
    ("R", 900, [("9", "PC1 COL2", BI)]),
    ("R", 920, [("8", "PC0 COL1", BI)]),
    ("R", 960, [("37", "PC6 ROW1", BI)]),
    ("R", 980, [("38", "PC7 ROW2", BI)]),
    ("R", 1000, [("39", "PC8 ROW3", BI)]),
    ("R", 1020, [("40", "PC9 ROW4", BI)]),
    ("R", 1040, [("51", "PC10 ROW5", BI)]),
    ("R", 1060, [("53", "PC12 ROW6", BI)]),
    ("B", ("mm", T(520)), [(n, nm, BI) for n, nm in UNUSED]),
]
box("U1", "STM32L476RGTx", "STM32L476RG, LQFP-64", U1R, u1_pins, fields_for(U1R))
WIRES[:] = [w for w in WIRES if not (w[0][1] == T(1150) and w[1][1] == T(1150))]  # no join on NC pins
for n, _ in UNUSED:
    nc(P("U1", n))

# VBUS rail -------------------------------------------------------------------
U3R = (520, 86, 610, 136)
box("U3", "MCP1700_U3", "MCP1700 LDO, SOT-23 (1 GND, 2 VOUT, 3 VIN)", U3R,
    [("L", 110, [("3", "VIN", PI)]), ("R", 110, [("2", "VOUT", PO)]),
     ("B", 565, [("1", "GND", PI)])], fields_for(U3R))
gnd(P("U3", "1"))
wire(d(20, 110), P("U3", "3"))
label("VBUS", d(150, 110))
flag(d(50, 110))
capdown("C4", d(80, 110))
two("R4", "R", d(410, 110), d(410, 160), {"Reference": (-2.54, -1.27, "right"), "Value": (-2.54, 1.27, "right")})
two("R5", "R", d(410, 160), d(410, 206), {"Reference": (-2.54, -1.27, "right"), "Value": (-2.54, 1.27, "right")})
gnd(d(410, 206))
wire(d(410, 160), d(480, 160), (T(480), P("U1", "42")[1]), P("U1", "42"))

# J2 USB-C and U4 ----------------------------------------------------------
J2R = (40, 906, 130, 1056)
box("J2", "USB_C_USB4085", "USB-C receptacle, USB 2.0, 16 pins", J2R,
    [("L", 930, [("A4", "VBUS", P_), ("A9", "VBUS", P_), ("B4", "VBUS", P_), ("B9", "VBUS", P_)]),
     ("R", 924, [("A6", "D+", P_), ("B6", "D+", P_)]),
     ("R", 948, [("A7", "D-", P_), ("B7", "D-", P_)]),
     ("R", 980, [("A5", "CC1", P_)]), ("R", 1004, [("B5", "CC2", P_)]),
     ("R", 1028, [("A8", "SBU1", P_)]), ("R", ("mm", T(1028) + G), [("B8", "SBU2", P_)]),
     ("B", ("mm", T(66)), [("A1", "GND", P_), ("A12", "GND", P_), ("B1", "GND", P_),
                           ("B12", "GND", P_), ("S1", "SHIELD", P_)])],
    fields_for(J2R))
WIRES[:] = [w for w in WIRES if w != (P("J2", "A8"), P("J2", "B8"))]
nc(P("J2", "A8")); nc(P("J2", "B8"))
gnd(P("J2", "A1"))
wire(P("J2", "A4"), (T(20), P("J2", "A4")[1]), d(20, 110))

U4R = (220, 906, 320, 966)
box("U4", "USBLC6-2SC6", "USB ESD protection, SOT-23-6", U4R,
    [("L", 924, [("1", "I/O1", P_)]), ("L", 948, [("3", "I/O2", P_)]),
     ("R", 924, [("6", "I/O1", P_)]), ("R", 948, [("4", "I/O2", P_)]),
     ("T", 270, [("5", "VBUS", PI)]), ("B", 270, [("2", "GND", PI)])],
    fields_for(U4R, "below"))
gnd(P("U4", "2"))
wire(P("U4", "5"), (P("U4", "5")[0], T(898)), (T(20), T(898)))
wire(P("J2", "A6"), P("U4", "1"))
wire(P("J2", "A7"), P("U4", "3"))
label("USB_CONN_DP", (P("J2", "A6")[0] + 3.81, P("J2", "A6")[1]))
label("USB_CONN_DM", (P("J2", "A7")[0] + 3.81, P("J2", "A7")[1]))
label("USB_DP", (P("U4", "6")[0] + 3.81, P("U4", "6")[1]))
label("USB_DM", (P("U4", "4")[0] + 3.81, P("U4", "4")[1]))
wire(P("U4", "6"), P("U1", "45"))
wire(P("U4", "4"), P("U1", "44"))
two("R1", "R", P("J2", "A5"), d(194, 980))
gnd(d(194, 980))
two("R2", "R", P("J2", "B5"), d(194, 1004))
gnd(d(194, 1004))

# 3V3_USB, Q1, Q2, coin cell ---------------------------------------------------
place("Q2", "PMOS", T(750), T(180), 0,
      {"Reference": (T(712) - T(750), -1.27, "right"), "Value": (T(712) - T(750), 1.27, "right")})
place("Q1", "PMOS", T(860), T(200), 0,
      {"Reference": (6.35, 3.81, "left"), "Value": (6.35, 6.35, "left")})
wire(P("U3", "2"), d(830, 110), d(830, 200), P("Q1", "1"))
label("3V3_USB", d(700, 110))
capdown("C5", d(640, 110))
resdown("R9", d(690, 110))
wire(d(750, 110), P("Q2", "3"))
g2 = P("Q2", "1")
wire(g2, (T(724), g2[1]), d(724, 208), d(750, 208))
wire(P("Q2", "2"), d(750, 300))
wire(d(780, 110), d(780, 540), P("U1", "48"))
wire(d(780, 460), d(752, 460))
capdown("C13", d(752, 460))
place("TP2", "TestPoint", T(738), T(110), 0, {"Reference": (1.27, -4.445, "left"), "Value": (1.27, -2.54, "left")})
wire(P("Q1", "3"), (T(860), T(170)), d(900, 170))
two("BT1", "BAT", d(900, 170), d(900, 214),
    {"Reference": (3.81, -1.27, "left"), "Value": (3.81, 1.27, "left")})
gnd(d(900, 214))
wire(P("Q1", "2"), d(860, 300))
label("CELL", (T(866), T(170)))

# VDD rail ----------------------------------------------------------------------
wire(d(40, 300), d(940, 300), d(940, 350))
label("VDD", d(500, 300))
flag(d(60, 300))
place("TP1", "TestPoint", T(620), T(300), 0, {"Reference": (1.27, -4.445, "left"), "Value": (1.27, -2.54, "left")})
for ref, x in (("C8", 200), ("C9", 240), ("C10", 280), ("C11", 320)):
    capdown(ref, d(x, 300))
capdown("C3", d(830, 300))
capdown("C6", d(920, 300))
wire(d(465, 300), (T(465), P("U1", "1")[1]), P("U1", "1"))
wire((T(465), P("U1", "19")[1]), P("U1", "19"))
two("FB1", "FB", d(440, 300), d(440, 500),
    {"Reference": (-2.54, -1.27, "right"), "Value": (-2.54, 1.27, "right")})
wire(d(440, 500), (T(440), P("U1", "13")[1]), P("U1", "13"))
wire(d(440, 520), d(370, 520))
label("VDDA", d(440, 600), 90)
flag(d(420, 520))
capdown("C14", d(400, 520))
capdown("C15", d(370, 520))
gnd_vssa = (T(476), P("U1", "12")[1])
wire(P("U1", "12"), gnd_vssa); gnd(gnd_vssa)
gnd_vss = (T(476), P("U1", "18")[1])
wire(P("U1", "18"), gnd_vss); gnd(gnd_vss)

# J3 SWD, reset, BOOT0 ----------------------------------------------------------
J3R = (60, 662, 110, 770)
box("J3", "SWD_1x6", "SWD header, Nucleo ST-LINK CN4 order", J3R,
    [("L", 674, [("1", "VDD", P_)]), ("L", 730, [("6", "SWO", P_)]),
     ("R", 684, [("4", "SWDIO", P_)]), ("R", 708, [("2", "SWCLK", P_)]),
     ("R", 732, [("5", "NRST", P_)]), ("R", 756, [("3", "GND", P_)])],
    fields_for(J3R))
nc(P("J3", "6"))
wire(d(40, 300), d(40, 780))
wire((T(40), P("J3", "1")[1]), P("J3", "1"))
wire(P("J3", "4"), P("U1", "46"))
wire(P("J3", "2"), P("U1", "49"))
wire(P("J3", "5"), P("U1", "7"))
wire(P("J3", "3"), (T(124), P("J3", "3")[1])); gnd((T(124), P("J3", "3")[1]))
capdown("C18", (T(310), P("U1", "7")[1]))
two("SW24", "SW", (T(410), P("U1", "7")[1]), d(410, 762),
    {"Reference": (3.81, -1.27, "left"), "Value": (3.81, 1.27, "left")})
gnd(d(410, 762))
two("SW23", "SW", d(110, 780), d(40, 780),
    {"Reference": (0, 3.81, None), "Value": (0, 6.35, None)})
wire(d(110, 780), P("U1", "60"))
resdown("R3", d(128, 780))
PARTS["SW23"]["value"] = "Recovery"
PARTS["SW24"]["value"] = "Reset"

# Crystals ------------------------------------------------------------------------
for xt, ca, cb, pa, pb in (("Y2", "C16", "C17", "5", "6"), ("Y1", "C19", "C20", "3", "4")):
    ya, yb = P("U1", pa)[1], P("U1", pb)[1]
    wire(P("U1", pa), (T(280), ya))
    wire(P("U1", pb), (T(280), yb))
    two(ca, "C", (T(280), ya), (T(236), ya), {"Reference": (0, -2.54, None), "Value": (0, 2.54, None)})
    gnd((T(236), ya))
    two(cb, "C", (T(280), yb), (T(236), yb), {"Reference": (0, -2.54, None), "Value": (0, 2.54, None)})
    gnd((T(236), yb))
    if xt == "Y2":   # 3225 four-pad crystal: 1 and 3 crystal, 2 and 4 case to GND
        c = snap((ya + yb) / 2)
        place(xt, "Y4", T(304), c, 0,
              {"Reference": (6.35, -1.27, "left"), "Value": (6.35, 1.27, "left")})
        wire((T(304), ya), P(xt, "1"))
        wire(P(xt, "3"), (T(304), yb))
        gnd(P(xt, "2")); gnd(P(xt, "4"))
    else:
        two(xt, "Y", (T(304), ya), (T(304), yb),
            {"Reference": (3.81, -1.27, "left"), "Value": (3.81, 1.27, "left")})

# Bootloader receive pins ----------------------------------------------------------
for r, pin in (("R10", "43"), ("R11", "17"), ("R12", "52")):
    y = P("U1", pin)[1]
    two(r, "R", P("U1", pin), (T(404), y), {"Reference": (0, -2.54, None), "Value": (0, 2.54, None)})
    gnd((T(404), y))

# Boost U2 ---------------------------------------------------------------------------
U2R = (960, 330, 1050, 430)
box("U2", "MCP1640", "MCP1640 boost converter, SOT-23-6", U2R,
    [("L", 350, [("6", "VIN", PI)]), ("L", 380, [("1", "SW", P_)]), ("L", 410, [("3", "EN", IN)]),
     ("R", 350, [("5", "VOUT", PO)]), ("R", 394, [("4", "VFB", IN)]),
     ("B", 1005, [("2", "GND", PI)])], fields_for(U2R))
gnd(P("U2", "2"))
wire(d(940, 350), P("U2", "6"))
two("L1", "L", d(940, 350), (T(940), P("U2", "1")[1]),
    {"Reference": (-2.54, -1.27, "right"), "Value": (-2.54, 1.27, "right")})
wire((T(940), P("U2", "1")[1]), P("U2", "1"))
en = P("U1", "26")
wire(en, (T(860), en[1]), (T(860), P("U2", "3")[1]), P("U2", "3"))
resdown("R8", (T(910), P("U2", "3")[1]))

# 5V_DISP -------------------------------------------------------------------------------
J1R = (1180, 560, 1250, 830)
box("J1", "LS027B7DH01_FPC", "FPC connector for the LS027B7DH01 panel (panel pin order)", J1R,
    [("T", 1200, [("6", "VDDA", P_)]), ("T", 1220, [("7", "VDD", P_)]), ("T", 1240, [("8", "EXTMODE", P_)]),
     ("L", 640, [("1", "SCLK", P_)]), ("L", 680, [("2", "SI", P_)]), ("L", 720, [("3", "SCS", P_)]),
     ("L", 760, [("4", "EXTCOMIN", P_)]), ("L", 800, [("5", "DISP", P_)]),
     ("B", 1200, [("9", "VSS", P_)]), ("B", 1230, [("10", "VSSA", P_)])],
    {"Reference": (T(1180) - snap((T(1180) + T(1250)) / 2), T(830) + 7.62 - snap((T(560) + T(830)) / 2), "left"),
     "Value": (T(1180) - snap((T(1180) + T(1250)) / 2), T(830) + 10.16 - snap((T(560) + T(830)) / 2), "left")})
gnd(P("J1", "9")); gnd(P("J1", "10"))
rail5 = P("U2", "5")[1]
wire(P("U2", "5"), (T(1240), rail5), P("J1", "8"))
wire((P("J1", "6")[0], rail5), P("J1", "6"))
wire((P("J1", "7")[0], rail5), P("J1", "7"))
label("5V_DISP", (T(1074), rail5))
two("R6", "R", (T(1070), rail5), (T(1070), P("U2", "4")[1]),
    {"Reference": (2.54, -1.27, "left"), "Value": (2.54, 1.27, "left")})
wire((T(1070), P("U2", "4")[1]), P("U2", "4"))
two("R7", "R", (T(1070), P("U2", "4")[1]), d(1070, 440),
    {"Reference": (2.54, -1.27, "left"), "Value": (2.54, 1.27, "left")})
gnd(d(1070, 440))
capdown("C7", (T(1105), rail5))
place("TP3", "TestPoint", T(1120), rail5, 0, {"Reference": (1.27, -4.445, "left"), "Value": (1.27, -2.54, "left")})
capdown("C21", (T(1137), rail5))
capdown("C22", (T(1182), rail5))

U5R = (1060, 480, 1170, 520)
box("U5", "MCP1700_U5", "MCP1700 LDO, SOT-23 (1 GND, 2 VOUT, 3 VIN)", U5R,
    [("T", 1158, [("3", "VIN", PI)]), ("L", 500, [("2", "VOUT", PO)]), ("B", 1115, [("1", "GND", PI)])],
    fields_for(U5R, "below"))
gnd(P("U5", "1"))
wire((P("U5", "3")[0], rail5), P("U5", "3"))
wire(d(1158, 420), d(1135, 420))
capdown("C23", d(1135, 420))

# 3V3_DISP and the buffers ------------------------------------------------------------
r3 = P("U5", "2")[1]
wire(P("U5", "2"), (T(880), r3), d(880, 782))
label("3V3_DISP", d(880, 604), 90)
for ref, x in (("C24", 1045), ("C25", 1020), ("C26", 995), ("C27", 970), ("C28", 945), ("C29", 920)):
    capdown(ref, (T(x), r3))
place("TP4", "TestPoint", T(898), r3, 0, {"Reference": (1.27, -4.445, "left"), "Value": (1.27, -2.54, "left")})
BUFS = [("U6", "21", 640, "1"), ("U7", "23", 680, "2"), ("U8", "20", 720, "3"),
        ("U9", "28", 760, "4"), ("U10", "27", 800, "5")]
for u, mpin, y, jpin in BUFS:
    X, Y = T(900) + 7.62, T(y)
    place(u, "BUF", X, Y, 0, {"Reference": (3.81, -2.54, "left"), "Value": (7.62, 3.81, "left")})
    wire(P("U1", mpin), P(u, "2"))
    tap = T(y - 18)
    wire((T(880), tap), (X, tap), P(u, "5"))
    gnd(P(u, "3"))
    wire(P(u, "4"), P("J1", jpin))

# Keypad -------------------------------------------------------------------------------
COLS = [("COL4", "11", 860, 1180), ("COL3", "10", 880, 1080), ("COL2", "9", 900, 980), ("COL1", "8", 920, 880)]
ROWS = [("ROW1", "37", 960, 820, 1120), ("ROW2", "38", 980, 810, 1180), ("ROW3", "39", 1000, 800, 1240),
        ("ROW4", "40", 1020, 790, 1300), ("ROW5", "51", 1040, 780, 1360), ("ROW6", "53", 1060, 770, 1420)]
colx = {"COL1": 880, "COL2": 980, "COL3": 1080, "COL4": 1180}
rowy = {f"ROW{i + 1}": r[4] for i, r in enumerate(ROWS)}
keys = {}
for ref, p in PARTS.items():
    if p["sym"] == "SW_Push" and ref not in ("SW23", "SW24"):
        keys[ref] = (p["nets"]["1"], p["nets"]["2"])
for ref, (row, col) in keys.items():
    Xc, Yr = T(colx[col]), T(rowy[row])
    place(ref, "KEY", Xc - 5.08, Yr + 5.08, 0,
          {"Reference": (-6.35, 3.81, "left"), "Value": (-6.35, 6.35, "left")})
for name, pin, y, x in COLS:
    last = max((P(r, "2") for r, (_, c) in keys.items() if c == name), key=lambda p: p[1])
    wire(P("U1", pin), d(x, y), last)
    label(name, (T(742), T(y)))
for name, pin, y, xv, yr in ROWS:
    last = max((P(r, "1") for r, (rw, _) in keys.items() if rw == name), key=lambda p: p[0])
    wire(P("U1", pin), d(xv, y), d(xv, yr), last)
    label(name, (T(xv) + 2.54, T(yr)))

# Ground flag, GND test point, mounting holes ---------------------------------------------
flag(d(520, 1270))
wire(d(520, 1270), d(600, 1270))
place("TP5", "TestPoint", T(560), T(1270), 0, {"Reference": (1.27, -4.445, "left"), "Value": (1.27, -2.54, "left")})
gnd(d(600, 1270))
for i in range(6):
    place(f"H{i + 1}", "MountingHole", T(520 + i * 40), T(1370), 0,
          {"Reference": (-2.54, 5.08, "left"), "Value": (-2.54, 7.62, "left")})

# Notes ------------------------------------------------------------------------------------
text("RPN calculator, rev C: the whole circuit on one sheet", d(24, 28), 2.54, True)
text("Same arrangement as the Full Schematic doc. A dot marks a join; wires that cross without a dot are not connected.", d(24, 50))
text("Generated by generate_schematic.py from netlist.py; once PCB layout starts, edit in KiCad instead.", d(24, 64))
text("Q2: gate and source to VDD; only its body diode conducts, feeding VDD from USB", d(560, 236))
text("Q1: on unless USB is in; never charges the cell", d(890, 252))
text("R6 976k / R7 309k set 5.0 V", d(1080, 456))
text("U6-U10 SN74LV1T34: 3.3 V buffers to the panel", d(940, 598))
text("R10-R12 hold the bootloader's unused inputs low", d(300, 1060))
text("Y2, C16, C17: footprint only, not fitted", d(320, 790))
text("Keypad: 22 Kailh Choc V1, no diodes. R6C1 and R6C3 empty (3u Enter)", d(500, 1200), 1.27, True)
text("Unused MCU pins: no-connect; firmware sets them to analog", d(500, 1180))


# ---------------------------------------------------------------------------
# Tidy the wiring: split wires at every point where something connects, add
# junction dots, then rebuild the connectivity and compare with netlist.py.
# ---------------------------------------------------------------------------
def power_pins():
    return [(k, (x, y)) for k, x, y in POWER]


def tidy():
    special = set()
    for a, b in WIRES:
        special.add(a); special.add(b)
    special |= set(PINPOS.values())
    special |= {(x, y) for _, x, y, _ in LABELS}
    special |= {pt for _, pt in power_pins()}
    out = set()
    for a, b in WIRES:
        if a[0] == b[0]:
            lo, hi = sorted((a[1], b[1]))
            cuts = sorted({lo, hi} | {p[1] for p in special if p[0] == a[0] and lo < p[1] < hi})
            segs = [((a[0], u), (a[0], v)) for u, v in zip(cuts, cuts[1:])]
        else:
            lo, hi = sorted((a[0], b[0]))
            cuts = sorted({lo, hi} | {p[0] for p in special if p[1] == a[1] and lo < p[0] < hi})
            segs = [((u, a[1]), (v, a[1])) for u, v in zip(cuts, cuts[1:])]
        for s in segs:
            out.add(tuple(sorted(s)))
    return sorted(out)


SEGS = tidy()


def connectivity():
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for a, b in SEGS:
        union(("pt", a), ("pt", b))
    for (ref, num), pt in PINPOS.items():
        union(("pin", ref, num), ("pt", pt))
    for kind, pt in power_pins():
        if kind == "GND":
            union(("net", "GND"), ("pt", pt))
        else:
            find(("pt", pt))
    for name, x, y, _ in LABELS:
        union(("net", name), ("pt", (x, y)))
    return find


def verify():
    find = connectivity()
    errors = []
    ends = defaultdict(int)
    for a, b in SEGS:
        ends[a] += 1; ends[b] += 1
    pin_at = defaultdict(list)
    for k, pt in PINPOS.items():
        pin_at[pt].append(k)
    for pt, ks in pin_at.items():
        if len(ks) > 1:
            errors.append(f"pins on top of each other: {ks}")
    # every pin connected, flagged NC, or of type no_connect
    ptype = {}
    for pl_ in PLACED:
        for num, _n, typ, *_ in LIBSYM[pl_["lib"]]["pins"]:
            ptype[(pl_["ref"], num)] = typ
    attached = set(ends) | {pt for _, pt in power_pins()}
    ncs = set(NCS)
    for k, pt in PINPOS.items():
        if pt in ncs:
            if pt in attached:
                errors.append(f"no-connect on a connected pin {k}")
        elif pt not in attached and ptype[k] != NC and len(pin_at[pt]) == 1:
            errors.append(f"unconnected pin {k}")
    for pt, n in ends.items():
        if n == 1 and pt not in pin_at and pt not in {(x, y) for _, x, y, _ in LABELS} \
                and pt not in {p for _, p in power_pins()}:
            errors.append(f"dangling wire end at {pt}")
    # compare with the netlist
    expect = defaultdict(set)
    for ref, p in PARTS.items():
        for num, net in p["nets"].items():
            expect[net].add((ref, num))
    group_of = {}
    for net, pins in expect.items():
        roots = {find(("pin", r, n)) for r, n in pins}
        if len(roots) != 1:
            errors.append(f"net {net} drawn in {len(roots)} pieces")
        for r in roots:
            if r in group_of and group_of[r] != net:
                errors.append(f"nets {group_of[r]} and {net} are joined")
            group_of[r] = net
        if find(("net", net)) != find(("pin", *sorted(pins)[0])) and (
                ("net", net) in [("net", n) for n, *_ in LABELS] or net == "GND"):
            errors.append(f"label {net} on the wrong net")
    for ref, p in PARTS.items():
        for num, *_ in LIBSYM[next(x["lib"] for x in PLACED if x["ref"] == ref)]["pins"]:
            if num not in p["nets"]:
                r = find(("pin", ref, num))
                if r in group_of:
                    errors.append(f"{ref}.{num} should be unconnected but is on {group_of[r]}")
    for name, *_ in LABELS:
        r = find(("net", name))
        if group_of.get(r) != name:
            errors.append(f"label {name} sits on net {group_of.get(r)}")
    return errors


# ---------------------------------------------------------------------------
# Write the files
# ---------------------------------------------------------------------------
def lib_text(name, prefix):
    s = LIBSYM[name]
    out = [f"(symbol {q(prefix + name)}"]
    if s["power"]:
        out.append("(power)")
    if not s["numbers"]:
        out.append("(pin_numbers hide)")
    out.append("(pin_names (offset 0.508)" + ("" if s["names"] else " hide") + ")")
    out.append("(exclude_from_sim no) (in_bom yes) (on_board yes)")
    out.append(f"(property \"Reference\" {q(s['ref'])} (at 0 0 0) {FONT})")
    out.append(f"(property \"Value\" {q(name)} (at 0 0 0) {FONT})")
    out.append(f"(property \"Footprint\" \"\" (at 0 0 0) {FONT_HIDE})")
    out.append(f"(property \"Datasheet\" \"\" (at 0 0 0) {FONT_HIDE})")
    out.append(f"(property \"Description\" {q(s['desc'])} (at 0 0 0) {FONT_HIDE})")
    out.append(f"(symbol {q(name + '_0_1')} {' '.join(s['gr'])})")
    pins = [f"(pin {t} line (at {f(x)} {f(y)} {a}) (length {f(ln)}) "
            f"(name {q(n)} {FONT}) (number {q(num)} {FONT}))"
            for num, n, t, x, y, a, ln in s["pins"]]
    out.append(f"(symbol {q(name + '_1_1')} {' '.join(pins)})")
    out.append(")")
    return " ".join(out)


GND_LIB = (
    '(symbol "power:GND" (power) (pin_numbers hide) (pin_names (offset 0) hide) '
    '(exclude_from_sim no) (in_bom yes) (on_board yes) '
    f'(property "Reference" "#PWR" (at 0 -6.35 0) {FONT_HIDE}) '
    f'(property "Value" "GND" (at 0 -3.81 0) {FONT}) '
    f'(property "Footprint" "" (at 0 0 0) {FONT_HIDE}) '
    f'(property "Datasheet" "" (at 0 0 0) {FONT_HIDE}) '
    f'(property "Description" "Power symbol creates a global label with name \\"GND\\" , ground" (at 0 0 0) {FONT_HIDE}) '
    '(symbol "GND_0_1" (polyline (pts (xy 0 0) (xy 0 -1.27) (xy 1.27 -1.27) (xy 0 -2.54) '
    '(xy -1.27 -1.27) (xy 0 -1.27)) (stroke (width 0) (type default)) (fill (type none)))) '
    '(symbol "GND_1_1" (pin power_in line (at 0 0 270) (length 0) hide '
    f'(name "GND" {FONT}) (number "1" {FONT}))))'
)
PWR_FLAG_LIB = (
    '(symbol "power:PWR_FLAG" (power) (pin_numbers hide) (pin_names (offset 0) hide) '
    '(exclude_from_sim no) (in_bom yes) (on_board yes) '
    f'(property "Reference" "#FLG" (at 0 1.905 0) {FONT_HIDE}) '
    f'(property "Value" "PWR_FLAG" (at 0 3.81 0) {FONT}) '
    f'(property "Footprint" "" (at 0 0 0) {FONT_HIDE}) '
    f'(property "Datasheet" "~" (at 0 0 0) {FONT_HIDE}) '
    f'(property "Description" "Special symbol for telling ERC where power comes from" (at 0 0 0) {FONT_HIDE}) '
    '(symbol "PWR_FLAG_0_0" (pin power_out line (at 0 0 90) (length 0) '
    f'(name "~" {FONT}) (number "1" {FONT}))) '
    '(symbol "PWR_FLAG_0_1" (polyline (pts (xy 0 0) (xy 0 1.27) (xy -1.016 1.905) '
    '(xy 0 2.54) (xy 1.016 1.905) (xy 0 1.27)) (stroke (width 0) (type default)) '
    '(fill (type none)))))'
)

ROOT = uid("root")


def prop(name, value, x, y, hide=False, just=None):
    j = f" (justify {just})" if just else ""
    h = " hide" if hide else ""
    return (f"(property {q(name)} {q(value)} (at {f(x)} {f(y)} 0) "
            f"(effects (font (size 1.27 1.27)){j}{h}))")


def inst(ref):
    return (f"(instances (project {q(PROJECT)} (path {q('/' + ROOT)} "
            f"(reference {q(ref)}) (unit 1))))")


def symbol_items():
    out = []
    for p in PLACED:
        ref, lib, X, Y, rot = p["ref"], p["lib"], p["X"], p["Y"], p["rot"]
        part_ = PARTS[ref]
        fl = p["fields"]
        props = []
        for key, val in (("Reference", ref), ("Value", part_["value"])):
            if key in fl:
                dx, dy, just = fl[key]
                props.append(prop(key, val, X + dx, Y + dy, just=just))
            else:
                props.append(prop(key, val, X, Y, hide=True))
        props += [prop("Footprint", part_["fp"], X, Y, hide=True),
                  prop("Datasheet", "", X, Y, hide=True),
                  prop("Description", LIBSYM[lib]["desc"], X, Y, hide=True)]
        if part_["mpn"]:
            props.append(prop("MPN", part_["mpn"], X, Y, hide=True))
        pins = " ".join(f"(pin {q(n)} (uuid {q(uid('p', ref, n))}))" for n, *_ in LIBSYM[lib]["pins"])
        in_bom = "no" if lib in ("TestPoint", "MountingHole") else "yes"
        out.append(f"(symbol (lib_id {q(LIB + ':' + lib)}) (at {f(X)} {f(Y)} {rot}) (unit 1) "
                   f"(exclude_from_sim no) (in_bom {in_bom}) (on_board yes) "
                   f"(dnp {'yes' if part_['dnp'] else 'no'}) (uuid {q(uid('s', ref))}) "
                   f"{' '.join(props)} {pins} {inst(ref)})")
    n_pwr = n_flg = 0
    for kind, x, y in POWER:
        if kind == "GND":
            n_pwr += 1
            ref, lid, val = f"#PWR{n_pwr:03d}", "power:GND", "GND"
            vprop = prop("Value", val, x, y + 3.81, hide=True)
        else:
            n_flg += 1
            ref, lid, val = f"#FLG{n_flg:02d}", "power:PWR_FLAG", "PWR_FLAG"
            vprop = prop("Value", val, x, y - 3.81)
        out.append(f"(symbol (lib_id {q(lid)}) (at {f(x)} {f(y)} 0) (unit 1) "
                   f"(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
                   f"(uuid {q(uid('pwr', ref))}) {prop('Reference', ref, x, y, hide=True)} {vprop} "
                   f"{prop('Footprint', '', x, y, hide=True)} {prop('Datasheet', '', x, y, hide=True)} "
                   f"{prop('Description', '', x, y, hide=True)} "
                   f"(pin \"1\" (uuid {q(uid('pwrpin', ref))})) {inst(ref)})")
    return out


def junctions():
    count = defaultdict(int)
    for a, b in SEGS:
        count[a] += 1; count[b] += 1
    for pt in PINPOS.values():
        if pt in count:
            count[pt] += 1
    for _, pt in power_pins():
        if pt in count:
            count[pt] += 1
    return sorted(p for p, n in count.items() if n >= 3)


def build():
    items = symbol_items()
    for a, b in SEGS:
        items.append(f"(wire (pts (xy {f(a[0])} {f(a[1])}) (xy {f(b[0])} {f(b[1])})) "
                     f"(stroke (width 0) (type default)) (uuid {q(uid('w', a, b))}))")
    for p in junctions():
        items.append(f"(junction (at {f(p[0])} {f(p[1])}) (diameter 0) (color 0 0 0 0) "
                     f"(uuid {q(uid('j', p))}))")
    for p in NCS:
        items.append(f"(no_connect (at {f(p[0])} {f(p[1])}) (uuid {q(uid('nc', p))}))")
    for name, x, y, a in LABELS:
        just = "left bottom"
        items.append(f"(label {q(name)} (at {f(x)} {f(y)} {a}) (fields_autoplaced yes) "
                     f"(effects (font (size 1.27 1.27)) (justify {just})) (uuid {q(uid('l', name, x, y))}))")
    for s, x, y, size, bold in TEXTS:
        b = " bold" if bold else ""
        items.append(f"(text {q(s)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
                     f"(effects (font (size {size} {size}){b}) (justify left bottom)) "
                     f"(uuid {q(uid('t', s))}))")
    libs = [lib_text(n, LIB + ":") for n in sorted(LIBSYM)] + [GND_LIB, PWR_FLAG_LIB]
    return (f"(kicad_sch (version 20231120) (generator \"eeschema\") (generator_version \"8.0\") "
            f"(uuid {q(ROOT)}) (paper \"A1\" portrait) "
            f"(title_block (title \"RPN Calculator\") (date \"2026-11-07\") (rev \"C\") "
            f"(comment 1 \"Whole circuit on one sheet, every connection wired\")) "
            f"(lib_symbols {' '.join(libs)}) {' '.join(items)} "
            f"(sheet_instances (path \"/\" (page \"1\"))))\n")


def write(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        fh.write(content)


if __name__ == "__main__":
    errs = verify()
    for e in errs:
        print("ERROR:", e)
    if errs:
        sys.exit(1)
    write(f"{PROJECT}.kicad_sch", build())
    write(f"{PROJECT}.kicad_sym", "(kicad_symbol_lib (version 20231120) (generator \"rpn_generate\") "
          "(generator_version \"8.0\") " + " ".join(lib_text(n, "") for n in sorted(LIBSYM)) + ")\n")
    write("sym-lib-table", "(sym_lib_table\n  (version 7)\n"
          f"  (lib (name \"{LIB}\")(type \"KiCad\")(uri \"${{KIPRJMOD}}/{PROJECT}.kicad_sym\")"
          "(options \"\")(descr \"RPN calculator symbols\"))\n)\n")
    write(f"{PROJECT}.kicad_pro",
          '{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 1\n  },\n'
          '  "sheets": [\n    [\n      "%s",\n      "Root"\n    ]\n  ]\n}\n' % (PROJECT, ROOT))
    print(f"OK: {len(PLACED)} parts, {len(SEGS)} wires, {len(junctions())} junctions, "
          f"{len(POWER)} power symbols, {len(NCS)} no-connects")
