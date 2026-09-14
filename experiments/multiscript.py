#!/usr/bin/env python3
"""Multi-script variant of babel42: characters instead of pixels, drawn from several
alphabets (Latin, Czech, Greek, mathematical operators, digits) and placed at random
positions in a 42-cell field, most cells left blank.

Measures three things:
  1. how big the space is for each alphabet and sparsity
  2. how often a uniformly random sparse field contains a well-formed expression
  3. how often a grammar-constrained draw contains a non-trivial one

Run:  python3 multiscript.py
"""
import hashlib, json, math, os, random, re, sys, time

WIDTH = 42
BLANK = " "

LATIN = "abcdefghijklmnopqrstuvwxyz"
CZECH = "áčďéěíňóřšťúůýž"
GREEK = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_UP = "ΓΔΘΛΞΠΣΦΨΩ"
DIGITS = "0123456789"
MATHOPS = "+-*/=<>()^"
MATHSYM = "√∫∑∏∞±≈≠≤≥∂∇∈∀∃⇒↔·°"
SUPER = "²³"

SETS = {
    "latin_en": LATIN,
    "latin_cs": LATIN + CZECH,
    "greek": GREEK + GREEK_UP,
    "math": DIGITS + MATHOPS + MATHSYM + SUPER,
    "mixed_all": LATIN + CZECH + GREEK + GREEK_UP + DIGITS + MATHOPS + MATHSYM + SUPER,
}

# ---------------------------------------------------------------- addressing
def sparse_field(alphabet, key, counter, k):
    """Deterministic sparse field: k characters at k random positions of WIDTH cells."""
    cells = [BLANK] * WIDTH
    need = 3 * k + 8
    buf = b""
    block = 0
    while len(buf) < need:
        buf += hashlib.blake2b(counter.to_bytes(8, "big") + block.to_bytes(2, "big"),
                               key=key, digest_size=64).digest()
        block += 1
    idx = 0
    used = set()
    for _ in range(k):
        while True:
            p = ((buf[idx] << 8) | buf[idx + 1]) % WIDTH
            idx += 2
            if p not in used:
                used.add(p)
                break
        cells[p] = alphabet[buf[idx] % len(alphabet)]
        idx += 1
    return "".join(cells)


def runs(field, minlen=3):
    return [r for r in field.split(BLANK) if len(r) >= minlen]


# ---------------------------------------------------------------- expression check
TOKEN = re.compile(r"\d+|[a-zαβγδεθλμπστφω]|[√∫∑∏∂∇]|[+\-*/^]|[=<>≈≠≤≥]|[()]|[²³]|[∞π±]")
CONST = {"π": math.pi, "∞": float("inf"), "e": math.e}
OPS = set("+-*/^")


def wellformed(run):
    """Cheap grammar check: alternating operand/operator, balanced brackets,
    at least two operators, and a finite numeric value."""
    toks = TOKEN.findall(run)
    if len("".join(toks)) < len(run):          # unknown characters present
        return None
    if sum(t in OPS for t in toks) < 2:
        return None
    depth = 0
    for t in toks:
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
            if depth < 0:
                return None
    if depth:
        return None
    expr = []
    for t in toks:
        if t == "^":
            expr.append("**")
        elif t == "²":
            expr.append("**2")
        elif t == "³":
            expr.append("**3")
        elif t == "π":
            expr.append("math.pi")
        elif t in "√∫∑∏∂∇∞±=<>≈≠≤≥":
            return None                        # needs a real grammar, not eval
        elif t.isalpha():
            expr.append("1.5")                 # bind free variables to a probe value
        else:
            expr.append(t)
    src = "".join(expr)
    try:
        v = eval(src, {"math": math, "__builtins__": {}})
    except Exception:
        return None
    if not isinstance(v, (int, float)) or v != v or abs(v) == float("inf"):
        return None
    return round(float(v), 9)


def script_of(ch):
    o = ord(ch)
    if ch in LATIN:
        return "latin"
    if ch in CZECH:
        return "czech"
    if 0x370 <= o <= 0x3FF:
        return "greek"
    if ch in DIGITS or ch in MATHOPS or ch in MATHSYM or ch in SUPER:
        return "math"
    return "other"


