#!/usr/bin/env python3
"""Check rpn-calculator.kicad_sch without KiCad.

Parses the file, rebuilds connectivity from the geometry (pin ends, wires,
labels, no-connect flags) and reports: unconnected pins, dangling wires,
pins of different parts touching, labels not on a wire, and the netlist.

Run:  python3 check_schematic.py [netlist.txt]
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def parse(s):
    tok, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "()":
            tok.append(c); i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            j, buf = i + 1, ""
            while s[j] != '"':
                if s[j] == "\\":
                    j += 1
                buf += s[j]; j += 1
            tok.append(("S", buf)); i = j + 1
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in '()"':
                j += 1
            tok.append(s[i:j]); i = j
    stack = [[]]
    for t in tok:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t[1] if isinstance(t, tuple) else t)
    assert len(stack) == 1 and len(stack[0]) == 1, "unbalanced parentheses"
    return stack[0][0]


def kids(node, name):
    return [k for k in node if isinstance(k, list) and k and k[0] == name]


def one(node, name):
    k = kids(node, name)
    return k[0] if k else None


def key(x, y):
    return (round(float(x) * 100), round(float(y) * 100))


def main():
    sch = parse(open(os.path.join(HERE, "rpn-calculator.kicad_sch")).read())
    assert sch[0] == "kicad_sch"
    libs = {}
    for sym in kids(one(sch, "lib_symbols"), "symbol"):
        pins = []
        for sub in kids(sym, "symbol"):
            for p in kids(sub, "pin"):
                at = one(p, "at")
                pins.append((one(p, "number")[1], float(at[1]), float(at[2])))
        libs[sym[1]] = pins

    pin_at = defaultdict(list)          # point -> [(ref, pin)]
    parts = {}
    for s in kids(sch, "symbol"):
        lib = one(s, "lib_id")[1]
        at = one(s, "at")
        X, Y, rot = float(at[1]), float(at[2]), int(at[3])
        assert rot == 0
        ref = [p[2] for p in kids(s, "property") if p[1] == "Reference"][0]
        assert ref not in parts, f"duplicate reference {ref}"
        parts[ref] = lib
        for num, px, py in libs[lib]:
            pin_at[key(X + px, Y - py)].append((ref, num))

    wires = []
    for w in kids(sch, "wire"):
        pts = one(w, "pts")
        a, b = [key(p[1], p[2]) for p in pts[1:]]
        wires.append((a, b))
    labels = defaultdict(list)
    for l in kids(sch, "label"):
        at = one(l, "at")
        labels[key(at[1], at[2])].append(l[1])
    nc = {key(n[1][1], n[1][2]) for n in kids(sch, "no_connect")}

    errors = []
    # union-find over points
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    ends = defaultdict(int)
    for a, b in wires:
        union(a, b)
        ends[a] += 1; ends[b] += 1
    for pt, lst in pin_at.items():
        if len(lst) > 1:
            errors.append(f"pins touching: {lst}")
        if pt not in ends and pt not in nc:
            errors.append(f"unconnected pin {lst}")
        if pt in ends and pt in nc:
            errors.append(f"no-connect on a wired pin {lst}")
    for pt, cnt in ends.items():
        if pt not in pin_at and pt not in labels and cnt < 2:
            errors.append(f"dangling wire end at {pt}")
    for pt, names in labels.items():
        if pt not in ends:
            errors.append(f"label {names} not on a wire")
        if len(set(names)) > 1:
            errors.append(f"two labels on one point: {names}")
    # a wire passing through a pin end (not ending there) would also connect in KiCad
    for pt in pin_at:
        for a, b in wires:
            if pt in (a, b):
                continue
            if a[0] == b[0] == pt[0] and min(a[1], b[1]) < pt[1] < max(a[1], b[1]):
                errors.append(f"wire crosses pin end {pin_at[pt]}")
            if a[1] == b[1] == pt[1] and min(a[0], b[0]) < pt[0] < max(a[0], b[0]):
                errors.append(f"wire crosses pin end {pin_at[pt]}")

    # nets: group points by component, then name by label; merge same names
    groups = defaultdict(set)
    for pt in list(parent):
        groups[find(pt)].add(pt)
    nets = defaultdict(set)
    for g in groups.values():
        names = {nm for pt in g for nm in labels.get(pt, [])}
        if len(names) != 1:
            errors.append(f"wire group with labels {names}")
            continue
        name = names.pop()
        for pt in g:
            for ref, num in pin_at.get(pt, []):
                nets[name].add((ref, num))

    real = {n: sorted(m) for n, m in nets.items()
            if any(not r.startswith("#") for r, _ in m)}
    for n, m in real.items():
        if len([1 for r, _ in m if not r.startswith("#")]) < 2:
            errors.append(f"net {n} has only one pin: {m}")

    print(f"{len(parts)} symbols, {len(wires)} wires, {sum(map(len, labels.values()))} labels, "
          f"{len(nc)} no-connects, {len(real)} nets")
    for e in errors:
        print("ERROR:", e)
    if len(sys.argv) > 1:
        def nat(p):
            r, n = p
            pre = r.rstrip("0123456789")
            return (pre, int(r[len(pre):] or 0), n)
        with open(sys.argv[1], "w") as fh:
            for n in sorted(real):
                fh.write(f"{n}: " + ", ".join(f"{r}.{p}" for r, p in sorted(real[n], key=nat)
                                               if not r.startswith("#")) + "\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
