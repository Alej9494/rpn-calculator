# KiCad project (rev C)

Open `rpn-calculator.kicad_pro` in KiCad (8 or later). The schematic is the whole circuit on one A2 sheet, built from the spec's rev C netlist.

| File | What |
|---|---|
| `rpn-calculator.kicad_sch` | Schematic, one sheet |
| `rpn-calculator.kicad_sym` | The project's symbols (library `rpn`, loaded through `sym-lib-table`) |
| `generate_schematic.py` | Builds the files above from the netlist |
| `check_schematic.py` | Rebuilds the netlist from the drawing and reports any unconnected pin, dangling wire or clash |

Every pin has a short wire and a net label, so pins with the same label are connected. The drawing with every connection as a wire is the Full Schematic doc.

Until PCB layout starts, change the circuit in `generate_schematic.py` and re-run it, then `check_schematic.py`. Once layout has started, edit in KiCad instead, since re-running would overwrite hand edits.

## Footprints
Assigned from KiCad's standard libraries: LQFP-64, SOT-23/-5/-6, 0805 and 1206 passives, the 1×6 header, Keystone 1058, GCT USB4085, Omron B3U-1000P, the 2.0 × 1.2 mm crystal, test pads and M2 holes. These names weren't checked against an installed KiCad, so the footprint assignment step may flag one.

Still to choose: J1 (Würth 687110183622), L1 (Würth 74404042047), SW1–SW22 (Kailh Choc V1, with or without hotswap sockets) and Y2. The Enter stabiliser has no circuit, so it goes straight on the PCB as a footprint.
