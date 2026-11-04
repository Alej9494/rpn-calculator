// RPN_Stage5.ino
// RPN calculator, stage 5: stage 4 (BCD maths, DejaVu fonts, Stop 2 sleep)
// with a battery indicator. The chip measures its own supply voltage against
// its internal reference (VREFINT) and shows a battery icon on the right of
// the status line. No extra parts are needed.
//
// Sketch folder RPN_Stage5 must contain: RPN_Stage5.ino, bcd.h, bcd.cpp,
// bcd_selftest.h, fonts.h.
//
// On the Nucleo the supply is a steady 3.3 V, so the icon shows full. To see
// the other levels, raise the BATT_ thresholds below for a test upload.
//
// Hardware: Nucleo-L476RG, Adafruit 2.7" Sharp Memory breakout, 6 x 4 keypad.
// Wiring:
//   Display: CLK -> D13, DI -> D11, CS -> D10, VIN -> 3V3 or 5V, GND -> GND
//   Keypad rows R1-R6:    PC6 (CN10-4), PC7 (CN10-19), PC8 (CN10-2),
//                         PC9 (CN10-1), PC10 (CN7-1), PC12 (CN7-3)
//   (ROW6 moved off PC11: ST's bootloader listens on PC11 as USART3 RX)
//   Keypad columns C1-C4: PC0 (CN7-38), PC1 (CN7-36), PC2 (CN7-35), PC3 (CN7-37)
//   (the same pins as the PCB; each column has its own wake-up line)
// Libraries: "Adafruit SHARP Memory Display", "Adafruit GFX",
//            "STM32duino Low Power" and "STM32duino RTC"
//
// Power:
// - On and idle: Stop 2, waking once a second to toggle the display's VCOM
//   and count towards the 5-minute auto-off. (The PCB will toggle VCOM from
//   the low-power timer instead, so it won't need these wakes.)
// - Off: screen cleared, Stop 2 with no timed wakes; only a key wakes it.
// - Serial Monitor only shows output while the chip is awake.
//
// Behaviour (HP 48 style):
// - Typing goes on a command line at the bottom, left-justified; the stack
//   shifts up so levels 3-1 stay visible. 4 lines in all, no separate X line.
// - ENTER pushes the typed number once. ENTER with nothing typed duplicates level 1.
// - An operation while typing enters the number first (5 ENTER 3 + = 8).
// - Unlimited stack (capped at STACK_MAX to protect RAM); missing operands = 0.
// - Errors (divide by 0, sqrt of negative, overflow) leave the stack untouched;
//   the next key only clears the message.
// - CLEAR acts on release; held 3 s it "switches off" (screen blanks, stack kept).
// - Auto-off after 5 minutes without a key. Any key wakes; that press is ignored.
// - At start-up the BCD maths checks itself against 422 cases computed with
//   Python's decimal module; the result is printed to Serial Monitor.

#include <Adafruit_GFX.h>
#include <Adafruit_SharpMem.h>
#include <vector>
#include <SPI.h>
#include <STM32LowPower.h>
#include "bcd.h"
#include "bcd_selftest.h"
#include "fonts.h"
#include "stm32yyxx_ll_adc.h"             // VREFINT calibration maths

// ============================ Display ============================
#define SHARP_CS 10
#define WIDTH    400
#define HEIGHT   240
#define BLACK 0
#define WHITE 1
Adafruit_SharpMem display(&SPI, SHARP_CS, WIDTH, HEIGHT, 2000000);

// Screen rows from the spec
const int ROW_STATUS_H = 24;
const int LINE_H = 54;                 // 4 lines of 54 px below the status line
const int LINE_TOP[4] = {24, 78, 132, 186};
const int VALUE_RIGHT = WIDTH - 8;     // right edge for numbers
const int VALUE_LEFT = 8;              // left edge for the command line
const int VALUE_MAX_W = WIDTH - 56;    // space left after the level label

