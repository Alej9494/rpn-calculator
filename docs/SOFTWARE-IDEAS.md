# Future software enhancements

Ideas for improving the calculator without changing the hardware. None of these are decided yet; each needs a decision before it is built, and anything that changes behaviour must go into both the firmware and the web app.

The keypad has no spare keys, so new functions have to use states that are free today:
- ~~BACK when nothing is typed~~ (now used for undo)
- a long-press on any key except CLEAR (CLEAR's long-press already switches off)
- a key held while waking the calculator

## Stack and maths
- [x] **Undo.** Done in firmware stage 6; see `DESIGN.md`.
- [x] **Too few arguments.** Done in firmware stage 6: HP 48 error; see `DESIGN.md`.
- [ ] **Stack browser.** A long-press opens a view of the whole stack that scrolls with 8 and 2. ENTER copies the chosen level to level 1 (HP 48 PICK), and DROP deletes it. This also gives a roll down without a new key.
- [ ] **Fixed 2 decimal places.** An optional FIX 2 display mode for money sums. It changes only how numbers are shown, not the 12-digit maths.

## Small behaviour fixes
- [ ] Auto-repeat BACK while it is held.
- [ ] Hysteresis on the battery icon, so it doesn't switch between 2 and 3 bars every minute when the voltage sits near a threshold.
- [ ] Consistent error messages: "Overflow" has no "Error:" prefix, unlike the others. Possibly a short "Underflow" note, since results below 1E-99 currently become 0 silently.
- [ ] Check on the HP 48SX what happens to the key pressed while an error is showing. Here that key only clears the message.

## Battery life
- [ ] Redraw only the lines that changed. The Sharp panel can update single lines, but every keypress currently clears and resends all 240.
- [ ] Toggle VCOM from the low-power timer, as already planned for the PCB, to remove the once-a-second wake.
- [ ] Keep the stack in a fixed array instead of a `std::vector`, so the heap doesn't grow or fragment in a device that never reboots.

## Robustness
- [ ] **Watchdog.** Use the independent watchdog to reset a hung calculator instead of leaving it stuck until the battery comes out. How it behaves in Stop 2 is set in the option bytes; not checked yet.
- [ ] **Info screen.** Open it by holding a key at wake-up. It shows the firmware version, the battery voltage in mV, the self-test result and the auto-off time.

## Firmware and web app in step
- [ ] **Shared calculator logic.** Move the stack and key logic out of the `.ino` into plain C++ that doesn't depend on Arduino. The shared keystroke tests in `tests/` can then run on a PC. The same code compiled to WebAssembly could power the web app, so the two behave identically by construction rather than being kept in step by hand.

## Suggested order
Next: the shared logic module (undo and too few arguments are done).
