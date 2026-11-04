// RPN_Stage2.ino
// RPN calculator, stage 2: same behaviour as stage 1, with exact 12-digit
// decimal (BCD) maths in place of floating point. Real sleep and PC-pin
// wiring come later.
//
// Sketch folder RPN_Stage2 must contain: RPN_Stage2.ino, bcd.h, bcd.cpp,
// bcd_selftest.h (the tests folder is for the computer and is ignored).
//
// Hardware: Nucleo-L476RG, Adafruit 2.7" Sharp Memory breakout, 6 x 4 keypad.
// Wiring (unchanged from the test sketches):
//   Display: CLK -> D13, DI -> D11, CS -> D10, VIN -> 3V3 or 5V, GND -> GND
//   Keypad:  rows R1-R6 -> D2-D7, columns C1-C4 -> A0-A3
// Libraries: "Adafruit SHARP Memory Display" and "Adafruit GFX"
// The "Newlib Nano + Float Printf" setting is no longer needed: BCD does
// its own formatting.
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
//   (Off is still simulated: the chip stays awake. Real Stop 2 sleep later.)
// - At start-up the BCD maths checks itself against 422 cases computed with
//   Python's decimal module; the result is printed to Serial Monitor.

#include <Adafruit_GFX.h>
#include <Adafruit_SharpMem.h>
#include <vector>
#include "bcd.h"
#include "bcd_selftest.h"

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
const int VALUE_SIZE = 4;              // largest text size; shrinks to fit

// ============================ Keypad =============================
const uint8_t NUM_ROWS = 6, NUM_COLS = 4;
const uint8_t ROW_PINS[NUM_ROWS] = {2, 3, 4, 5, 6, 7};
const uint8_t COL_PINS[NUM_COLS] = {A0, A1, A2, A3};

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
const unsigned long AUTO_OFF_MS = 5UL * 60UL * 1000UL;   // 5 minutes

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
unsigned long lastScan = 0, pressStart = 0, lastKeyTime = 0, lastRefresh = 0;
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

// Largest built-in font size (from maxSize down) whose text fits maxW.
int fitSize(const char *text, int maxSize, int maxW) {
  int16_t bx, by;
  uint16_t bw, bh;
  for (int size = maxSize; size >= 1; size--) {
    display.setTextSize(size);
    display.getTextBounds(text, 0, 0, &bx, &by, &bw, &bh);
    if (bw <= maxW) return size;
  }
  return 1;
}

void drawValue(const char *text, int top, bool leftAlign) {
  int size = fitSize(text, VALUE_SIZE, VALUE_MAX_W);
  int16_t bx, by;
  uint16_t bw, bh;
  display.setTextSize(size);
  display.getTextBounds(text, 0, 0, &bx, &by, &bw, &bh);
  int x = leftAlign ? VALUE_LEFT : VALUE_RIGHT - bw;
  display.setCursor(x, top + (LINE_H - 8 * size) / 2);
  display.print(text);
}

void drawLabel(const char *label, int top) {
  display.setTextSize(2);
  display.setCursor(8, top + (LINE_H - 16) / 2);
  display.print(label);
}

// Value at stack level n (1 = bottom). Returns false if that level is empty.
bool levelValue(size_t n, BCD &v) {
  if (stack.size() < n) return false;
  v = stack[stack.size() - n];
  return true;
}

void drawScreen() {
  display.clearDisplay();
  if (isOff) { display.refresh(); lastRefresh = millis(); return; }
  display.setTextColor(BLACK, WHITE);

  // Status line: depth (or error) on the left
  char status[32];
  if (errorActive) snprintf(status, sizeof(status), "%s", errorMsg);
  else snprintf(status, sizeof(status), "%u on stack", (unsigned)stack.size());
  display.setTextSize(2);
  display.setCursor(8, 4);
  display.print(status);
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
  lastKeyTime = millis();
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

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("RPN calculator, stage 2 (12-digit BCD)");

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

  stack.reserve(64);
  display.begin();
  lastKeyTime = millis();
  if (failures) showError("BCD self-test FAILED");
  drawScreen();
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

  // Auto-off after 5 minutes without a key
  if (!isOff && now - lastKeyTime >= AUTO_OFF_MS) switchOff("auto-off");

  // Refresh about once a second so the library keeps toggling VCOM
  if (now - lastRefresh >= 1000) {
    display.refresh();
    lastRefresh = now;
  }
}