// ============================ Keypad =============================
const uint8_t NUM_ROWS = 6, NUM_COLS = 4;
const uint32_t ROW_PINS[NUM_ROWS] = {PC6, PC7, PC8, PC9, PC10, PC12};
const uint32_t COL_PINS[NUM_COLS] = {PC0, PC1, PC2, PC3};

enum Key : int8_t {
  K_NONE = -1,
  K_CLEAR, K_DROP, K_SWAP, K_SQRT,
  K_7, K_8, K_9, K_DIV,
  K_4, K_5, K_6, K_MUL,
  K_1, K_2, K_3, K_SUB,
  K_0, K_DOT, K_NEG, K_ADD,
  K_EMPTY1, K_ENTER, K_EMPTY2, K_BACK
};
const char *KEY_LABEL[24] = {
  "CLEAR", "DROP", "SWAP", "SQRT", "7", "8", "9", "/", "4", "5", "6", "*",
  "1", "2", "3", "-", "0", ".", "+/-", "+", "(none)", "ENTER", "(none)", "BACK"
};

const int MULTI_KEY = -2;
const unsigned long SCAN_MS = 5;
const uint8_t DEBOUNCE_SCANS = 4;              // 20 ms
const unsigned long CLEAR_OFF_MS = 3000;       // hold CLEAR to switch off
const unsigned int AUTO_OFF_S = 5 * 60;                  // 5 minutes

// Battery icon thresholds in millivolts (CR2032 is about 3.0 V new). Set the
// final values once the PCB runs from a real coin cell; see the spec.
const uint16_t BATT_3_BARS_MV = 2850;     // at or above: full
const uint16_t BATT_2_BARS_MV = 2650;
const uint16_t BATT_1_BAR_MV  = 2450;     // below this: empty icon with "!"
const unsigned int BATT_CHECK_S = 60;     // re-check once a minute while idle
const uint32_t TICK_MS = 1000;                           // timed wake while on and idle

// ============================ Calculator state ===================
const size_t STACK_MAX = 1000;
const uint8_t MAX_DIGITS = 12;

std::vector<BCD> stack;          // stack.back() is level 1
bool entering = false;           // true while a number is on the command line
char entry[24] = "";             // the command line, as typed (not on the stack yet)
bool errorActive = false;
const char *errorMsg = "";
bool isOff = false;

// Key handling state
int stableKey = K_NONE, lastRaw = K_NONE;
uint8_t sameCount = 0;
unsigned long lastScan = 0, pressStart = 0, lastRefresh = 0;
unsigned int idleSeconds = 0;    // timed wakes since the last key (millis stops in Stop 2)
volatile bool keyWoke = false;   // set by the column interrupt
bool vcomBit = false;
uint16_t battMv = 0;             // smoothed supply voltage, millivolts (0 = not read yet)
bool clearHoldHandled = false;   // CLEAR already switched off during this hold
bool ignoreRelease = false;      // release of a key that only woke / cleared an error

// =================================================================
// Number formatting: done by bcdFormat (12 significant digits, trailing
// zeros removed, thousands grouped, scientific when it won't fit).
// =================================================================

void formatNumber(const BCD &v, char *out) { bcdFormat(v, out); }

// =================================================================
// Drawing
// =================================================================

// Width of text in a font: the sum of each character's advance.
int textWidth(const GFXfont *f, const char *text) {
  int w = 0;
  for (const char *p = text; *p; p++) {
    uint8_t c = *p;
    if (c >= f->first && c <= f->last) w += f->glyph[c - f->first].xAdvance;
  }
  return w;
}

// A number on one of the four lines: big font, or medium if it won't fit.
void drawValue(const char *text, int top, bool leftAlign) {
  const GFXfont *f = &CalcBig;
  int digitH = CALCBIG_DIGIT_H;
  int w = textWidth(f, text);
  if (w > VALUE_MAX_W) {
    f = &CalcMedium;
    digitH = CALCMEDIUM_DIGIT_H;
    w = textWidth(f, text);
  }
  display.setFont(f);
  int x = leftAlign ? VALUE_LEFT : VALUE_RIGHT - w;
  display.setCursor(x, top + (LINE_H + digitH) / 2);   // cursor y is the baseline
  display.print(text);
}

