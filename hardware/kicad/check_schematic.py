#!/usr/bin/env python3
"""Check rpn-calculator.kicad_sch without KiCad.

Reads the file itself (not the generator), rebuilds the connectivity the way
KiCad does (wire ends, pin ends, labels, GND symbols, junctions) and compares
it with netlist.py. Also reports unconnected pins, dangling wires, T-joins
without a junction dot and wires that pass over a pin.

Run:  python3 check_schematic.py
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from netlist import PARTS  # noqa: E402


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


def pt(x, y):
    return (round(float(x), 2), round(float(y), 2))


def main():
    sch = parse(open(os.path.join(HERE, "rpn-calculator.kicad_sch")).read())
    assert sch[0] == "kicad_sch"
    libs = {}
    for sym in kids(one(sch, "lib_symbols"), "symbol"):
        pins = []
        for sub in kids(sym, "symbol"):
            for p in kids(sub, "pin"):
                at = one(p, "at")
                pins.append((one(p, "number")[1], p[1], float(at[1]), float(at[2])))
        libs[sym[1]] = dict(pins=pins, power=any(k == ["power"] for k in sym))

    errors = []
    pin_at = defaultdict(list)
    ptype, refs, power_pts = {}, {}, []
    for s in kids(sch, "symbol"):
        lib = one(s, "lib_id")[1]
        at = one(s, "at")
        X, Y, rot = float(at[1]), float(at[2]), int(at[3])
        props = {p[1]: p[2] for p in kids(s, "property")}
        ref = props["Reference"]
        if libs[lib]["power"]:
            power_pts.append((props["Value"], pt(X, Y)))
            continue
        assert ref not in refs, f"duplicate reference {ref}"
        refs[ref] = lib
        for num, typ, px, py in libs[lib]["pins"]:
            if rot == 0:
                p = pt(X + px, Y - py)
            elif rot == 180:
                p = pt(X - px, Y + py)
            else:
                raise SystemExit(f"{ref}: rotation {rot} not handled")
            pin_at[p].append((ref, num))
            ptype[(ref, num)] = typ

    segs = []
    for w in kids(sch, "wire"):
        pts = one(w, "pts")
        a, b = [pt(p[1], p[2]) for p in pts[1:]]
        if a[0] != b[0] and a[1] != b[1]:
            errors.append(f"diagonal wire {a} {b}")
        segs.append((a, b))
    labels = defaultdict(list)
    for l in kids(sch, "label"):
        at = one(l, "at")
        labels[pt(at[1], at[2])].append(l[1])
    juncs = {pt(*one(j, "at")[1:3]) for j in kids(sch, "junction")}
    ncs = {pt(*one(n, "at")[1:3]) for n in kids(sch, "no_connect")}

    ends = defaultdict(int)
    for a, b in segs:
        ends[a] += 1; ends[b] += 1
    power_set = {p for _, p in power_pts}

    def on_interior(p, a, b):
        if a[0] == b[0] == p[0]:
            return min(a[1], b[1]) < p[1] < max(a[1], b[1])
        if a[1] == b[1] == p[1]:
            return min(a[0], b[0]) < p[0] < max(a[0], b[0])
        return False

    # anything that would connect mid-wire must have been split by the generator
    probe = set(ends) | set(pin_at) | set(labels) | power_set
    for p in probe:
        for a, b in segs:
            if on_interior(p, a, b):
                errors.append(f"{pin_at.get(p) or labels.get(p) or 'wire end'} at {p} sits mid-wire")
    for p, n in ends.items():
        items = n + len(pin_at.get(p, [])) + (1 if p in power_set else 0)
        if items >= 3 and p not in juncs:
            errors.append(f"join without a junction dot at {p}")
        if n == 1 and p not in pin_at and p not in labels and p not in power_set:
            errors.append(f"dangling wire end at {p}")
    for p in juncs:
        if ends.get(p, 0) + len(pin_at.get(p, [])) + (1 if p in power_set else 0) < 3:
            errors.append(f"junction dot with nothing to join at {p}")
    for p, lst in pin_at.items():
        if len(lst) > 1:
            errors.append(f"pins on top of each other: {lst}")
        connected = p in ends or p in power_set
        for k in lst:
            if p in ncs and connected:
                errors.append(f"no-connect flag on a connected pin {k}")
            if not connected and p not in ncs and ptype[k] != "no_connect":
                errors.append(f"unconnected pin {k}")

    # connectivity
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for a, b in segs:
        union(a, b)
    for p, lst in pin_at.items():
        for k in lst:
            union(("pin",) + k, p)
    for name, p in power_pts:
        if name != "PWR_FLAG":          # PWR_FLAG only marks a source for ERC
            union(("net", name), p)
        else:
            find(p)
    for p, names in labels.items():
        for nm in names:
            union(("net", nm), p)

    expect = defaultdict(set)
    for ref, part in PARTS.items():
        if ref not in refs:
            errors.append(f"{ref} missing from the schematic")
        for num, net in part["nets"].items():
            expect[net].add((ref, num))
    owner = {}
    for net, pins in sorted(expect.items()):
        roots = {find(("pin",) + k) for k in pins}
        if len(roots) > 1:
            errors.append(f"net {net} is in {len(roots)} pieces")
        for r in roots:
            if r in owner:
                errors.append(f"nets {owner[r]} and {net} are joined")
            owner[r] = net
    for ref, lib in refs.items():
        for num, *_ in libs[lib]["pins"]:
            if num not in PARTS[ref]["nets"] and find(("pin", ref, num)) in owner:
                errors.append(f"{ref}.{num} should be unconnected")
    for p, names in labels.items():
        for nm in names:
            if owner.get(find(p)) != nm:
                errors.append(f"label {nm} is on net {owner.get(find(p))}")

    print(f"{len(refs)} parts, {len(segs)} wires, {len(juncs)} junctions, "
          f"{len(power_pts)} power symbols, {len(ncs)} no-connects, {len(expect)} nets checked")
    for e in errors:
        print("ERROR:", e)
    if not errors:
        print("Matches netlist.py: every net complete, no extra joins.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