def coherent(run):
    """Cheapest possible filter: a run must stay inside one script, or inside the
    legitimate mixture {latin, greek, math} that real formulas use."""
    s = {script_of(c) for c in run}
    return len(s) == 1 or s <= {"latin", "greek", "math"}


# ---------------------------------------------------------------- 1. the counting
def counting():
    print("space size, 42 cells, k characters placed at random positions\n")
    print(f"{'alphabet':10} {'|A|':>4}  " + "  ".join(f"k={k:<2}" for k in (4, 6, 8, 12, 42)))
    for name, alpha in SETS.items():
        row = []
        for k in (4, 6, 8, 12, 42):
            k = min(k, WIDTH)
            pos = math.lgamma(WIDTH + 1) - math.lgamma(k + 1) - math.lgamma(WIDTH - k + 1)
            log10 = pos / math.log(10) + k * math.log10(len(alpha))
            row.append(f"10^{log10:5.1f}")
        print(f"{name:10} {len(alpha):>4}  " + "  ".join(row))
    print()


# ---------------------------------------------------------------- 2. uniform draw
def uniform_trial(n=200000, k=8, alphabet_name="mixed_all", seconds=25):
    alpha = SETS[alphabet_name]
    key = os.urandom(16)
    t0 = time.time()
    seen = coh = wf = 0
    hits = []
    for c in range(n):
        f = sparse_field(alpha, key, c, k)
        for r in runs(f):
            seen += 1
            if not coherent(r):
                continue
            coh += 1
            v = wellformed(r)
            if v is None:
                continue
            wf += 1
            hits.append((r, v, c))
            ledger({"kind": "expression", "alphabet": alphabet_name, "k": k,
                    "key": key.hex(), "counter": c, "text": r, "value": v,
                    "codepoints": [hex(ord(ch)) for ch in r]})
        if time.time() - t0 > seconds:
            n = c + 1
            break
    el = time.time() - t0
    print(f"uniform draw, alphabet={alphabet_name} (|A|={len(alpha)}), k={k}, "
          f"{n:,} fields in {el:.0f}s ({n/el:,.0f}/s)")
    print(f"  runs of 3+ chars      : {seen:,}")
    print(f"  script-coherent       : {coh:,}  ({coh/max(seen,1):.4%})")
    print(f"  well-formed expression: {wf:,}  ({wf/max(seen,1):.6%} of runs, "
          f"{wf/max(n,1):.6%} per field)")
    for h in hits[:10]:
        print(f"     {h[0]!r} = {h[1]}   at counter {h[2]}")
    print()
    return wf, n


# ---------------------------------------------------------------- 3. grammar draw
ATOMS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "π", "e", "√2", "√3", "√5"]
BINOPS = ["+", "-", "*", "/"]
TARGETS = {"π": math.pi, "e": math.e, "√2": math.sqrt(2), "φ": (1 + math.sqrt(5)) / 2,
           "ln2": math.log(2), "γ": 0.5772156649015329, "ζ(3)": 1.2020569031595943,
           "π²/6": math.pi ** 2 / 6, "√π": math.sqrt(math.pi), "π/e": math.pi / math.e}
VAL = {"π": math.pi, "e": math.e, "√2": math.sqrt(2), "√3": math.sqrt(3), "√5": math.sqrt(5)}


def grammar_draw(rng, depth=0):
    """Every draw is well-formed by construction: the randomness sits in the
    derivation, not in the characters."""
    if depth >= 2 or rng.random() < 0.35:
        a = rng.choice(ATOMS)
        return a, VAL.get(a, float(a) if a[0].isdigit() else 0.0)
    ls, lv = grammar_draw(rng, depth + 1)
    rs, rv = grammar_draw(rng, depth + 1)
    op = rng.choice(BINOPS)
    try:
        v = {"+": lv + rv, "-": lv - rv, "*": lv * rv,
             "/": lv / rv if rv else None}[op]
    except Exception:
        v = None
    if v is None:
        return ls, lv
    s = f"({ls}{op}{rs})"
    if rng.random() < 0.15:
        if v >= 0:
            return f"√{s}", math.sqrt(v)
        return s, v
    return s, v


