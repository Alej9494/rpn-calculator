BCD tests (run on a computer, not the Nucleo)

1. python3 gen_vectors.py          (writes vectors.txt, about 265,000 cases)
2. g++ -std=c++17 -O2 -I.. bcd_test.cpp ../bcd.cpp -o bcd_test
3. ./bcd_test                      (prints cases and failures per operation)

The expected results come from Python's decimal module: 12 digits,
ROUND_HALF_UP, overflow above 9.99999999999E99, underflow below 1E-99 to 0.
Arduino ignores this folder when it builds the sketch.