void drawLabel(const char *label, int top) {
  display.setFont(&CalcLabel);
  display.setCursor(8, top + (LINE_H + CALCLABEL_DIGIT_H) / 2);
  display.print(label);
}

// Value at stack level n (1 = bottom). Returns false if that level is empty.
bool levelValue(size_t n, BCD &v) {
  if (stack.size() < n) return false;
  v = stack[stack.size() - n];
  return true;
}

// =================================================================
// Battery
// =================================================================

// Read the supply voltage via the internal reference and smooth it a little.
// Called while the CPU is busy redrawing, so a coin cell is under load and
// shows its true, lower voltage.
void readBattery() {
  uint32_t raw = analogRead(AVREF);
  uint32_t mv = __LL_ADC_CALC_VREFANALOG_VOLTAGE(raw, LL_ADC_RESOLUTION_12B);
  battMv = battMv ? (uint16_t)((battMv * 3UL + mv) / 4) : (uint16_t)mv;
}

int batteryBars() {
  if (battMv >= BATT_3_BARS_MV) return 3;
  if (battMv >= BATT_2_BARS_MV) return 2;
  if (battMv >= BATT_1_BAR_MV) return 1;
  return 0;
}

// Battery icon at the right of the status line: an outline with a nub and
// up to three bars. Empty shows a "!" instead.
void drawBattery() {
  const int w = 28, h = 14;
  const int x = WIDTH - 8 - w - 3, y = (ROW_STATUS_H - h) / 2 - 1;
  display.drawRect(x, y, w, h, BLACK);
  display.drawRect(x + 1, y + 1, w - 2, h - 2, BLACK);            // 2 px outline
  display.fillRect(x + w, y + 4, 3, h - 8, BLACK);                // nub
  int bars = batteryBars();
  for (int i = 0; i < bars; i++)
    display.fillRect(x + 4 + i * 7, y + 4, 6, h - 8, BLACK);
  if (bars == 0) {
    display.fillRect(x + w / 2 - 1, y + 3, 3, 5, BLACK);          // "!"
    display.fillRect(x + w / 2 - 1, y + h - 5, 3, 2, BLACK);
  }
}

void drawScreen() {
  display.clearDisplay();
  if (isOff) { display.refresh(); lastRefresh = millis(); return; }
  display.setTextColor(BLACK, WHITE);

  // Status line: depth (or error) on the left
  char status[32];
  if (errorActive) snprintf(status, sizeof(status), "%s", errorMsg);
  else snprintf(status, sizeof(status), "%u on stack", (unsigned)stack.size());
  display.setFont(&CalcLabel);
  display.setCursor(8, 4 + CALCLABEL_DIGIT_H);
  display.print(status);
  readBattery();
  drawBattery();
  display.drawFastHLine(0, ROW_STATUS_H - 1, WIDTH, BLACK);

  // Not typing: levels 4, 3, 2, 1. Typing: levels 3, 2, 1, then the command line.
  int topLevel = entering ? 3 : 4;
  for (int line = 0; line < topLevel; line++) {
    int level = topLevel - line;
    char label[4];
    snprintf(label, sizeof(label), "%d:", level);
    drawLabel(label, LINE_TOP[line]);
    BCD v;
    if (levelValue(level, v)) {
      char buf[40];
      formatNumber(v, buf);
      drawValue(buf, LINE_TOP[line], false);   // right-justified
    }
  }
  if (entering) drawValue(entry, LINE_TOP[3], true);   // command line, left-justified

  display.refresh();
  lastRefresh = millis();
}

// =================================================================
// Stack helpers
// =================================================================

BCD peek(size_t n) {               // level n (1 = bottom), 0 if missing
  BCD v = bcdZero();
  levelValue(n, v);
  return v;
}

void dropLevels(size_t n) {
  while (n-- > 0 && !stack.empty()) stack.pop_back();
}

void showError(const char *msg) {
  errorActive = true;
  errorMsg = msg;
  Serial.println(msg);
}

