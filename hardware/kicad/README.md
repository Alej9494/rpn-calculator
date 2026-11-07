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
Most come from KiCad's standard libraries. The project's own library, `rpn.pretty` (loaded through `fp-lib-table`), adds:

| Footprint | For | Source |
|---|---|---|
| `SW_Kailh_Choc_V1_1.00u` | SW1–SW22 | [kiswitch](https://github.com/kiswitch/kiswitch) keyswitch library, CC-BY-SA 4.0 with an exception for designs made with it; unchanged |
| `Wurth_687110183622_1x10-1MP_P0.50mm_Horizontal` | J1 | Drawn from the recommended land pattern in `docs/datasheets/Wurth-687110183622-FPC-connector.pdf` (rev 001.008): ten 0.3 x 1.0 mm pads at 0.5 mm pitch, two 1.65 x 1.30 mm tabs (pad "MP", no net) 1.45 mm out from pins 1 and 10 and 0.75 mm below the pad row. The cable enters from the body side. |

Y2 uses KiCad's 3.2 x 2.5 mm four-pad crystal footprint: pads 1 and 3 are the crystal, 2 and 4 the case, tied to GND.

Still to do: L1 (Wurth 74404042047, WE-LQS 4018) needs the land pattern from Wurth's datasheet. The Enter key uses the 1u footprint at R6C2; the stabiliser has no circuit, so its holes go straight on the PCB, checked against the stabiliser you bought.