def grammar_trial(n=400000, seconds=25):
    rng = random.Random(20260914)
    t0 = time.time()
    exact = nontrivial = 0
    show = []
    for i in range(n):
        s, v = grammar_draw(rng)
        if v is None or v != v or abs(v) == float("inf"):
            continue
        for name, t in TARGETS.items():
            if t and abs(v - t) < 1e-9:
                exact += 1
                atom = {"π": "π", "e": "e", "√2": "2", "φ": "5", "ln2": None,
                        "γ": None, "ζ(3)": None, "π²/6": "π", "√π": "π",
                        "π/e": "π"}.get(name)
                if atom and atom in s:
                    break                      # restatement of the target itself
                nontrivial += 1
                ledger({"kind": "identity", "constant": name, "expression": s,
                        "value": v})
                if len(show) < 10:
                    show.append((name, s, v))
                break
        if time.time() - t0 > seconds:
            n = i + 1
            break
    el = time.time() - t0
    print(f"grammar-constrained draw, {n:,} expressions in {el:.0f}s ({n/el:,.0f}/s)")
    print(f"  numerically equal to a named constant : {exact:,} ({exact/n:.4%})")
    print(f"  after removing self-restatements      : {nontrivial:,} ({nontrivial/n:.4%})")
    for name, s, v in show:
        print(f"     {name} = {s} = {v}")
    print()


LEDGER = [None]


def ledger(rec):
    """Append one find as a JSON line. Nothing is written unless --ledger is on."""
    path = LEDGER[0]
    if not path:
        return
    rec = dict(rec)
    rec["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def resolve(spec):
    """'greek', 'greek+math', or a literal string of characters."""
    if spec in SETS:
        return SETS[spec], spec
    parts = spec.split("+")
    if all(p in SETS for p in parts):
        seen = ""
        for p in parts:
            for c in SETS[p]:
                if c not in seen:
                    seen += c
        return seen, spec
    return spec, "custom"


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="multi-script 42-cell fields")
    p.add_argument("--alphabet", default=None,
                   help="named set, sets joined with '+', or literal characters")
    p.add_argument("--k", type=int, default=8, help="cells filled, 1..42")
    p.add_argument("--seconds", type=float, default=10)
    p.add_argument("--list", action="store_true", help="show the named sets and exit")
    p.add_argument("--grammar", action="store_true", help="run the grammar draw too")
    p.add_argument("--ledger", default="multiscript-finds.jsonl",
                   help="append finds to this JSON-lines file")
    p.add_argument("--no-ledger", dest="ledger", action="store_const", const=None)
    a = p.parse_args()

    LEDGER[0] = a.ledger
    if a.ledger:
        print(f"ledger: {a.ledger}")

    if a.list:
        for name, alpha in SETS.items():
            print(f"{name:10} {len(alpha):>4}  {alpha}")
        raise SystemExit

    if a.alphabet is None:
        counting()
        uniform_trial(k=8, alphabet_name="mixed_all", seconds=a.seconds)
        uniform_trial(k=8, alphabet_name="math", seconds=a.seconds)
        grammar_trial(seconds=a.seconds)
    else:
        alpha, label = resolve(a.alphabet)
        SETS[label] = alpha
        print(f"alphabet {label} (|A|={len(alpha)}): {alpha}")
        pos = math.lgamma(WIDTH + 1) - math.lgamma(a.k + 1) - math.lgamma(WIDTH - a.k + 1)
        print(f"space with {a.k} of {WIDTH} cells filled: "
              f"10^{pos/math.log(10) + a.k*math.log10(len(alpha)):.1f}\n")
        uniform_trial(n=10**9, k=a.k, alphabet_name=label, seconds=a.seconds)
        if a.grammar:
            grammar_trial(seconds=a.seconds)