// Show the error for a failed BCD operation. Returns true if it succeeded.
bool checkStatus(BcdStatus st) {
  switch (st) {
    case BCD_OK: return true;
    case BCD_OVERFLOW: showError("Overflow"); return false;
    case BCD_DIV_ZERO: showError("Error: divide by 0"); return false;
    case BCD_NEG_SQRT: showError("Error: sqrt of negative"); return false;
    default: showError("Error: bad number"); return false;
  }
}

// Push the command line onto the stack. Returns false if the stack is full.
bool commitEntry() {
  if (!entering) return true;
  entering = false;
  bool hasDigit = false;
  for (const char *p = entry; *p; p++) if (*p >= '0' && *p <= '9') hasDigit = true;
  BCD v;
  BcdStatus st = hasDigit ? bcdFromString(entry, v) : BCD_OK;
  entry[0] = '\0';
  if (!hasDigit) return true;                           // "-" or "." alone: discard
  if (!checkStatus(st)) return false;
  if (stack.size() >= STACK_MAX) { showError("Stack full"); return false; }
  stack.push_back(v);
  return true;
}

void startEntry() {
  if (!entering) { entering = true; entry[0] = '\0'; }
}

uint8_t entryDigitCount() {
  uint8_t n = 0;
  for (const char *p = entry; *p; p++) if (*p >= '0' && *p <= '9') n++;
  const char *s = (entry[0] == '-') ? entry + 1 : entry;
  if (s[0] == '0' && s[1] == '.') n--;   // a leading "0." isn't significant
  return n;
}

// =================================================================
// Key actions
// =================================================================

void keyDigit(char d) {
  startEntry();
  if (entryDigitCount() >= MAX_DIGITS) return;          // 13th digit ignored
  const char *s = (entry[0] == '-') ? entry + 1 : entry;
  if (strcmp(s, "0") == 0) {                            // "007" -> "7"
    entry[strlen(entry) - 1] = d;
  } else {
    size_t n = strlen(entry);
    entry[n] = d;
    entry[n + 1] = '\0';
  }
}

void keyDot() {
  startEntry();
  if (strchr(entry, '.')) return;                       // only one point
  const char *s = (entry[0] == '-') ? entry + 1 : entry;
  if (*s == '\0') strcat(entry, "0");                   // ".5" shows as "0.5"
  strcat(entry, ".");
}

void keyEnter() {
  if (entering) { commitEntry(); return; }              // push the typed number once
  if (stack.empty()) return;
  if (stack.size() >= STACK_MAX) { showError("Stack full"); return; }
  stack.push_back(stack.back());                        // nothing typed: duplicate level 1
}

void keyNeg() {
  if (entering) {
    if (entry[0] == '-') memmove(entry, entry + 1, strlen(entry));
    else { memmove(entry + 1, entry, strlen(entry) + 1); entry[0] = '-'; }
    return;
  }
  if (!stack.empty()) stack.back() = bcdNegate(stack.back());
}

void keyBack() {
  if (!entering) return;                                // no effect when not typing
  size_t n = strlen(entry);
  if (n > 0) entry[n - 1] = '\0';
  const char *s = (entry[0] == '-') ? entry + 1 : entry;
  if (*s == '\0') { entering = false; entry[0] = '\0'; }   // command line emptied
}

void keyDrop() {
  if (entering) { entering = false; entry[0] = '\0'; return; }   // abandon the typing
  if (!stack.empty()) stack.pop_back();
}

void keySwap() {
  if (!commitEntry()) return;
  size_t n = stack.size();
  if (n == 0) return;
  if (n == 1) stack.insert(stack.begin(), bcdZero());  // missing level 2 counts as 0
  std::swap(stack[stack.size() - 1], stack[stack.size() - 2]);
}

void keyBinary(Key k) {
  if (!commitEntry()) return;
  BCD x = peek(1), y = peek(2), r;
  BcdStatus st;
  switch (k) {
    case K_ADD: st = bcdAdd(y, x, r); break;
    case K_SUB: st = bcdSub(y, x, r); break;
    case K_MUL: st = bcdMul(y, x, r); break;
    case K_DIV: st = bcdDiv(y, x, r); break;
    default: return;
  }
  if (!checkStatus(st)) return;                         // stack untouched on error
  dropLevels(2);
  stack.push_back(r);
}

