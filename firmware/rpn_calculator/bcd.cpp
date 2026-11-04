// bcd.cpp - 12-digit decimal arithmetic. See bcd.h for the number format.
//
// Each operation works on exact big decimal integers (Big, below), then
// rounds the exact result half-up to 12 digits in pack(). Because the
// intermediate results are exact, the rounding is always correct.

#include "bcd.h"
#include <string.h>

// ---------------------------------------------------------------------------
// Big: an unsigned decimal integer, one digit per byte, least significant
// first. n is the number of digits (0 means the value 0). 72 digits is more
// than any operation needs (the largest is an addition with 40 digits of
// alignment: 12 + 40 + 1).
// ---------------------------------------------------------------------------
static const int BIG_MAX = 72;

struct Big {
  uint8_t d[BIG_MAX];
  int n;
};

static void bigTrim(Big &b) {
  while (b.n > 0 && b.d[b.n - 1] == 0) b.n--;
}

static void bigZero(Big &b) { b.n = 0; }

static void bigFromMant(const BCD &x, Big &b) {
  for (int i = 0; i < BCD_DIGITS; i++) b.d[i] = x.m[BCD_DIGITS - 1 - i];
  b.n = BCD_DIGITS;
  bigTrim(b);
}

// Multiply by 10^k (append k zeros).
static void bigShift(Big &b, int k) {
  if (b.n == 0 || k <= 0) return;
  memmove(b.d + k, b.d, b.n);
  memset(b.d, 0, k);
  b.n += k;
}

static int bigCmp(const Big &a, const Big &b) {
  if (a.n != b.n) return a.n < b.n ? -1 : 1;
  for (int i = a.n - 1; i >= 0; i--) {
    if (a.d[i] != b.d[i]) return a.d[i] < b.d[i] ? -1 : 1;
  }
  return 0;
}

// a += b
static void bigAdd(Big &a, const Big &b) {
  int n = a.n > b.n ? a.n : b.n;
  int carry = 0;
  for (int i = 0; i < n; i++) {
    int s = carry + (i < a.n ? a.d[i] : 0) + (i < b.n ? b.d[i] : 0);
    a.d[i] = s % 10;
    carry = s / 10;
  }
  a.n = n;
  if (carry) a.d[a.n++] = carry;
}

// a -= b, requires a >= b
static void bigSub(Big &a, const Big &b) {
  int borrow = 0;
  for (int i = 0; i < a.n; i++) {
    int s = a.d[i] - borrow - (i < b.n ? b.d[i] : 0);
    if (s < 0) { s += 10; borrow = 1; } else borrow = 0;
    a.d[i] = s;
  }
  bigTrim(a);
}

// a = a * k + add, for small k and add (0-200)
static void bigMulAddSmall(Big &a, int k, int add) {
  int carry = add;
  for (int i = 0; i < a.n; i++) {
    int s = a.d[i] * k + carry;
    a.d[i] = s % 10;
    carry = s / 10;
  }
  while (carry) {
    a.d[a.n++] = carry % 10;
    carry /= 10;
  }
  bigTrim(a);
}

// r = a * b
static void bigMul(const Big &a, const Big &b, Big &r) {
  uint32_t acc[BIG_MAX];
  int n = a.n + b.n;
  memset(acc, 0, sizeof(acc));
  for (int i = 0; i < a.n; i++)
    for (int j = 0; j < b.n; j++) acc[i + j] += a.d[i] * b.d[j];
  uint32_t carry = 0;
  for (int i = 0; i < n; i++) {
    uint32_t s = acc[i] + carry;
    r.d[i] = s % 10;
    carry = s / 10;
  }
  r.n = n;
  bigTrim(r);
}

// quot = floor(num / den), den != 0
static void bigDiv(const Big &num, const Big &den, Big &quot) {
  Big rem;
  bigZero(rem);
  quot.n = num.n;
  for (int i = num.n - 1; i >= 0; i--) {
    bigMulAddSmall(rem, 10, num.d[i]);          // bring down the next digit
    int count = 0;
    while (bigCmp(rem, den) >= 0) { bigSub(rem, den); count++; }
    quot.d[i] = count;
  }
  bigTrim(quot);
}

