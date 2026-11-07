# KiCad project (rev C)

Open `rpn-calculator.kicad_pro` in KiCad (8 or later). The schematic is the whole circuit on one A1 portrait sheet, in the same arrangement as the Full Schematic doc, with every connection drawn as a wire. A dot marks a join; wires that cross without a dot are not connected.

| File | What |
|---|---|
| `rpn-calculator.kicad_sch` | Schematic, one sheet |
| `rpn-calculator.kicad_sym` | The project's symbols (library `rpn`, loaded through `sym-lib-table`) |
| `netlist.py` | Parts, values, footprints and every connection (the spec's rev C netlist) |
| `generate_schematic.py` | Draws the schematic and checks the drawing against `netlist.py` |
| `check_schematic.py` | Reads the saved file on its own and checks it again: every net complete, no extra joins, no unconnected pins, junction dots where wires join |

Net names: the rails (VBUS, 3V3_USB, VDD, VDDA, CELL, 5V_DISP, 3V3_DISP), ROW1–6, COL1–4 and the USB lines carry labels; other nets get KiCad's automatic names.

U4 (USBLC6-2SC6) is drawn flow-through, as in the doc: pins 1 and 6 (and 3 and 4) are joined inside the chip (datasheet functional diagram), so the connector side of the USB lines is its own net, USB_CONN_DP and USB_CONN_DM.

Until PCB layout starts, change the circuit in `netlist.py` / `generate_schematic.py` and re-run both scripts. Once layout has started, edit in KiCad instead, since re-running would overwrite hand edits.

## Footprints
Assigned from KiCad's standard libraries: LQFP-64, SOT-23/-5/-6, 0805 and 1206 passives, the 1×6 header, Keystone 1058, GCT USB4085, Omron B3U-1000P, the 2.0 × 1.2 mm crystal, test pads and M2 holes. These names weren't checked against an installed KiCad, so the footprint assignment step may flag one.

Still to choose: J1 (Würth 687110183622), L1 (Würth 74404042047), SW1–SW22 (Kailh Choc V1, with or without hotswap sockets) and Y2. The Enter stabiliser has no circuit, so it goes straight on the PCB as a footprint.