void keySqrt() {
  if (!commitEntry()) return;
  BCD r;
  if (!checkStatus(bcdSqrt(peek(1), r))) return;
  if (stack.empty()) stack.push_back(r);
  else stack.back() = r;
}

void clearAll() {
  stack.clear();
  entering = false;
  entry[0] = '\0';
}

void switchOff(const char *why) {
  isOff = true;
  Serial.print("Switching off (");
  Serial.print(why);
  Serial.println("), stack kept");
  drawScreen();
}

void printStack() {
  Serial.print("Stack (top .. level 1): ");
  for (size_t i = 0; i < stack.size(); i++) {
    char buf[40];
    formatNumber(stack[i], buf);
    Serial.print(buf);
    Serial.print(i + 1 < stack.size() ? " | " : "");
  }
  if (entering) { Serial.print("   typing: "); Serial.print(entry); }
  Serial.println();
}

// =================================================================
// Key events
// =================================================================

void onKeyDown(int k) {
  idleSeconds = 0;
  pressStart = millis();
  clearHoldHandled = false;
  ignoreRelease = false;

  if (isOff) {                    // any key wakes; that press does nothing else
    isOff = false;
    ignoreRelease = true;
    Serial.println("Woken");
    drawScreen();
    return;
  }
  if (errorActive) {              // next key only clears the message
    errorActive = false;
    ignoreRelease = true;
    drawScreen();
    return;
  }

  Serial.print("Key ");
  Serial.println(KEY_LABEL[k]);

  switch (k) {
    case K_0: keyDigit('0'); break;
    case K_1: keyDigit('1'); break;
    case K_2: keyDigit('2'); break;
    case K_3: keyDigit('3'); break;
    case K_4: keyDigit('4'); break;
    case K_5: keyDigit('5'); break;
    case K_6: keyDigit('6'); break;
    case K_7: keyDigit('7'); break;
    case K_8: keyDigit('8'); break;
    case K_9: keyDigit('9'); break;
    case K_DOT: keyDot(); break;
    case K_ENTER: keyEnter(); break;
    case K_NEG: keyNeg(); break;
    case K_BACK: keyBack(); break;
    case K_DROP: keyDrop(); break;
    case K_SWAP: keySwap(); break;
    case K_ADD: case K_SUB: case K_MUL: case K_DIV: keyBinary((Key)k); break;
    case K_SQRT: keySqrt(); break;
    case K_CLEAR: return;          // CLEAR acts on release (or at 3 s held)
    default: return;               // empty matrix positions
  }
  printStack();
  drawScreen();
  Serial.print("Supply: ");
  Serial.print(battMv);
  Serial.println(" mV");
}

void onKeyUp(int k) {
  if (ignoreRelease) { ignoreRelease = false; return; }
  if (k == K_CLEAR && !clearHoldHandled) {   // tap: clear everything
    Serial.println("Key CLEAR (tap)");
    clearAll();
    printStack();
    drawScreen();
  }
}

// =================================================================
// Keypad scanning (same method as Keypad_Test)
// =================================================================

int scanMatrix() {
  int found = K_NONE;
  for (uint8_t r = 0; r < NUM_ROWS; r++) {
    pinMode(ROW_PINS[r], OUTPUT);
    digitalWrite(ROW_PINS[r], LOW);
    delayMicroseconds(10);
    for (uint8_t c = 0; c < NUM_COLS; c++) {
      if (digitalRead(COL_PINS[c]) == LOW) {
        int k = r * NUM_COLS + c;
        found = (found == K_NONE) ? k : MULTI_KEY;
      }
    }
    pinMode(ROW_PINS[r], INPUT);
  }
  return found;
}

// =================================================================
// Start-up self-test: re-run a sample of the computer test cases on the
// Nucleo, to confirm the BCD maths behaves the same on the ARM chip.
// =================================================================

