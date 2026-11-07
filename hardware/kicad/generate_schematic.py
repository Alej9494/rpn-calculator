#!/usr/bin/env python3
"""Generate the rev C KiCad schematic for the RPN calculator.

Writes, next to this script:
  rpn-calculator.kicad_pro   project file (KiCad fills in its defaults)
  rpn-calculator.kicad_sch   the whole circuit on one sheet
  rpn-calculator.kicad_sym   the project's own symbol library
  sym-lib-table              points KiCad at that library

The circuit is the spec's rev C netlist. Every pin gets a short wire and a
net label (or a no-connect flag), so the netlist is exact; the drawing with
every connection as a wire is the Full Schematic doc.

Run:  python3 generate_schematic.py
"""
import os
import uuid as _uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = "rpn-calculator"
LIB = "rpn"
G = 2.54                     # grid
_NS = _uuid.UUID("6f1c6c1e-6b8e-4c43-9a8e-7a1b0c2d3e4f")


def uid(*key):
    """Stable UUIDs, so re-running the script gives the same file."""
    return str(_uuid.uuid5(_NS, "/".join(str(k) for k in key)))


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def f(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


FONT = "(effects (font (size 1.27 1.27)))"
FONT_HIDE = "(effects (font (size 1.27 1.27)) hide)"

# ---------------------------------------------------------------------------
# Symbols
#   box symbols: left and right pin lists of (number, name, type); None = gap
#   two-pin symbols: drawn horizontally, pin 1 left, pin 2 right
# ---------------------------------------------------------------------------
SYMBOLS = {}


def box(name, ref, left, right, width=15.24, desc=""):
    SYMBOLS[name] = dict(kind="box", ref=ref, left=left, right=right,
                         width=width, desc=desc)


def two(name, ref, shape, n1="1", n2="2", desc=""):
    SYMBOLS[name] = dict(kind="two", ref=ref, shape=shape, n=(n1, n2),
                         desc=desc)


P, PI, PO, BI, IN, OUT, NC = ("passive", "power_in", "power_out",
                              "bidirectional", "input", "output", "no_connect")

# STM32L476RGT6, LQFP-64 (pin numbers from the datasheet's pin table)
U1_LEFT = [
    ("1", "VBAT", PI), ("19", "VDD", PI), ("32", "VDD", PI), ("64", "VDD", PI),
    ("13", "VDDA/VREF+", PI), ("48", "VDDUSB", PI), None,
    ("7", "NRST", BI), ("60", "BOOT0", IN), None,
    ("3", "PC14-OSC32_IN", BI), ("4", "PC15-OSC32_OUT", BI),
    ("5", "PH0-OSC_IN", BI), ("6", "PH1-OSC_OUT", BI), None,
    ("46", "PA13/SWDIO", BI), ("49", "PA14/SWCLK", BI), None,
    ("42", "PA9/VBUS_SENSE", BI), ("44", "PA11/USB_DM", BI),
    ("45", "PA12/USB_DP", BI), None,
    ("43", "PA10", BI), ("17", "PA3", BI), ("52", "PC11", BI), None,
    ("12", "VSSA/VREF-", PI), ("18", "VSS", PI), ("31", "VSS", PI),
    ("47", "VSS", PI), ("63", "VSS", PI),
]
U1_RIGHT = [
    ("21", "PA5/SPI1_SCK", BI), ("23", "PA7/SPI1_MOSI", BI),
    ("20", "PA4", BI), ("28", "PB2/LPTIM1_OUT", BI), ("27", "PB1", BI),
    ("26", "PB0", BI), ("22", "PA6", BI), None,
    ("37", "PC6", BI), ("38", "PC7", BI), ("39", "PC8", BI), ("40", "PC9", BI),
    ("51", "PC10", BI), ("53", "PC12", BI), None,
    ("8", "PC0", BI), ("9", "PC1", BI), ("10", "PC2", BI), ("11", "PC3", BI),
    None,
    ("2", "PC13", BI), ("14", "PA0", BI), ("15", "PA1", BI), ("16", "PA2", BI),
    ("24", "PC4", BI), ("25", "PC5", BI), ("41", "PA8", BI), ("50", "PA15", BI),
    ("29", "PB10", BI), ("30", "PB11", BI), ("33", "PB12", BI),
    ("34", "PB13", BI), ("35", "PB14", BI), ("36", "PB15", BI),
    ("55", "PB3", BI), ("56", "PB4", BI), ("57", "PB5", BI), ("58", "PB6", BI),
    ("59", "PB7", BI), ("61", "PB8", BI), ("62", "PB9", BI), ("54", "PD2", BI),
]
box("STM32L476RGTx", "U", U1_LEFT, U1_RIGHT, width=27.94,
    desc="STM32L476RG, LQFP-64")

box("MCP1640", "U", [("6", "VIN", PI), ("3", "EN", IN), ("2", "GND", PI)],
    [("1", "SW", P), ("5", "VOUT", PO), ("4", "VFB", IN)],
    desc="MCP1640 boost converter, SOT-23-6 (1 SW, 2 GND, 3 EN, 4 VFB, 5 VOUT, 6 VIN)")
box("MCP1700", "U", [("3", "VIN", PI), ("1", "GND", PI)],
    [("2", "VOUT", PO)], width=12.7,
    desc="MCP1700 LDO, SOT-23 (1 GND, 2 VOUT, 3 VIN)")
box("USBLC6-2SC6", "U",
    [("1", "I/O1", P), ("3", "I/O2", P), ("2", "GND", PI)],
    [("6", "I/O1", P), ("4", "I/O2", P), ("5", "VBUS", PI)], width=12.7,
    desc="USB ESD protection, SOT-23-6")
box("SN74LV1T34", "U", [("2", "A", IN), ("1", "NC", NC), ("3", "GND", PI)],
    [("4", "Y", OUT), ("5", "VCC", PI)], width=10.16,
    desc="Single buffer, SOT-23-5 (1 NC, 2 A, 3 GND, 4 Y, 5 VCC)")
box("DMG2305UX", "Q", [("1", "G", P)], [("2", "S", P), ("3", "D", P)],
    width=10.16, desc="P-channel MOSFET, SOT-23 (1 G, 2 S, 3 D)")
box("LS027B7DH01_FPC", "J",
    [("1", "SCLK", P), ("2", "SI", P), ("3", "SCS", P), ("4", "EXTCOMIN", P),
     ("5", "DISP", P)],
    [("6", "VDDA", P), ("7", "VDD", P), ("8", "EXTMODE", P), ("9", "VSS", P),
     ("10", "VSSA", P)], width=20.32,
    desc="10-pin 0.5 mm FPC connector for the LS027B7DH01 panel (panel pin order)")
box("USB_C_USB2", "J",
    [("A4", "VBUS", P), ("A9", "VBUS", P), ("B4", "VBUS", P), ("B9", "VBUS", P),
     None, ("A5", "CC1", P), ("B5", "CC2", P), None,
     ("A1", "GND", P), ("A12", "GND", P), ("B1", "GND", P), ("B12", "GND", P),
     ("S1", "SHIELD", P)],
    [("A6", "D+", P), ("B6", "D+", P), ("A7", "D-", P), ("B7", "D-", P), None,
     ("A8", "SBU1", P), ("B8", "SBU2", P)], width=15.24,
    desc="USB-C receptacle, USB 2.0, 16 pins")
box("SWD_1x6", "J",
    [("1", "VDD", P), ("2", "SWCLK", P), ("3", "GND", P), ("4", "SWDIO", P),
     ("5", "NRST", P), ("6", "SWO", P)], [], width=10.16,
    desc="SWD header, Nucleo ST-LINK CN4 order")
two("R", "R", "res", desc="Resistor")
two("C", "C", "cap", desc="Capacitor")
two("L", "L", "ind", desc="Inductor")
two("FB", "FB", "res", desc="Ferrite bead")
two("Crystal", "Y", "xtal", desc="Crystal")
two("SW_Push", "SW", "sw", desc="Push button / key switch")
two("Battery_Cell", "BT", "bat", desc="Coin cell holder, pin 1 +, pin 2 -")
SYMBOLS["TestPoint"] = dict(kind="one", ref="TP", desc="Test point")
SYMBOLS["MountingHole"] = dict(kind="none", ref="H", desc="M2 mounting hole")


def box_geom(s):
    rows = max(len(s["left"]), len(s["right"]))
    h = (rows - 1) * G
    top = h / 2
    w = s["width"]
    pins = []  # (number, name, type, x, y, angle)  lib coords, y up
    for side, lst in (("L", s["left"]), ("R", s["right"])):
        for i, p in enumerate(lst):
            if p is None:
                continue
            y = top - i * G
            if side == "L":
                pins.append((*p, -w / 2 - G, y, 0))
            else:
                pins.append((*p, w / 2 + G, y, 180))
    return pins, (-w / 2, top + G, w / 2, -top - G)


def sym_pins(name):
    s = SYMBOLS[name]
    if s["kind"] == "box":
        return box_geom(s)[0]
    if s["kind"] == "two":
        n1, n2 = s["n"]
        return [(n1, "~", P, -5.08, 0, 0), (n2, "~", P, 5.08, 0, 180)]
    if s["kind"] == "one":
        return [("1", "1", P, 0, 0, 90)]
    return []


def lib_symbol(name, prefix=LIB + ":"):
    s = SYMBOLS[name]
    out = [f"(symbol {q(prefix + name)}"]
    if s["kind"] in ("two", "one", "none"):
        out.append("(pin_numbers hide) (pin_names (offset 0) hide)")
    else:
        out.append("(pin_names (offset 1.016))")
    out.append("(exclude_from_sim no) (in_bom yes) (on_board yes)")
    out.append(f"(property \"Reference\" {q(s['ref'])} (at 0 0 0) {FONT})")
    out.append(f"(property \"Value\" {q(name)} (at 0 0 0) {FONT})")
    out.append(f"(property \"Footprint\" \"\" (at 0 0 0) {FONT_HIDE})")
    out.append(f"(property \"Datasheet\" \"\" (at 0 0 0) {FONT_HIDE})")
    out.append(f"(property \"Description\" {q(s['desc'])} (at 0 0 0) {FONT_HIDE})")
    gr = []
    stroke = "(stroke (width 0.254) (type default))"
    if s["kind"] == "box":
        _, (x1, y1, x2, y2) = box_geom(s)
        gr.append(f"(rectangle (start {f(x1)} {f(y1)}) (end {f(x2)} {f(y2)}) "
                  f"{stroke} (fill (type background)))")
    elif s["kind"] == "two":
        sh = s["shape"]

        def pl(*pts, fill="none"):
            xy = " ".join(f"(xy {f(a)} {f(b)})" for a, b in pts)
            return f"(polyline (pts {xy}) {stroke} (fill (type {fill})))"
        if sh == "res":
            gr.append("(rectangle (start -2.54 1.016) (end 2.54 -1.016) "
                      f"{stroke} (fill (type none)))")
        elif sh == "ind":
            gr.append("(rectangle (start -2.54 1.016) (end 2.54 -1.016) "
                      f"{stroke} (fill (type outline)))")
        elif sh == "cap":
            gr += [pl((-2.54, 0), (-0.508, 0)), pl((-0.508, 2.032), (-0.508, -2.032)),
                   pl((0.508, 2.032), (0.508, -2.032)), pl((0.508, 0), (2.54, 0))]
        elif sh == "xtal":
            gr += [pl((-2.54, 0), (-1.524, 0)), pl((-1.524, 1.778), (-1.524, -1.778)),
                   pl((1.524, 1.778), (1.524, -1.778)), pl((1.524, 0), (2.54, 0)),
                   "(rectangle (start -0.762 1.27) (end 0.762 -1.27) "
                   f"{stroke} (fill (type none)))"]
        elif sh == "sw":
            gr += [pl((-2.54, 0), (-1.524, 0)), pl((-1.27, 0.254), (1.524, 1.524)),
                   pl((1.524, 0), (2.54, 0)), pl((0, 1.016), (0, 2.032)),
                   pl((-1.27, 2.032), (1.27, 2.032))]
        elif sh == "bat":
            gr += [pl((-2.54, 0), (-0.508, 0)), pl((-0.508, 2.54), (-0.508, -2.54)),
                   pl((0.508, 1.27), (0.508, -1.27)), pl((0.508, 0), (2.54, 0)),
                   pl((-2.286, 1.778), (-1.27, 1.778)), pl((-1.778, 2.286), (-1.778, 1.27))]
    elif s["kind"] == "one":
        gr.append(f"(circle (center 0 3.302) (radius 0.762) {stroke} (fill (type none)))")
    elif s["kind"] == "none":
        gr.append(f"(circle (center 0 0) (radius 2.54) {stroke} (fill (type none)))")
    out.append(f"(symbol {q(name + '_0_1')} {' '.join(gr)})")
    pins = []
    for num, pname, ptype, x, y, ang in sym_pins(name):
        length = 2.54 if s["kind"] != "one" else 2.54
        pins.append(f"(pin {ptype} line (at {f(x)} {f(y)} {ang}) (length {length}) "
                    f"(name {q(pname)} {FONT}) (number {q(num)} {FONT}))")
    out.append(f"(symbol {q(name + '_1_1')} {' '.join(pins)})")
    out.append(")")
    return " ".join(out)


PWR_FLAG_LIB = (
    '(symbol "power:PWR_FLAG" (power) (pin_numbers hide) '
    '(pin_names (offset 0) hide) (exclude_from_sim no) (in_bom yes) (on_board yes) '
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

# ---------------------------------------------------------------------------
# Parts: ref -> (symbol, value, footprint, part number, dnp, {pin: net})
# Nets follow the spec's rev C netlist.
# ---------------------------------------------------------------------------
FP_R = "Resistor_SMD:R_0805_2012Metric"
FP_C = "Capacitor_SMD:C_0805_2012Metric"
PARTS = {}


def part(ref, sym, value, fp, mpn, nets, dnp=False):
    PARTS[ref] = dict(sym=sym, value=value, fp=fp, mpn=mpn, nets=nets, dnp=dnp)


def r(ref, value, a, b, mpn="", dnp=False):
    part(ref, "R", value, FP_R, mpn, {"1": a, "2": b}, dnp)


def c(ref, value, a, b="GND", mpn="", fp=FP_C, dnp=False):
    part(ref, "C", value, fp, mpn, {"1": a, "2": b}, dnp)


U1_NETS = {
    "1": "VDD", "19": "VDD", "32": "VDD", "64": "VDD", "13": "VDDA",
    "48": "3V3_USB", "12": "GND", "18": "GND", "31": "GND", "47": "GND",
    "63": "GND", "7": "NRST", "60": "BOOT0", "3": "LSE_IN", "4": "LSE_OUT",
    "5": "HSE_IN", "6": "HSE_OUT", "46": "SWDIO", "49": "SWCLK",
    "42": "VBUS_SENSE", "44": "USB_DM", "45": "USB_DP", "43": "BL_RX1",
    "17": "BL_RX2", "52": "BL_RX3", "21": "DISP_SCK", "23": "DISP_SI",
    "20": "DISP_SCS", "28": "DISP_EXTCOMIN", "27": "DISP_ON",
    "26": "DISP_PWR_EN", "37": "ROW1", "38": "ROW2", "39": "ROW3",
    "40": "ROW4", "51": "ROW5", "53": "ROW6", "8": "COL1", "9": "COL2",
    "10": "COL3", "11": "COL4",
}
part("U1", "STM32L476RGTx", "STM32L476RGT6", "Package_QFP:LQFP-64_10x10mm_P0.5mm",
     "STM32L476RGT6", U1_NETS)

# Power in, USB
part("J2", "USB_C_USB2", "USB4085-GF-A", "Connector_USB:USB_C_Receptacle_GCT_USB4085",
     "GCT USB4085-GF-A",
     {"A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS", "A5": "CC1",
      "B5": "CC2", "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
      "S1": "GND", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DM",
      "B7": "USB_DM"})          # A8, B8 (SBU) not connected
part("U4", "USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
     "USBLC6-2SC6", {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM",
                     "4": "USB_DM", "2": "GND", "5": "VBUS"})
r("R1", "5.1k", "CC1", "GND")
r("R2", "5.1k", "CC2", "GND")
r("R4", "100k", "VBUS", "VBUS_SENSE", "RC0805FR-07100KL")
r("R5", "100k", "VBUS_SENSE", "GND", "RC0805FR-07100KL")
part("U3", "MCP1700", "MCP1700T-3302E/TT", "Package_TO_SOT_SMD:SOT-23",
     "MCP1700T-3302E/TT", {"3": "VBUS", "1": "GND", "2": "3V3_USB"})
c("C4", "1uF", "VBUS", mpn="CL21B105KAFNNNE")
c("C5", "1uF", "3V3_USB", mpn="CL21B105KAFNNNE")
r("R9", "100k", "3V3_USB", "GND", "RC0805FR-07100KL")
part("Q1", "DMG2305UX", "DMG2305UX-13", "Package_TO_SOT_SMD:SOT-23",
     "DMG2305UX-13", {"1": "3V3_USB", "2": "VDD", "3": "CELL"})
part("Q2", "DMG2305UX", "DMG2305UX-13", "Package_TO_SOT_SMD:SOT-23",
     "DMG2305UX-13", {"1": "VDD", "2": "VDD", "3": "3V3_USB"})
part("BT1", "Battery_Cell", "CR2032 (Keystone 1058)",
     "Battery:BatteryHolder_Keystone_1058_1x2032", "Keystone 1058",
     {"1": "CELL", "2": "GND"})
c("C3", "10uF 25V", "VDD", mpn="C3216X5R1E106K160AB",
  fp="Capacitor_SMD:C_1206_3216Metric")

# MCU support
for ref in ("C8", "C9", "C10", "C11"):
    c(ref, "100nF", "VDD", mpn="CL21B104KBCNNNC")
c("C13", "100nF", "3V3_USB", mpn="CL21B104KBCNNNC")
part("FB1", "FB", "BLM21PG221SN1D", "Inductor_SMD:L_0805_2012Metric",
     "BLM21PG221SN1D", {"1": "VDD", "2": "VDDA"})
c("C14", "100nF", "VDDA", mpn="CL21B104KBCNNNC")
c("C15", "1uF", "VDDA", mpn="CL21B105KAFNNNE")
c("C18", "100nF", "NRST", mpn="CL21B104KBCNNNC")
part("SW24", "SW_Push", "Reset (B3U-1000P)", "Button_Switch_SMD:SW_SPST_B3U-1000P",
     "B3U-1000P", {"1": "NRST", "2": "GND"})
r("R3", "10k", "BOOT0", "GND", "RC0805FR-0710KL")
part("SW23", "SW_Push", "Recovery (B3U-1000P)", "Button_Switch_SMD:SW_SPST_B3U-1000P",
     "B3U-1000P", {"1": "BOOT0", "2": "VDD"})
part("Y1", "Crystal", "32.768kHz 4pF", "Crystal:Crystal_SMD_2012-2Pin_2.0x1.2mm",
     "CM8V-T1A-32.768KHZ-4PF-20PPM-TA-QC", {"1": "LSE_IN", "2": "LSE_OUT"})
c("C19", "3.9pF C0G", "LSE_IN")
c("C20", "3.9pF C0G", "LSE_OUT")
part("Y2", "Crystal", "8MHz (not fitted)", "", "", {"1": "HSE_IN", "2": "HSE_OUT"},
     dnp=True)
c("C16", "DNP", "HSE_IN", dnp=True)
c("C17", "DNP", "HSE_OUT", dnp=True)
part("J3", "SWD_1x6", "SWD", "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
     "", {"1": "VDD", "2": "SWCLK", "3": "GND", "4": "SWDIO", "5": "NRST"})
r("R10", "100k", "BL_RX1", "GND", "RC0805FR-07100KL")
r("R11", "100k", "BL_RX2", "GND", "RC0805FR-07100KL")
r("R12", "100k", "BL_RX3", "GND", "RC0805FR-07100KL")

# Display supply
part("U2", "MCP1640", "MCP1640T-I/CHY", "Package_TO_SOT_SMD:SOT-23-6",
     "MCP1640T-I/CHY", {"6": "VDD", "3": "DISP_PWR_EN", "2": "GND",
                        "1": "SW_BOOST", "5": "5V_DISP", "4": "FB_BOOST"})
part("L1", "L", "4.7uH", "", "Wurth 74404042047", {"1": "VDD", "2": "SW_BOOST"})
c("C6", "4.7uF", "VDD", mpn="CL21A475KAQNNNE")
c("C7", "22uF 16V", "5V_DISP", mpn="CL21A226MOQNNNE")
r("R6", "976k", "5V_DISP", "FB_BOOST", "RC0805FR-07976KL")
r("R7", "309k", "FB_BOOST", "GND", "RC0805FR-07309KL")
r("R8", "100k", "DISP_PWR_EN", "GND", "RC0805FR-07100KL")
part("U5", "MCP1700", "MCP1700T-3302E/TT", "Package_TO_SOT_SMD:SOT-23",
     "MCP1700T-3302E/TT", {"3": "5V_DISP", "1": "GND", "2": "3V3_DISP"})
c("C23", "1uF", "5V_DISP", mpn="CL21B105KAFNNNE")
c("C24", "1uF", "3V3_DISP", mpn="CL21B105KAFNNNE")

# Display buffers and panel
BUFS = [("U6", "DISP_SCK", "LCD_SCK", "C25"), ("U7", "DISP_SI", "LCD_SI", "C26"),
        ("U8", "DISP_SCS", "LCD_SCS", "C27"),
        ("U9", "DISP_EXTCOMIN", "LCD_EXTCOMIN", "C28"),
        ("U10", "DISP_ON", "LCD_DISP", "C29")]
for u, a, y, cap in BUFS:
    part(u, "SN74LV1T34", "SN74LV1T34DBVR", "Package_TO_SOT_SMD:SOT-23-5",
         "SN74LV1T34DBVR", {"2": a, "3": "GND", "4": y, "5": "3V3_DISP"})
    c(cap, "100nF", "3V3_DISP", mpn="CL21B104KBCNNNC")
part("J1", "LS027B7DH01_FPC", "LS027B7DH01 panel", "", "Wurth 687110183622",
     {"1": "LCD_SCK", "2": "LCD_SI", "3": "LCD_SCS", "4": "LCD_EXTCOMIN",
      "5": "LCD_DISP", "6": "5V_DISP", "7": "5V_DISP", "8": "5V_DISP",
      "9": "GND", "10": "GND"})
c("C21", "1uF", "5V_DISP", mpn="CL21B105KAFNNNE")
c("C22", "1uF", "5V_DISP", mpn="CL21B105KAFNNNE")

# Keypad: same order as KEY_LABEL in the firmware, row by row
KEYS = ["CLEAR", "DROP", "SWAP", "SQRT", "7", "8", "9", "/", "4", "5", "6", "*",
        "1", "2", "3", "-", "0", ".", "+/-", "+", None, "ENTER", None, "BACK"]
KEYPOS = {}
n = 0
for i, k in enumerate(KEYS):
    if k is None:
        continue
    n += 1
    row, col = i // 4 + 1, i % 4 + 1
    ref = f"SW{n}"
    KEYPOS[ref] = (row, col)
    part(ref, "SW_Push", k, "", "Kailh Choc V1", {"1": f"ROW{row}", "2": f"COL{col}"})

# Test points and mounting holes (from the spec's PCB section)
for i, net in enumerate(["VDD", "3V3_USB", "5V_DISP", "3V3_DISP", "GND"], 1):
    part(f"TP{i}", "TestPoint", net, "TestPoint:TestPoint_Pad_D1.5mm", "", {"1": net})
for i in range(1, 7):
    part(f"H{i}", "MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", "", {})

# Power nets that only passive parts drive need a PWR_FLAG for ERC
FLAGS = ["VDD", "GND", "VBUS", "VDDA", "CELL"]

# ---------------------------------------------------------------------------
# Layout (schematic coordinates, mm, y down). Columns of stacked parts.
# ---------------------------------------------------------------------------
LAYOUT = []        # (heading, x, y, [refs])
LAYOUT.append(("USB-C and power path", 45.72, 38.1,
               ["J2", "U4", "R1", "R2", "R4", "R5", "U3", "C4", "C5", "R9",
                "Q1", "Q2", "BT1", "C3"]))
LAYOUT.append(("MCU support", 132.08, 38.1,
               ["C8", "C9", "C10", "C11", "C13", "FB1", "C14", "C15", "C18",
                "SW24", "R3", "SW23", "Y1", "C19", "C20", "Y2", "C16", "C17",
                "J3", "R10", "R11", "R12"]))
LAYOUT.append(("Microcontroller", 233.68, 50.8, ["U1"]))
LAYOUT.append(("Display supply", 335.28, 38.1,
               ["U2", "L1", "C6", "C7", "R6", "R7", "R8", "U5", "C23", "C24"]))
LAYOUT.append(("Display buffers and panel", 419.1, 38.1,
               ["U6", "C25", "U7", "C26", "U8", "C27", "U9", "C28", "U10", "C29",
                "J1", "C21", "C22"]))
LAYOUT.append(("Test points", 335.28, 228.6, ["TP1", "TP2", "TP3", "TP4", "TP5"]))
LAYOUT.append(("Mounting holes (M2)", 233.68, 228.6,
               ["H1", "H2", "H3", "H4", "H5", "H6"]))
KEYPAD_ORIGIN = (482.6, 58.42)   # keypad drawn as its own grid
FLAGS_ORIGIN = (233.68, 190.5)


def snap(v):
    return round(v / 1.27) * 1.27


def sym_extent(sym):
    pins = sym_pins(sym)
    s = SYMBOLS[sym]
    if s["kind"] == "box":
        return box_geom(s)[1]
    if s["kind"] == "two":
        return (-5.08, 2.54, 5.08, -2.54)
    if s["kind"] == "one":
        return (-1.27, 5.08, 1.27, 0)
    return (-2.54, 2.54, 2.54, -2.54)


POS = {}
for heading, x, y, refs in LAYOUT:
    cy = y + 7.62
    for ref in refs:
        sym = PARTS[ref]["sym"]
        x1, y1, x2, y2 = sym_extent(sym)
        cy += y1 + 2.54          # top edge clearance (y1 is the top, lib y-up)
        if SYMBOLS[sym]["kind"] == "one":
            cy += 2.54
        POS[ref] = (snap(x), snap(cy))
        cy += -y2 + 7.62 if SYMBOLS[sym]["kind"] != "two" else 5.08 + 2.54
        if SYMBOLS[sym]["kind"] == "box":
            cy += 2.54
for k, ref in enumerate(KEYPOS):        # two columns of 11 keys
    x0, y0 = KEYPAD_ORIGIN
    POS[ref] = (snap(x0 + (k // 11) * 45.72), snap(y0 + (k % 11) * 10.16))


# ---------------------------------------------------------------------------
# Emit schematic
# ---------------------------------------------------------------------------
ROOT = uid("root")
items = []
labels_at = []           # for the checker: (name, x, y)


def wire(x1, y1, x2, y2):
    items.append(f"(wire (pts (xy {f(x1)} {f(y1)}) (xy {f(x2)} {f(y2)})) "
                 f"(stroke (width 0) (type default)) (uuid {q(uid('w', x1, y1, x2, y2))}))")


def label(name, x, y, ang):
    just = {0: "left bottom", 180: "right bottom", 90: "left bottom",
            270: "right bottom"}[ang]
    items.append(f"(label {q(name)} (at {f(x)} {f(y)} {ang}) (fields_autoplaced yes) "
                 f"(effects (font (size 1.27 1.27)) (justify {just})) "
                 f"(uuid {q(uid('l', name, x, y))}))")
    labels_at.append((name, x, y))


def text(s, x, y, size=2.54, bold=True):
    b = " bold" if bold else ""
    items.append(f"(text {q(s)} (exclude_from_sim no) (at {f(x)} {f(y)} 0) "
                 f"(effects (font (size {size} {size}){b}) (justify left bottom)) "
                 f"(uuid {q(uid('t', s, x, y))}))")


def prop(name, value, x, y, hide=False, just=None):
    j = f" (justify {just})" if just else ""
    h = " hide" if hide else ""
    return (f"(property {q(name)} {q(value)} (at {f(x)} {f(y)} 0) "
            f"(effects (font (size 1.27 1.27)){j}{h}))")


def place(ref):
    p = PARTS[ref]
    sym = p["sym"]
    s = SYMBOLS[sym]
    X, Y = POS[ref]
    x1, y1, x2, y2 = sym_extent(sym)
    if s["kind"] == "box":
        rx, ry, vx, vy, just = X + x1, Y - y1 - 1.27, X + x1, Y - y2 + 2.54, "left"
    elif s["kind"] == "two":
        rx, ry, vx, vy, just = X, Y - 3.81, X, Y + 3.81, None
    elif s["kind"] == "one":
        rx, ry, vx, vy, just = X + 2.54, Y - 4.445, X + 2.54, Y - 2.54, "left"
    else:
        rx, ry, vx, vy, just = X + 3.81, Y - 1.27, X + 3.81, Y + 1.27, "left"
    props = [prop("Reference", ref, rx, ry, just=just),
             prop("Value", p["value"], vx, vy, just=just),
             prop("Footprint", p["fp"], X, Y, hide=True),
             prop("Datasheet", "", X, Y, hide=True),
             prop("Description", s["desc"], X, Y, hide=True)]
    if p["mpn"]:
        props.append(prop("MPN", p["mpn"], X, Y, hide=True))
    pins_u = " ".join(f"(pin {q(num)} (uuid {q(uid('p', ref, num))}))"
                      for num, *_ in sym_pins(sym))
    dnp = "yes" if p["dnp"] else "no"
    in_bom = "no" if s["kind"] == "none" or sym == "TestPoint" else "yes"
    items.append(
        f"(symbol (lib_id {q(LIB + ':' + sym)}) (at {f(X)} {f(Y)} 0) (unit 1) "
        f"(exclude_from_sim no) (in_bom {in_bom}) (on_board yes) (dnp {dnp}) "
        f"(fields_autoplaced yes) (uuid {q(uid('s', ref))}) {' '.join(props)} {pins_u} "
        f"(instances (project {q(PROJECT)} (path {q('/' + ROOT)} "
        f"(reference {q(ref)}) (unit 1)))))")
    # stubs and labels
    for num, pname, ptype, px, py, ang in sym_pins(sym):
        ax, ay = X + px, Y - py
        net = p["nets"].get(num)
        if net is None:
            items.append(f"(no_connect (at {f(ax)} {f(ay)}) (uuid {q(uid('nc', ref, num))}))")
            continue
        if ang == 0:        # pin on the left, points right into the body
            bx, by, la = ax - 2.54, ay, 180
        elif ang == 180:
            bx, by, la = ax + 2.54, ay, 0
        elif ang == 90:     # pin at bottom pointing up (test point)
            bx, by, la = ax, ay + 2.54, 270
        else:
            bx, by, la = ax, ay - 2.54, 90
        wire(ax, ay, bx, by)
        label(net, bx, by, la)


for heading, x, y, refs in LAYOUT:
    text(heading, x - 20.32, y)
    for ref in refs:
        place(ref)
text("Keypad: 6 rows x 4 columns, no diodes", KEYPAD_ORIGIN[0] - 20.32,
     KEYPAD_ORIGIN[1] - 12.7)
text("SW1-SW22 in firmware KEY_LABEL order; R6C1 and R6C3 empty (3u Enter on R6C2)",
     KEYPAD_ORIGIN[0] - 20.32, KEYPAD_ORIGIN[1] - 7.62, size=1.27, bold=False)
for ref in KEYPOS:
    place(ref)

# PWR_FLAGs
text("Power flags (ERC only)", FLAGS_ORIGIN[0] - 20.32, FLAGS_ORIGIN[1])
for i, net in enumerate(FLAGS):
    X, Y = snap(FLAGS_ORIGIN[0] + i * 12.7), snap(FLAGS_ORIGIN[1] + 12.7)
    items.append(
        f"(symbol (lib_id \"power:PWR_FLAG\") (at {f(X)} {f(Y)} 0) (unit 1) "
        f"(exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
        f"(uuid {q(uid('flag', net))}) "
        f"{prop('Reference', f'#FLG0{i + 1}', X, Y - 1.905, hide=True)} "
        f"{prop('Value', 'PWR_FLAG', X, Y - 3.81)} "
        f"{prop('Footprint', '', X, Y, hide=True)} "
        f"{prop('Datasheet', '~', X, Y, hide=True)} "
        f"{prop('Description', '', X, Y, hide=True)} "
        f"(pin \"1\" (uuid {q(uid('flagpin', net))})) "
        f"(instances (project {q(PROJECT)} (path {q('/' + ROOT)} "
        f"(reference \"#FLG0{i + 1}\") (unit 1)))))")
    wire(X, Y, X, Y + 2.54)
    label(net, X, Y + 2.54, 270)

NOTES = [
    "RPN calculator rev C. Generated from the spec netlist by generate_schematic.py; edit the script, not this file, until layout starts.",
    "Every pin has a wire stub and a net label: pins with the same label are connected.",
    "The drawing with every connection as a wire is the Full Schematic doc.",
    "Unused MCU pins carry no-connect flags; firmware sets them to analog. J2 A8/B8 (SBU) not connected.",
    "Y2, C16, C17: footprint only, not fitted (DNP).",
    "Footprints still to choose: J1 (Wurth 687110183622), L1 (Wurth 74404042047), SW1-SW22 (Kailh Choc V1), Y2.",
]
for i, s in enumerate(NOTES):
    text(s, 25.4, 375.92 + i * 3.81, size=1.524, bold=False)

lib_syms = [lib_symbol(n) for n in SYMBOLS] + [PWR_FLAG_LIB]
sch = (
    f"(kicad_sch (version 20231120) (generator \"eeschema\") (generator_version \"8.0\") "
    f"(uuid {q(ROOT)}) (paper \"A2\") "
    f"(title_block (title \"RPN Calculator\") (date \"2026-11-07\") (rev \"C\") "
    f"(comment 1 \"Whole circuit on one sheet\") (comment 2 \"From the spec's rev C netlist\")) "
    f"(lib_symbols {' '.join(lib_syms)}) "
    f"{' '.join(items)} "
    f"(sheet_instances (path \"/\" (page \"1\"))))"
)


def pretty(s):
    """Indent the s-expression one list per line, KiCad style."""
    out, depth, i, n = [], 0, 0, len(s)
    buf = ""
    in_str = False
    while i < n:
        ch = s[i]
        if in_str:
            buf += ch
            if ch == "\\":
                buf += s[i + 1]
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            buf += ch
        elif ch == "(":
            if buf.strip():
                out.append("\t" * depth + buf.strip())
            buf = "("
            depth += 1
        elif ch == ")":
            depth -= 1
            buf += ")"
            out.append("\t" * depth + buf.strip())
            buf = ""
        elif ch == " " and buf == "":
            pass
        else:
            buf += ch
        i += 1
    # join short closing lines back onto their parents for readability
    lines, res = out, []
    for ln in lines:
        if ln.strip() == ")" and res:
            res[-1] += ")"
        else:
            res.append(ln)
    return "\n".join(res) + "\n"


def write(name, content):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as fh:
        fh.write(content)


write(f"{PROJECT}.kicad_sch", sch + "\n")
lib = ("(kicad_symbol_lib (version 20231120) (generator \"rpn_generate\") "
       "(generator_version \"8.0\") "
       + " ".join(lib_symbol(n, prefix="") for n in SYMBOLS) + ")\n")
write(f"{PROJECT}.kicad_sym", lib)
write("sym-lib-table",
      "(sym_lib_table\n  (version 7)\n"
      f"  (lib (name \"{LIB}\")(type \"KiCad\")(uri \"${{KIPRJMOD}}/{PROJECT}.kicad_sym\")"
      "(options \"\")(descr \"RPN calculator symbols\"))\n)\n")
write(f"{PROJECT}.kicad_pro",
      '{\n  "meta": {\n    "filename": "%s.kicad_pro",\n    "version": 1\n  },\n'
      '  "sheets": [\n    [\n      "%s",\n      "Root"\n    ]\n  ]\n}\n' % (PROJECT, ROOT))

if __name__ == "__main__":
    print(f"{len(PARTS)} parts, {len(set(n for p in PARTS.values() for n in p['nets'].values()))} nets")