// root = floor(sqrt(a)), digit by digit (the pencil-and-paper method)
static void bigIsqrt(const Big &a, Big &root) {
  Big rem, t;
  bigZero(rem);
  bigZero(root);
  int pairs = (a.n + 1) / 2;
  for (int p = pairs - 1; p >= 0; p--) {
    int hi = (2 * p + 1 < a.n) ? a.d[2 * p + 1] : 0;
    int lo = a.d[2 * p];
    bigMulAddSmall(rem, 100, hi * 10 + lo);     // bring down the next pair
    int x = 9;
    for (; x > 0; x--) {                        // largest x with (20*root + x) * x <= rem
      t = root;
      bigMulAddSmall(t, 20, x);
      bigMulAddSmall(t, x, 0);
      if (bigCmp(t, rem) <= 0) break;
    }
    if (x > 0) bigSub(rem, t);
    bigMulAddSmall(root, 10, x);
  }
}

// ---------------------------------------------------------------------------
// Rounding and packing: exact value (-1)^neg * b * 10^q -> 12-digit BCD
// ---------------------------------------------------------------------------
static BcdStatus pack(bool neg, Big &b, int q, BCD &out) {
  bigTrim(b);
  if (b.n == 0) { out = bcdZero(); return BCD_OK; }

  if (b.n > BCD_DIGITS) {
    int drop = b.n - BCD_DIGITS;
    int next = b.d[drop - 1];                   // first dropped digit decides rounding
    memmove(b.d, b.d + drop, BCD_DIGITS);
    b.n = BCD_DIGITS;
    q += drop;
    if (next >= 5) {                            // round half up (away from zero)
      bigMulAddSmall(b, 1, 1);
      if (b.n > BCD_DIGITS) {                   // 999999999999 + 1: one digit longer
        memmove(b.d, b.d + 1, BCD_DIGITS);
        b.n = BCD_DIGITS;
        q += 1;
      }
    }
  } else if (b.n < BCD_DIGITS) {
    int pad = BCD_DIGITS - b.n;
    bigShift(b, pad);
    q -= pad;
  }

  int e = q + BCD_DIGITS - 1;
  if (e > BCD_EMAX) return BCD_OVERFLOW;
  if (e < BCD_EMIN) { out = bcdZero(); return BCD_OK; }   // underflow -> 0

  out.neg = neg;
  out.q = q;
  for (int i = 0; i < BCD_DIGITS; i++) out.m[i] = b.d[BCD_DIGITS - 1 - i];
  return BCD_OK;
}

// ---------------------------------------------------------------------------
// Public functions
// ---------------------------------------------------------------------------
BCD bcdZero() {
  BCD z;
  z.neg = false;
  z.q = 0;
  memset(z.m, 0, sizeof(z.m));
  return z;
}

bool bcdIsZero(const BCD &x) { return x.m[0] == 0; }

bool bcdIsNeg(const BCD &x) { return x.neg && !bcdIsZero(x); }

BCD bcdNegate(const BCD &x) {
  BCD r = x;
  if (!bcdIsZero(r)) r.neg = !r.neg;
  return r;
}

int bcdExponent(const BCD &x) {
  return bcdIsZero(x) ? 0 : x.q + BCD_DIGITS - 1;
}

