# RPN calculator — notes for Claude

Alex's personal project: a simple HP-style RPN calculator, as a phone web app and as hardware (STM32L476, Sharp Memory LCD, 22 Choc keys, CR2032). The two must behave identically. Alex hand-solders everything and reads schematics best as one single diagram.

## Live documents (open these, don't copy them)
- Hardware spec, rev C: https://claude.ai/artifact/BjSprbmsqPrHh3voA2DEm3
  Pin map, netlist, BOM, power path, test plan, and the "Still to check or do" list.
- Full Schematic, one sheet: https://claude.ai/artifact/QQxwgQhgPRL1rAU2wL2xc6
  The diagram the breakout prototype is wired from.
Read them with the Docs tools when a task touches the hardware. When a decision changes, update the spec, the Full Schematic, `hardware/` BOMs and `docs/DESIGN.md` together so they stay consistent.

## Where things are
| Path | What |
|---|---|
| `docs/DESIGN.md` | Requirements and behaviour decisions (short) |
| `docs/datasheets/` | Every component datasheet; check pinouts against these |
| `firmware/rpn_calculator/` | Arduino (STM32duino) sketch for the Nucleo L476RG; `bcd.*` is the 12-digit BCD maths, `tests/` runs it against Python's decimal |
| `hardware/` | BOM (text and Digi-Key CSV); KiCad files will go here |
| `webapp/` | Phone web app |
| `tests/` | Shared keystroke test vectors for web app and firmware |

## Decisions that are easy to get wrong
- Entry is HP 48 style: left-justified command line, ENTER pushes once and duplicates only when nothing is typed, 4 equal stack lines, unlimited stack. Only + − × ÷ and √x. 12 digits, BCD, ROUND_HALF_UP.
- No On/Off key: auto-off after 5 min, stack kept in RAM (Stop 2). Hold CLEAR 3 s to switch off; CLEAR acts on release. Stack is not saved to flash.
- Power: VDD is about 3.0 V from the CR2032 through Q1 (DMG2305UX P-MOSFET: S to VDD, D to BT1+, G to 3V3_USB, R9 100k pulls G low). USB-C powers the board only during updates: U3 MCP1700 makes 3V3_USB, which feeds VDDUSB and, through Q2 (second DMG2305UX used as its body diode: G and S to VDD, D to 3V3_USB), VDD at about 2.7 V. Q1 turns off then, so USB never charges the cell.
- Display: U2 MCP1640 boost makes 5V_DISP (R6 976k / R7 309k), U5 MCP1700 makes 3V3_DISP, U6–U10 SN74LV1T34 buffers lift the five panel signals to 3.3 V. EXTMODE to 5V_DISP. Panel LS027B7DH01 (zero-defect grade of LS027B7DH01A, same datasheet).
- Keypad: 6 rows × 4 columns, no diodes. ROW1–6 on PC6–PC10 and PC12 (ROW6 moved off PC11), COL1–4 on PC0–PC3. R10–R12 hold the bootloader's unused RX pins (PA10, PA3, PC11) low.
- Updates: hold SWAP while plugging in USB-C → system bootloader DFU. SW23 recovery button on BOOT0 through a 1 mm hole. Y1 32.768 kHz fitted (CM8V-T1A); Y2 8 MHz footprint left empty.
- Connectors: J1 Würth 687110183622 (top contact; the SMK part Sharp names is obsolete). J2 GCT USB4085-GF-A, fully through-hole. BT1 Keystone 1058.

## Status (Nov 2026)
Working on the Nucleo: display, keypad, BCD maths, sleep and auto-off. Next: full-circuit prototype on an LQFP-64 breakout with SOT-23 adapters and the perfboard keypad, wired from the Full Schematic. Then KiCad capture and the PCB. Open items are in the spec's "Still to check or do".

## Working with Alex
- Write in plain UK English; explain the reason behind a hardware choice briefly.
- Check part pinouts and limits against the datasheet in `docs/datasheets/` before stating them; say when something is unchecked.
- Datasheets Alex sends go into `docs/datasheets/` and its README table.