int runSelfTest() {
  int failures = 0;
  for (int i = 0; i < BCD_CASE_COUNT; i++) {
    const BcdCase &c = BCD_CASES[i];
    char got[40];
    BCD a, b, r = bcdZero();
    BcdStatus st = bcdFromString(c.a, a);
    if (c.b) bcdFromString(c.b, b);
    if (c.op != 'p') st = BCD_OK;
    switch (c.op) {
      case '+': st = bcdAdd(a, b, r); break;
      case '-': st = bcdSub(a, b, r); break;
      case '*': st = bcdMul(a, b, r); break;
      case '/': st = bcdDiv(a, b, r); break;
      case 'r': st = bcdSqrt(a, r); break;
      case 'p': r = a; break;
      case 'f': break;
    }
    if (c.op == 'f') bcdFormat(a, got);
    else if (st == BCD_OK) bcdToSci(r, got);
    else strcpy(got, st == BCD_OVERFLOW ? "OVF" : st == BCD_DIV_ZERO ? "DIV0"
                     : st == BCD_NEG_SQRT ? "NEGSQRT" : "BADINPUT");
    if (strcmp(got, c.expect) != 0) {
      failures++;
      Serial.print("  FAIL ");
      Serial.print(c.op);
      Serial.print(' ');
      Serial.print(c.a);
      Serial.print(' ');
      Serial.print(c.b ? c.b : "");
      Serial.print(" expected ");
      Serial.print(c.expect);
      Serial.print(" got ");
      Serial.println(got);
    }
  }
  return failures;
}

// =================================================================
// Sleep
// =================================================================

void keyWakeISR() { keyWoke = true; }

// The serial link is shut down while asleep and restarted only when needed,
// so the once-a-second VCOM wake stays as short as possible.
bool serialActive = true;

void serialOff() {
  if (!serialActive) return;
  Serial.flush();                              // let pending text out first
  Serial.end();
  pinMode(PA2, INPUT_ANALOG);
  pinMode(PA3, INPUT_ANALOG);
  serialActive = false;
}

void serialOn() {
  if (serialActive) return;
  Serial.begin(115200);
  serialActive = true;
}

// Toggle the display's VCOM without sending a frame: the Sharp "maintain"
// command, two bytes, LSB first. Takes about 15 microseconds.
void vcomToggle() {
  vcomBit = !vcomBit;
  SPI.beginTransaction(SPISettings(2000000, LSBFIRST, SPI_MODE0));
  digitalWrite(SHARP_CS, HIGH);
  delayMicroseconds(3);
  SPI.transfer(vcomBit ? 0x02 : 0x00);
  SPI.transfer(0x00);
  delayMicroseconds(1);
  digitalWrite(SHARP_CS, LOW);
  SPI.endTransaction();
}

// Sleep in Stop 2 until a key (or, while on, the next one-second tick).
void sleepUntilWake() {
  for (uint8_t r = 0; r < NUM_ROWS; r++) {     // all rows low: any key pulls a column low
    pinMode(ROW_PINS[r], OUTPUT);
    digitalWrite(ROW_PINS[r], LOW);
  }
  keyWoke = false;

  // Park the pins that would otherwise leak while asleep: the serial link to
  // the ST-LINK (PA2, PA3) and the unused, floating SPI MISO (PA6).
  serialOff();
  pinMode(PA6, INPUT_ANALOG);

  if (isOff) LowPower.deepSleep();             // off: only a key wakes it
  else LowPower.deepSleep(TICK_MS);            // on: wake for VCOM and auto-off

  for (uint8_t r = 0; r < NUM_ROWS; r++) pinMode(ROW_PINS[r], INPUT);   // back to scanning

  if (keyWoke) {
    serialOn();                                // serial back only when a key wakes it
    sameCount = 0;                             // start debouncing the wake key at once
    lastScan = 0;
    return;
  }
  if (!isOff) {
    vcomToggle();
    if (idleSeconds > 0 && idleSeconds % BATT_CHECK_S == 0) {
      int before = batteryBars();
      readBattery();
      if (batteryBars() != before) drawScreen();   // redraw only if the icon changes
    }
    if (++idleSeconds >= AUTO_OFF_S) {
      serialOn();                              // switchOff prints a message
      switchOff("auto-off");
    }
  }
}

