"""Parts and connections for the RPN calculator, rev C.

This is the reference netlist: it follows the spec's rev C netlist, and the
schematic generator checks its drawing against it. Each part:
ref -> sym (drawing style), value, fp (KiCad footprint), mpn, dnp, nets {pin: net}.
Pins not listed are not connected.
"""
PARTS = {}


def part(ref, sym, value, fp, mpn, nets, dnp=False):
    PARTS[ref] = dict(sym=sym, value=value, fp=fp, mpn=mpn, nets=nets, dnp=dnp)


FP_R = "Resistor_SMD:R_0805_2012Metric"
FP_C = "Capacitor_SMD:C_0805_2012Metric"



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
      "S1": "GND", "A6": "USB_CONN_DP", "B6": "USB_CONN_DP", "A7": "USB_CONN_DM",
      "B7": "USB_CONN_DM"})          # A8, B8 (SBU) not connected
part("U4", "USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
     "USBLC6-2SC6", {"1": "USB_CONN_DP", "6": "USB_DP", "3": "USB_CONN_DM",
                     "4": "USB_DM", "2": "GND", "5": "VBUS"})
# U4 is drawn flow-through: pins 1 and 6 (and 3 and 4) are joined inside the
# chip (datasheet functional diagram), so the connector side is its own net.
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
part("Y2", "Crystal", "8MHz (not fitted)", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm_HandSoldering", "",
     {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"},  # 3225: pads 1, 3 crystal; 2, 4 case
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
part("J1", "LS027B7DH01_FPC", "LS027B7DH01 panel", "rpn:Wurth_687110183622_1x10-1MP_P0.50mm_Horizontal", "Wurth 687110183622",
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
    part(ref, "SW_Push", k, "rpn:SW_Kailh_Choc_V1_1.00u", "Kailh Choc V1", {"1": f"ROW{row}", "2": f"COL{col}"})

# Test points and mounting holes (from the spec's PCB section)
for i, net in enumerate(["VDD", "3V3_USB", "5V_DISP", "3V3_DISP", "GND"], 1):
    part(f"TP{i}", "TestPoint", net, "TestPoint:TestPoint_Pad_D1.5mm", "", {"1": net})
for i in range(1, 7):
    part(f"H{i}", "MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", "", {})

