#!/usr/bin/env python3
"""Generate BCD test vectors with Python's decimal module as the reference.

Reference rules (match the spec):
  - every result rounded half-up to 12 significant digits
  - scientific exponent above 99 -> OVF (overflow error)
  - result below 1E-99 -> 0
  - division by zero -> DIV0, square root of a negative -> NEGSQRT

Writes vectors.txt with one case per line:
  op  a  b  expected        (b is '-' for sqrt, fmt, parse)
"""
import random
import sys
from decimal import Decimal, Context, ROUND_HALF_UP

CTX = Context(prec=12, rounding=ROUND_HALF_UP, Emax=999999, Emin=-999999)
EXACT = Context(prec=200, rounding=ROUND_HALF_UP, Emax=999999, Emin=-999999)


def canon(d):
    """Canonical text for a 12-digit result, or OVF / 0 by the spec's rules."""
    if d == 0:
        return "0"
    if d.adjusted() > 99:
        return "OVF"
    if d.adjusted() < -99:
        return "0"
    sign, digits, _ = d.as_tuple()
    ds = "".join(map(str, digits)).rstrip("0") or "0"
    s = ("-" if sign else "") + ds[0]
    if len(ds) > 1:
        s += "." + ds[1:]
    return s + "E" + str(d.adjusted())


def rnd(x):
    """Round an exact Decimal to the 12-digit result."""
    return CTX.plus(x)


def num_text(d):
    """Canonical input text for an exact Decimal that is a valid 12-digit BCD."""
    return canon(d)


def rand_num(rng, emin=-99, emax=99, ndigits=None, sign=None):
    n = ndigits or rng.choice([1, 1, 2, 3, 6, 12, 12, 12, 12])
    digits = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(n - 1))
    e = rng.randint(emin, emax)
    s = sign if sign is not None else rng.choice(["", "-"])
    return Decimal(f"{s}{digits[0]}.{digits[1:] or '0'}E{e}")


def near(rng, a):
    """A number close to a: same exponent, a few last-digit changes."""
    sign, digits, exp = a.as_tuple()
    digs = list(digits) + [0] * (12 - len(digits))
    digs = digs[:12]
    exp = a.adjusted() - 11
    k = rng.randint(1, 4)
    for _ in range(k):
        i = rng.randint(6, 11)
        digs[i] = rng.randint(0, 9)
    if digs[0] == 0:
        digs[0] = 1
    if rng.random() < 0.5:
        sign = 1 - sign
    return Decimal((sign, tuple(digs), exp))


def special_numbers():
    vals = ["0", "1", "-1", "2", "3", "0.5", "0.1", "0.2", "0.3", "10", "100",
            "999999999999", "9.99999999999E99", "-9.99999999999E99", "1E99", "1E-99",
            "-1E-99", "1.00000000001", "0.99999999999", "5E-100", "1.23456789012",
            "123456789012", "0.000000000001", "4", "9", "16", "1E12", "1E11",
            "5.55555555555", "4.44444444445", "1.5", "2.5", "-2.5", "7", "6E50", "2E-50"]
    out = []
    for v in vals:
        d = Decimal(v)
        if canon(d) not in ("OVF",) and (d == 0 or d.adjusted() >= -99):
            out.append(d)
    return out


