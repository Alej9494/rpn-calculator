# RPN Calculator — Design

A simple hardware RPN calculator, with a matching phone web app. Both must behave identically.

## Scope
- Operations: + − × ÷ and square root only (no trig)
- RPN behaviour modelled on HP; entry style follows the HP 48
- 12-digit resolution, BCD (decimal) arithmetic
- Kept deliberately simple

## Entry and stack behaviour (HP 48 style)
- Typing goes onto a left-justified command line
- ENTER pushes the command line once; it duplicates only when nothing is typed
- 4 equal stack lines on screen, with no separate X line; the stack itself is unlimited
- Separate Backspace and Drop keys
- Too few arguments: an operation that needs more stack levels than there are shows "Error: too few arguments", as on the HP 48. + − × ÷ and SWAP need 2 levels; √x, DROP, +/− and ENTER (duplicate) need 1. A number being typed is pushed first, so `3 +` on an empty stack leaves 3 on the stack
- Undo: BACK with nothing typed restores the stack as it was before the last key that changed it. One level, as on the HP 48; BACK again redoes. A number that was being typed is not brought back. CLEAR can be undone, and undo survives auto-off
- No EEX key

## Screen
- 400 × 240 Sharp Memory LCD: a status line (stack depth or error message on the left, battery icon on the right), then 4 equal lines
- Not typing: levels 4–1, numbers right-justified. Typing: levels 3–1, with the command line left-justified at the bottom
- Numbers: 12 significant digits, thousands grouped with commas, scientific notation when they don't fit, true minus sign
- Battery icon: 3, 2, 1 bars, then an empty outline with "!" when low; the supply is measured against VREFINT, with no extra parts

![Screen font preview](images/screen-font-preview.png)

![Battery icon levels](images/battery-icon-levels.png)

## Power and sleep
- CR2032 coin cell
- No On/Off key: auto-off after 5 minutes, with the stack kept in RAM
- Holding Clear for 3 s switches off; Clear acts on release
- The stack is not saved to flash on battery swap
- Battery voltage monitoring

## Firmware updates
- USB-C is used for firmware updates and powers the device while updating; it is not a normal power source
- Hold SWAP while plugging in USB-C to enter update mode
- A recovery button for corrupt firmware, reachable through a 1 mm hole in the case
- SWD header on the PCB (pads with a soldered header)

## Hardware
- MCU: STM32L476 (prototyped on a Nucleo L476RG)
- Display: Sharp LS027B7DH01 2.7" Memory LCD, zero-defect grade (Adafruit board for the prototype)
- Font: DejaVu Sans Condensed Bold, status line included
- Keys: Kailh Choc V1 for the final build; cheaper buttons for the prototype
- 3-wide Enter key with a stabiliser and one centre switch
- Key layout matches the phone app
- PCB: bare board from the fab, all parts hand-soldered by Alex
- Enclosure: 3D-designed, printed case

## Status (Nov 2026)
- Working on the Nucleo: display, keypad, BCD maths, real sleep and auto-off
- Next: a full-circuit prototype using a 64-pin LQFP breakout for the STM32, SOT-23 adapter boards, and the existing perfboard keypad on a header, before committing to the keypad PCB

## Hardware details
The full hardware design (pin map, netlist, power path, BOM, test plan) is in the live spec, and the circuit is in the one-sheet Full Schematic; links are in `CLAUDE.md`. BOMs are in `hardware/`.

## Open items
Tracked in the spec's "Still to check or do": panel ribbon thickness for J1, SW23 height, stabiliser fit, C19/C20 part number, Enter keycap, Nucleo bootloader ID, then KiCad capture, PCB layout and the firmware port to the PCB pin map.