BcdStatus bcdFromString(const char *s, BCD &out) {
  bool neg = false;
  if (*s == '-' || *s == '+') { neg = (*s == '-'); s++; }

  Big b;
  bigZero(b);
  int digits = 0, fracDigits = 0;
  bool seenPoint = false, seenDigit = false;
  for (; *s && *s != 'E' && *s != 'e'; s++) {
    if (*s == '.') {
      if (seenPoint) return BCD_BAD_INPUT;
      seenPoint = true;
    } else if (*s >= '0' && *s <= '9') {
      seenDigit = true;
      if (b.n == 0 && *s == '0') {              // leading zero: only shifts the point
        if (seenPoint) fracDigits++;
        continue;
      }
      if (digits >= BIG_MAX - 2) return BCD_BAD_INPUT;
      bigMulAddSmall(b, 10, *s - '0');
      digits++;
      if (seenPoint) fracDigits++;
    } else {
      return BCD_BAD_INPUT;
    }
  }
  if (!seenDigit) return BCD_BAD_INPUT;

  int exp = 0;
  if (*s == 'E' || *s == 'e') {
    s++;
    bool eneg = false;
    if (*s == '-' || *s == '+') { eneg = (*s == '-'); s++; }
    if (!(*s >= '0' && *s <= '9')) return BCD_BAD_INPUT;
    for (; *s >= '0' && *s <= '9'; s++) {
      exp = exp * 10 + (*s - '0');
      if (exp > 9999) return BCD_BAD_INPUT;
    }
    if (*s) return BCD_BAD_INPUT;
    if (eneg) exp = -exp;
  }
  return pack(neg, b, exp - fracDigits, out);
}

// a + (bNeg ? -|b| : |b|)
static BcdStatus addSigned(const BCD &a, const BCD &b, bool bNeg, BCD &out) {
  if (bcdIsZero(b)) { out = a; return BCD_OK; }
  if (bcdIsZero(a)) { out = b; out.neg = bNeg; return BCD_OK; }

  // Make x the operand with the larger exponent (both are 12-digit normalised).
  const BCD *x = &a, *y = &b;
  bool xNeg = a.neg, yNeg = bNeg;
  if (b.q > a.q) { x = &b; y = &a; xNeg = bNeg; yNeg = a.neg; }

  int diff = x->q - y->q;
  // y far below x's last digit can't change the rounded result. Any gap of
  // 14 or more is safe (the tests fail at 12); 40 leaves a wide margin.
  if (diff > 40) {
    out = *x;
    out.neg = xNeg;
    return BCD_OK;
  }

  Big X, Y;
  bigFromMant(*x, X);
  bigFromMant(*y, Y);
  bigShift(X, diff);                            // align to y's power of ten
  int q = y->q;

  if (xNeg == yNeg) {
    bigAdd(X, Y);
    return pack(xNeg, X, q, out);
  }
  int c = bigCmp(X, Y);
  if (c == 0) { out = bcdZero(); return BCD_OK; }
  if (c > 0) { bigSub(X, Y); return pack(xNeg, X, q, out); }
  bigSub(Y, X);
  return pack(yNeg, Y, q, out);
}

BcdStatus bcdAdd(const BCD &a, const BCD &b, BCD &out) {
  BCD r;
  BcdStatus st = addSigned(a, b, b.neg, r);
  if (st == BCD_OK) out = r;
  return st;
}

BcdStatus bcdSub(const BCD &a, const BCD &b, BCD &out) {
  BCD r;
  BcdStatus st = addSigned(a, b, !b.neg, r);
  if (st == BCD_OK) out = r;
  return st;
}

BcdStatus bcdMul(const BCD &a, const BCD &b, BCD &out) {
  if (bcdIsZero(a) || bcdIsZero(b)) { out = bcdZero(); return BCD_OK; }
  Big A, B, P;
  bigFromMant(a, A);
  bigFromMant(b, B);
  bigMul(A, B, P);
  BCD r;
  BcdStatus st = pack(a.neg != b.neg, P, a.q + b.q, r);
  if (st == BCD_OK) out = r;
  return st;
}

BcdStatus bcdDiv(const BCD &a, const BCD &b, BCD &out) {
  if (bcdIsZero(b)) return BCD_DIV_ZERO;
  if (bcdIsZero(a)) { out = bcdZero(); return BCD_OK; }
  Big A, B, Q;
  bigFromMant(a, A);
  bigFromMant(b, B);
  bigShift(A, 13);                              // quotient gets 13-14 digits
  bigDiv(A, B, Q);
  BCD r;
  BcdStatus st = pack(a.neg != b.neg, Q, a.q - b.q - 13, r);
  if (st == BCD_OK) out = r;
  return st;
}

