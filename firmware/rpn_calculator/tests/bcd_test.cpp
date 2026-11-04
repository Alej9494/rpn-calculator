// bcd_test.cpp - runs every vector in vectors.txt through bcd.cpp and
// compares with Python's decimal results. Build and run on a computer:
//   python3 gen_vectors.py
//   g++ -std=c++17 -O2 -Wall -I.. bcd_test.cpp ../bcd.cpp -o bcd_test && ./bcd_test

#include "bcd.h"
#include <cstdio>
#include <cstring>
#include <map>
#include <string>

static std::string statusText(BcdStatus st, const BCD &r) {
  switch (st) {
    case BCD_OK: { char buf[32]; bcdToSci(r, buf); return buf; }
    case BCD_OVERFLOW: return "OVF";
    case BCD_DIV_ZERO: return "DIV0";
    case BCD_NEG_SQRT: return "NEGSQRT";
    default: return "BADINPUT";
  }
}

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "vectors.txt";
  FILE *f = fopen(path, "r");
  if (!f) { printf("cannot open %s\n", path); return 2; }

  std::map<std::string, int> total, failed;
  char op[16], a[64], b[64], expect[64];
  int shown = 0;
  while (fscanf(f, "%15s %63s %63s %63s", op, a, b, expect) == 4) {
    std::string got;
    BCD x, y, r = bcdZero();
    if (!strcmp(op, "parse")) {
      got = statusText(bcdFromString(a, r), r);
    } else {
      if (bcdFromString(a, x) != BCD_OK) { printf("bad input %s\n", a); return 2; }
      if (strcmp(b, "-") && bcdFromString(b, y) != BCD_OK) { printf("bad input %s\n", b); return 2; }
      BcdStatus st = BCD_OK;
      if (!strcmp(op, "add")) st = bcdAdd(x, y, r);
      else if (!strcmp(op, "sub")) st = bcdSub(x, y, r);
      else if (!strcmp(op, "mul")) st = bcdMul(x, y, r);
      else if (!strcmp(op, "div")) st = bcdDiv(x, y, r);
      else if (!strcmp(op, "sqrt")) st = bcdSqrt(x, r);
      else if (!strcmp(op, "fmt")) { char buf[40]; bcdFormat(x, buf); got = buf; }
      if (strcmp(op, "fmt")) got = statusText(st, r);
    }
    total[op]++;
    if (got != expect) {
      failed[op]++;
      if (shown++ < 25) printf("FAIL %s %s %s: expected %s, got %s\n", op, a, b, expect, got.c_str());
    }
  }
  fclose(f);

  int all = 0, bad = 0;
  for (auto &t : total) {
    printf("%-6s %7d cases, %d failed\n", t.first.c_str(), t.second, failed[t.first]);
    all += t.second;
    bad += failed[t.first];
  }
  printf("TOTAL  %7d cases, %d failed\n", all, bad);
  return bad ? 1 : 0;
}