def main(n_per_op=40000, seed=12345):
    rng = random.Random(seed)
    lines = []

    def valid(d):
        # an input must be a 12-digit number inside the calculator's range
        return d is None or d == 0 or (-99 <= d.adjusted() <= 99 and rnd(d) == d)

    def add_case(op, a, b, expected):
        if not (valid(a) and valid(b)):
            return
        lines.append(f"{op} {num_text(a)} {num_text(b) if b is not None else '-'} {expected}")

    specials = special_numbers()

    # ----- add / sub -----
    for op in ("add", "sub"):
        for a in specials:
            for b in specials:
                exact = EXACT.add(a, b) if op == "add" else EXACT.subtract(a, b)
                add_case(op, a, b, canon(rnd(exact)))
        for i in range(n_per_op):
            r = rng.random()
            a = rand_num(rng)
            if r < 0.35:     # similar size: carries and borrows
                b = rand_num(rng, a.adjusted() - 3, a.adjusted() + 3)
            elif r < 0.55:   # nearly equal: heavy cancellation
                b = near(rng, a)
            elif r < 0.75:   # alignment gaps around the 12-digit edge and the 40-digit cut-off
                gap = rng.choice([11, 12, 13, 14, 15, 25, 38, 39, 40, 41, 42, 60])
                e = a.adjusted() - gap
                if e < -99:
                    e = -99
                b = rand_num(rng, e, e)
            elif r < 0.85:   # near the top of the range: overflow by carry
                a = rand_num(rng, 97, 99, ndigits=12)
                b = rand_num(rng, 85, 99)
            else:            # anything
                b = rand_num(rng)
            exact = EXACT.add(a, b) if op == "add" else EXACT.subtract(a, b)
            add_case(op, a, b, canon(rnd(exact)))

    # A tiny number taken off an exact power of ten (1E10 - 3E-3) drops the
    # result's exponent by one, so digits far below the last place can still
    # change the rounding. Random cases rarely hit this, so aim at it directly.
    for i in range(n_per_op // 4):
        k = rng.randint(-50, 50)
        x = Decimal(rng.choice(["1", "1.00000000001", "1.0000000001"])) * Decimal(f"1E{k}")
        gap = rng.randint(11, 45)
        y = rand_num(rng, k - gap, k - gap, ndigits=rng.choice([1, 6, 12]), sign="")
        if rng.random() < 0.5:
            x = -x
        else:
            y = -y
        # x and y have opposite signs: add them, or subtract the mirrored pair
        add_case("add", x, y, canon(rnd(EXACT.add(x, y))))
        add_case("sub", x, -y, canon(rnd(EXACT.subtract(x, -y))))
        add_case("add", y, x, canon(rnd(EXACT.add(y, x))))

    # ----- mul -----
    for a in specials:
        for b in specials:
            add_case("mul", a, b, canon(rnd(EXACT.multiply(a, b))))
    for i in range(n_per_op):
        r = rng.random()
        if r < 0.6:
            a, b = rand_num(rng, -20, 20), rand_num(rng, -20, 20)
        elif r < 0.8:   # overflow / underflow edges
            if rng.random() < 0.5:
                a, b = rand_num(rng, 40, 99), rand_num(rng, 40, 60)
            else:
                a, b = rand_num(rng, -99, -40), rand_num(rng, -60, -40)
        else:
            a, b = rand_num(rng), rand_num(rng)
        add_case("mul", a, b, canon(rnd(EXACT.multiply(a, b))))

    # ----- div -----
    for a in specials:
        for b in specials:
            if b == 0:
                add_case("div", a, b, "DIV0")
            else:
                add_case("div", a, b, canon(rnd(EXACT.divide(a, b))))
    for i in range(n_per_op):
        r = rng.random()
        if r < 0.6:
            a, b = rand_num(rng, -20, 20), rand_num(rng, -20, 20)
        elif r < 0.7:   # exact quotients and simple fractions
            b = rand_num(rng, -3, 3, ndigits=rng.choice([1, 2, 3]))
            a = rnd(b * rand_num(rng, -3, 3, ndigits=rng.choice([1, 2, 3, 6])))
        elif r < 0.85:  # overflow / underflow edges
            if rng.random() < 0.5:
                a, b = rand_num(rng, 50, 99), rand_num(rng, -60, -1)
            else:
                a, b = rand_num(rng, -99, -50), rand_num(rng, 1, 60)
        else:
            a, b = rand_num(rng), rand_num(rng)
        # exact division to 200 digits, then round: half-up ties land exactly
        add_case("div", a, b, canon(rnd(EXACT.divide(a, b))))

    # ----- sqrt -----
    for a in specials:
        if a < 0:
            add_case("sqrt", a, None, "NEGSQRT")
        else:
            add_case("sqrt", a, None, canon(rnd(EXACT.sqrt(a))))
    for i in range(n_per_op):
        r = rng.random()
        if r < 0.1:      # perfect squares
            k = rand_num(rng, -45, 45, ndigits=rng.choice([1, 2, 3, 6]), sign="")
            a = rnd(k * k)
        elif r < 0.15:
            a = rand_num(rng, sign="-")
        else:
            a = rand_num(rng, sign="")
        if a < 0:
            add_case("sqrt", a, None, "NEGSQRT")
        else:
            add_case("sqrt", a, None, canon(rnd(EXACT.sqrt(a))))

    # ----- parse: typed entries as the keypad produces them -----
    for i in range(n_per_op // 4):
        nd = rng.randint(1, 12)
        digits = "".join(str(rng.randint(0, 9)) for _ in range(nd))
        if rng.random() < 0.3:
            digits = "0" * rng.randint(1, 3) + digits
        if rng.random() < 0.6:
            p = rng.randint(0, len(digits))
            text = digits[:p] + "." + digits[p:]
            if text.startswith("."):
                text = "0" + text
        else:
            text = digits
        if rng.random() < 0.3:
            text = "-" + text
        d = Decimal(text)
        lines.append(f"parse {text} - {canon(rnd(d))}")

    # ----- fmt: display formatting against an independent implementation -----
    for i in range(n_per_op // 2):
        r = rng.random()
        if r < 0.6:
            a = rand_num(rng, -14, 14)
        else:
            a = rand_num(rng)
        lines.append(f"fmt {num_text(a)} - {fmt_ref(a)}")
    for a in specials:
        lines.append(f"fmt {num_text(a)} - {fmt_ref(a)}")

    with open("vectors.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(lines)} vectors written")


def fmt_ref(d):
    """Display rules from the spec, written independently of the C code."""
    if d == 0:
        return "0"
    d = rnd(d)
    sign, digits, _ = d.as_tuple()
    ds = "".join(map(str, digits)).rstrip("0") or "0"
    e = d.adjusted()
    neg = "-" if sign else ""
    if 0 <= e < 12:
        int_part = (ds + "0" * 12)[: e + 1]
        frac = ds[e + 1:]
        grouped = f"{int(int_part):,}"
        return neg + grouped + ("." + frac if frac else "")
    if e < 0 and (-e - 1 + len(ds)) <= 12:
        return neg + "0." + "0" * (-e - 1) + ds
    return neg + ds[0] + ("." + ds[1:] if len(ds) > 1 else "") + "E" + str(e)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
    main(n)