BcdStatus bcdSqrt(const BCD &a, BCD &out) {
  if (bcdIsZero(a)) { out = bcdZero(); return BCD_OK; }
  if (a.neg) return BCD_NEG_SQRT;
  Big A, R;
  bigFromMant(a, A);
  int q = a.q;
  if (q & 1) { bigShift(A, 1); q -= 1; }        // make the power of ten even
  bigShift(A, 14);                              // root gets 13-14 digits
  q -= 14;
  bigIsqrt(A, R);
  BCD r;
  BcdStatus st = pack(false, R, q / 2, r);
  if (st == BCD_OK) out = r;
  return st;
}

// ---------------------------------------------------------------------------
// Text output
// ---------------------------------------------------------------------------

// Significant digits as characters, trailing zeros removed. Returns the count.
static int sigDigits(const BCD &x, char *digits) {
  int nd = BCD_DIGITS;
  while (nd > 1 && x.m[nd - 1] == 0) nd--;
  for (int i = 0; i < nd; i++) digits[i] = '0' + x.m[i];
  digits[nd] = '\0';
  return nd;
}

void bcdToSci(const BCD &x, char *out) {
  if (bcdIsZero(x)) { strcpy(out, "0"); return; }
  char digits[BCD_DIGITS + 1];
  int nd = sigDigits(x, digits);
  char *p = out;
  if (x.neg) *p++ = '-';
  *p++ = digits[0];
  if (nd > 1) {
    *p++ = '.';
    memcpy(p, digits + 1, nd - 1);
    p += nd - 1;
  }
  *p++ = 'E';
  int e = bcdExponent(x);
  if (e < 0) { *p++ = '-'; e = -e; }
  if (e >= 10) *p++ = '0' + e / 10;
  *p++ = '0' + e % 10;
  *p = '\0';
}

// Copy integer digits into out with a comma every three digits from the right.
static char *putGrouped(const char *digits, int n, char *out) {
  for (int i = 0; i < n; i++) {
    *out++ = digits[i];
    int remaining = n - i - 1;
    if (remaining > 0 && remaining % 3 == 0) *out++ = ',';
  }
  return out;
}

void bcdFormat(const BCD &x, char *out) {
  if (bcdIsZero(x)) { strcpy(out, "0"); return; }
  char digits[BCD_DIGITS + 1];
  int nd = sigDigits(x, digits);
  int e = bcdExponent(x);
  char *p = out;
  if (x.neg) *p++ = '-';

  if (e >= 0 && e < BCD_DIGITS) {
    // Fixed: e+1 integer digits, the rest after the point
    char intPart[BCD_DIGITS];
    int intLen = e + 1;
    for (int i = 0; i < intLen; i++) intPart[i] = (i < nd) ? digits[i] : '0';
    p = putGrouped(intPart, intLen, p);
    if (nd > intLen) {
      *p++ = '.';
      memcpy(p, digits + intLen, nd - intLen);
      p += nd - intLen;
    }
  } else if (e < 0 && (-e - 1 + nd) <= BCD_DIGITS) {
    // Fixed small number: 0.000ddd
    *p++ = '0';
    *p++ = '.';
    for (int i = 0; i < -e - 1; i++) *p++ = '0';
    memcpy(p, digits, nd);
    p += nd;
  } else {
    // Scientific: d.dddE-xx
    *p++ = digits[0];
    if (nd > 1) {
      *p++ = '.';
      memcpy(p, digits + 1, nd - 1);
      p += nd - 1;
    }
    *p++ = 'E';
    if (e < 0) { *p++ = '-'; e = -e; }
    if (e >= 10) *p++ = '0' + e / 10;
    *p++ = '0' + e % 10;
  }
  *p = '\0';
}