// Put every pin this sketch doesn't use into analog mode. Floating digital
// inputs (and PH0, which the Nucleo's ST-LINK feeds with an 8 MHz clock)
// draw hundreds of microamps in Stop 2; analog mode cuts that to almost nothing.
// Kept as they are: Serial (PA2, PA3), display SPI and CS (PA5, PA6, PA7, PB6),
// SWD (PA13, PA14), keypad (PC0-PC3, PC6-PC10, PC12), 32 kHz crystal (PC14, PC15).
void unusedPinsToAnalog() {
  const uint32_t unused[] = {
    PA0, PA1, PA4, PA8, PA9, PA10, PA11, PA12, PA15,
    PB0, PB1, PB2, PB3, PB4, PB5, PB7, PB8, PB9, PB10, PB11, PB12, PB13, PB14, PB15,
    PC4, PC5, PC11, PC13, PD2, PH0, PH1
  };
  for (uint32_t pin : unused) pinMode(pin, INPUT_ANALOG);
}

void setup() {
  unusedPinsToAnalog();
  HAL_DBGMCU_DisableDBGStopMode();             // debugger must not keep the chip awake in Stop
  Serial.begin(115200);
  delay(500);
  Serial.println("RPN calculator, stage 5 (BCD, fonts, sleep, battery indicator)");
  analogReadResolution(12);

  unsigned long t0 = millis();
  int failures = runSelfTest();
  Serial.print("BCD self-test: ");
  Serial.print(BCD_CASE_COUNT - failures);
  Serial.print("/");
  Serial.print(BCD_CASE_COUNT);
  Serial.print(" passed in ");
  Serial.print(millis() - t0);
  Serial.println(" ms");

  for (uint8_t r = 0; r < NUM_ROWS; r++) pinMode(ROW_PINS[r], INPUT);
  for (uint8_t c = 0; c < NUM_COLS; c++) pinMode(COL_PINS[c], INPUT_PULLUP);

  LowPower.begin();
  for (uint8_t c = 0; c < NUM_COLS; c++)
    LowPower.attachInterruptWakeup(COL_PINS[c], keyWakeISR, FALLING, DEEP_SLEEP_MODE);

  stack.reserve(64);
  display.begin();
  if (failures) showError("BCD self-test FAILED");
  drawScreen();
  Serial.print("Supply: ");
  Serial.print(battMv);
  Serial.println(" mV");
}

void loop() {
  unsigned long now = millis();

  if (now - lastScan >= SCAN_MS) {
    lastScan = now;
    int raw = scanMatrix();
    if (raw == lastRaw) {
      if (sameCount < DEBOUNCE_SCANS) sameCount++;
    } else {
      lastRaw = raw;
      sameCount = 1;
    }
    if (sameCount == DEBOUNCE_SCANS && raw != stableKey) {
      int previous = stableKey;
      stableKey = raw;
      if (previous >= 0) onKeyUp(previous);
      if (raw >= 0) onKeyDown(raw);
      // MULTI_KEY: more than one key down, ignored
    }
  }

  // CLEAR held for 3 s: switch off straight away, keep the stack
  if (stableKey == K_CLEAR && !clearHoldHandled && !ignoreRelease &&
      now - pressStart >= CLEAR_OFF_MS) {
    clearHoldHandled = true;
    switchOff("CLEAR held");
  }

  // While awake (a key held), keep VCOM toggling about once a second
  if (!isOff && now - lastRefresh >= 1000) {
    vcomToggle();
    lastRefresh = now;
  }

  // Nothing held and the keypad has settled: sleep until the next key or tick
  if (stableKey == K_NONE && lastRaw == K_NONE && sameCount >= DEBOUNCE_SCANS) {
    sleepUntilWake();
  }
}
