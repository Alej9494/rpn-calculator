// bcd.h - 12-digit decimal (BCD) arithmetic for the RPN calculator.
//
// A number is stored as a sign, 12 decimal digits and a power of ten:
//     value = (-1)^neg * M * 10^q,  M = m[0] m[1] ... m[11] read as an integer.
// M is always normalised so m[0] != 0, except for zero (all digits 0, q = 0).
// The scientific exponent shown on screen is E = q + 11, kept within -99..99.
//
// Every result is the exact answer rounded half-up to 12 significant digits,
// the same as Python's decimal module with prec=12 and ROUND_HALF_UP.
// Results with E > 99 are an overflow error; results below 1E-99 become 0.

#pragma once
#include <stdint.h>

#define BCD_DIGITS 12
#define BCD_EMAX 99
#define BCD_EMIN (-99)

struct BCD {
  bool neg;                     // true for negative numbers (never for zero)
  int16_t q;                    // power of ten applied to the 12-digit integer
  uint8_t m[BCD_DIGITS];        // digits, most significant first, 0-9 each
};

enum BcdStatus : uint8_t {
  BCD_OK = 0,
  BCD_OVERFLOW,                 // result above 9.99999999999E99
  BCD_DIV_ZERO,                 // division by zero
  BCD_NEG_SQRT,                 // square root of a negative number
  BCD_BAD_INPUT                 // text could not be read as a number
};

BCD bcdZero();
bool bcdIsZero(const BCD &x);
bool bcdIsNeg(const BCD &x);                    // strictly negative
BCD bcdNegate(const BCD &x);
int bcdExponent(const BCD &x);                  // scientific exponent E (0 for zero)

// Read "-12.5", "007", ".5", "1.5E-7" and similar. More than 12 significant
// digits are rounded half-up.
BcdStatus bcdFromString(const char *s, BCD &out);

// out = a op b. On an error, out is left unchanged.
BcdStatus bcdAdd(const BCD &a, const BCD &b, BCD &out);
BcdStatus bcdSub(const BCD &a, const BCD &b, BCD &out);
BcdStatus bcdMul(const BCD &a, const BCD &b, BCD &out);
BcdStatus bcdDiv(const BCD &a, const BCD &b, BCD &out);
BcdStatus bcdSqrt(const BCD &a, BCD &out);

// Canonical scientific text, e.g. "-1.2345E-5", "1E0", "0". Buffer >= 24 chars.
void bcdToSci(const BCD &x, char *out);

// Display text per the spec: up to 12 significant digits, trailing zeros
// removed, thousands grouped, scientific when it won't fit. Buffer >= 32 chars.
void bcdFormat(const BCD &x, char *out);
