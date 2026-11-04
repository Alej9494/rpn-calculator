// RPN_Stage1.ino
// RPN calculator, stage 1: full behaviour from the spec, with floating-point
// (double) maths. BCD maths, real sleep and PC-pin wiring come later.
//
// Hardware: Nucleo-L476RG, Adafruit 2.7" Sharp Memory breakout, 6 x 4 keypad.
// Wiring (unchanged from the test sketches):
//   Display: CLK -> D13, DI -> D11, CS -> D10, VIN -> 3V3 or 5V, GND -> GND
//   Keypad:  rows R1-R6 -> D2-D7, columns C1-C4 -> A0-A3
// Libraries: "Adafruit SHARP Memory Display" and "Adafruit GFX"
// IMPORTANT: Tools -> C Runtime Library -> "Newlib Nano + Float Printf"
// (number formatting uses printf with %e; without it numbers show blank).
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
//   (Stage 1 only simulates off: the chip stays awake. Real Stop 2 sleep later.)

#include <Adafruit_GFX.h>
#include <Adafruit_SharpMem.h>
#include <math.h>
#include <vector>

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
const double MAX_MAG = 9.99999999999e99;
const double MIN_MAG = 1e-99;
const uint8_t MAX_DIGITS = 12;

std::vector<double> stack;       // stack.back() is level 1
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
// Number formatting: 12 significant digits, trailing zeros removed,
// thousands grouped, scientific when it won't fit in 12 digits.
// =================================================================

// Insert commas into a string of integer digits.
void groupDigits(const char *digits, char *out) {
  size_t n = strlen(digits);
  size_t o = 0;
  for (size_t i = 0; i < n; i++) {
    out[o++] = digits[i];
    size_t remaining = n - i - 1;
    if (remaining > 0 && remaining % 3 == 0) out[o++] = ',';
  }
  out[o] = '\0';
}

void formatNumber(double v, char *out) {
  if (v == 0 || fabs(v) < MIN_MAG) { strcpy(out, "0"); return; }

  // Let printf round to 12 significant digits: d.dddddddddddE+xx
  char sci[32];
  snprintf(sci, sizeof(sci), "%.11e", fabs(v));
  char digits[16];
  int nd = 0;
  const char *p = sci;
  while (*p && *p != 'e') {
    if (*p >= '0' && *p <= '9') digits[nd++] = *p;
    p++;
  }
  digits[nd] = '\0';
  int e = atoi(p + 1);
  while (nd > 1 && digits[nd - 1] == '0') digits[--nd] = '\0';   // strip trailing zeros

  char body[40];
  if (e >= 0 && e < MAX_DIGITS) {
    // Fixed: e+1 integer digits
    char intPart[16], frac[16];
    int intLen = e + 1;
    for (int i = 0; i < intLen; i++) intPart[i] = (i < nd) ? digits[i] : '0';
    intPart[intLen] = '\0';
    int fracLen = (nd > intLen) ? nd - intLen : 0;
    memcpy(frac, digits + intLen, fracLen);
    frac[fracLen] = '\0';
    char grouped[24];
    groupDigits(intPart, grouped);
    if (fracLen > 0) snprintf(body, sizeof(body), "%s.%s", grouped, frac);
    else snprintf(body, sizeof(body), "%s", grouped);
  } else if (e < 0 && (-e - 1 + nd) <= MAX_DIGITS) {
    // Fixed small number: 0.000ddd
    int zeros = -e - 1;
    int o = 0;
    body[o++] = '0';
    body[o++] = '.';
    for (int i = 0; i < zeros; i++) body[o++] = '0';
    for (int i = 0; i < nd; i++) body[o++] = digits[i];
    body[o] = '\0';
  } else {
    // Scientific: d.dddE-xx
    if (nd > 1) snprintf(body, sizeof(body), "%c.%sE%d", digits[0], digits + 1, e);
    else snprintf(body, sizeof(body), "%cE%d", digits[0], e);
  }
  snprintf(out, 40, "%s%s", (v < 0) ? "-" : "", body);
}

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
bool levelValue(size_t n, double &v) {
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
    double v;
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

double peek(size_t n) {            // level n (1 = X), 0 if missing
  double v = 0;
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

// Check a result; returns false (and shows an error) if it's out of range.
bool checkResult(double &r) {
  if (r != r || fabs(r) > MAX_MAG) { showError("Overflow"); return false; }   // NaN or too big (incl. infinity)
  if (fabs(r) < MIN_MAG) r = 0;
  return true;
}

// Push the command line onto the stack. Returns false if the stack is full.
bool commitEntry() {
  if (!entering) return true;
  entering = false;
  bool hasDigit = false;
  for (const char *p = entry; *p; p++) if (*p >= '0' && *p <= '9') hasDigit = true;
  double v = atof(entry);
  entry[0] = '\0';
  if (!hasDigit) return true;                           // "-" or "." alone: discard
  if (stack.size() >= STACK_MAX) { showError("Stack full"); return false; }
  stack.push_back(v == 0 ? 0 : v);
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
  if (!stack.empty() && stack.back() != 0) stack.back() = -stack.back();
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
  if (n == 1) stack.insert(stack.begin(), 0.0);        // missing level 2 counts as 0
  std::swap(stack[stack.size() - 1], stack[stack.size() - 2]);
}

void keyBinary(Key k) {
  if (!commitEntry()) return;
  double x = peek(1), y = peek(2), r = 0;
  switch (k) {
    case K_ADD: r = y + x; break;
    case K_SUB: r = y - x; break;
    case K_MUL: r = y * x; break;
    case K_DIV:
      if (x == 0) { showError("Error: divide by 0"); return; }
      r = y / x;
      break;
    default: return;
  }
  if (!checkResult(r)) return;                          // stack untouched on error
  dropLevels(2);
  stack.push_back(r);
}

void keySqrt() {
  if (!commitEntry()) return;
  double x = peek(1);
  if (x < 0) { showError("Error: sqrt of negative"); return; }
  double r = sqrt(x);
  if (!checkResult(r)) return;
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

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("RPN calculator, stage 1 (floating point)");

  for (uint8_t r = 0; r < NUM_ROWS; r++) pinMode(ROW_PINS[r], INPUT);
  for (uint8_t c = 0; c < NUM_COLS; c++) pinMode(COL_PINS[c], INPUT_PULLUP);

  stack.reserve(64);
  display.begin();
  lastKeyTime = millis();
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
