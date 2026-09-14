#!/usr/bin/env python3
"""pixels42 - the pixel variant, drawn live in the terminal as dots.

A 42 x 42 bitmap is produced from a keyed hash of a counter, exactly like the text and
music variants, so every frame has an address of the form key:counter. Each field is
scored for the three cheapest signs of structure - mirror symmetry, one large connected
blob, and a sane amount of ink - and the best field seen so far is held on screen beside
the live one.

Drawing is deliberately rare: the search runs at whatever rate the machine allows, the
screen is repainted only a few times a second, and a duty cycle keeps the process off the
CPU. That is what makes it usable as a screensaver rather than a heater.

    python3 pixels42.py                 live, ~8 frames a second, ~15 % of one core
    python3 pixels42.py --fps 4 --cpu 8 slower and lighter
    python3 pixels42.py --render half   half-block pixels instead of braille dots
    python3 pixels42.py --frames 3      print a few frames and exit (no live screen)
    python3 pixels42.py --verify KEY:N  redraw one field from its address
"""
import argparse, hashlib, json, os, sys, time

SIDE = 42          # default grid, kept as the working version
W = H = SIDE       # set by --grid; 42 x 42 reproduces every earlier address
BRAILLE = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


# --------------------------------------------------------------- the field
_TABLES = {}


def field(key, counter, ink=0.30):
    """W x H bits as H rows of bytes, one keyed hash call per field."""
    table = _TABLES.get(ink)
    if table is None:
        thr = int(255 * ink)
        table = _TABLES[ink] = bytes(1 if i <= thr else 0 for i in range(256))
    flat = hashlib.shake_256(key + counter.to_bytes(8, "big")).digest(
        W * H).translate(table)
    return [flat[r * W:(r + 1) * W] for r in range(H)]


def pattern(index):
    """The index-th bitmap of the 2^(W*H) that exist - for small grids only.

    Plain counting is useless to watch: the first billions of patterns all have empty
    top rows, because the low bits move first. Multiplying by an odd constant modulo
    2^(W*H) is a full-cycle permutation, so every bitmap is still visited exactly once
    but consecutive ones look unrelated.
    """
    n = W * H
    index = (index * 0x9E3779B97F4A7C15) % (1 << n)
    bits = bin(index)[2:].rjust(n, "0")
    flat = bytes(1 if c == "1" else 0 for c in bits)
    return [flat[r * W:(r + 1) * W] for r in range(H)]


# --------------------------------------------------------------- the screen
def symmetry(rows):
    """Fraction of cells matching their mirror image about the vertical axis."""
    h = W // 2
    if h == 0:
        return 1.0
    same = 0
    for r in rows:
        same += sum(a == b for a, b in zip(r[:h], r[:h - 1:-1]))
    return same / (len(rows) * h)


def largest_blob(rows):
    seen = [[False] * W for _ in range(H)]
    best = 0
    for y in range(H):
        for x in range(W):
            if rows[y][x] and not seen[y][x]:
                stack = [(y, x)]
                seen[y][x] = True
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W \
                                and rows[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((ny, nx))
                if n > best:
                    best = n
    return best


INK_BAND = (0.12, 0.70)


def score(rows, sym_floor=0.0):
    """Ink first, then symmetry, then the blob scan.

    The ink band exists because a blank field is perfectly symmetric and would otherwise
    win every run for ever - which is exactly what happened the first time enumeration
    reached the all-zero bitmap. The connected-component scan is twenty times dearer than
    symmetry, so it runs only once a field is already a contender.
    """
    ink = sum(bytes(r).count(1) for r in rows) / (W * H)
    if not INK_BAND[0] <= ink <= INK_BAND[1]:
        return None
    sym = symmetry(rows)
    if sym < sym_floor:
        return None
    blob = largest_blob(rows)
    return {"ink": ink, "sym": sym, "blob": blob,
            "value": round(sym * 100 + blob / 10, 2)}


def note_find(path, rec):
    """One JSON line per new best field, so a run leaves a record behind."""
    if not path:
        return
    rec = dict(rec)
    rec["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# --------------------------------------------------------------- rendering
def as_braille(rows):
    out = []
    for by in range(0, H, 4):
        line = []
        for bx in range(0, W, 2):
            v = 0
            for dy in range(4):
                for dx in range(2):
                    y, x = by + dy, bx + dx
                    if y < H and x < W and rows[y][x]:
                        v |= BRAILLE[dy][dx]
            line.append(chr(0x2800 + v))
        out.append("".join(line))
    return out


def as_half(rows):
    out = []
    for y in range(0, H, 2):
        line = []
        for x in range(W):
            t = rows[y][x]
            b = rows[y + 1][x] if y + 1 < H else 0
            line.append(" ▄▀█"[(t << 1) | b] if (t or b) else " ")
        out.append("".join(line))
    return out


def frame(rows, best_rows, render, stats):
    left = (as_braille if render == "braille" else as_half)(rows)
    right = (as_braille if render == "braille" else as_half)(best_rows) if best_rows else []
    w = max(len(l) for l in left)
    lines = ["  live                              best so far"]
    for i in range(max(len(left), len(right))):
        a = left[i] if i < len(left) else ""
        b = right[i] if i < len(right) else ""
        lines.append(f"  {a:<{w}}    {b}")
    lines += ["", stats]
    return lines


# --------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--fps", type=float, default=8.0)
    p.add_argument("--cpu", type=float, default=15.0, help="percent of one core")
    p.add_argument("--ink", type=float, default=0.30)
    p.add_argument("--render", choices=("braille", "half"), default="braille")
    p.add_argument("--grid", default="42x42",
                   help="WxH or a single N for NxN; 42x42 is the default working version")
    p.add_argument("--enumerate", action="store_true",
                   help="walk every bitmap in order instead of sampling at random "
                        "(only sensible for small grids)")
    p.add_argument("--frames", type=int, default=0, help="print N frames and exit")
    p.add_argument("--ledger", default="pixels42-finds.jsonl",
                   help="append each new best field to this JSON-lines file")
    p.add_argument("--no-ledger", dest="ledger", action="store_const", const=None)
    p.add_argument("--random", action="store_true",
                   help="fresh OS entropy per field instead of counting upward")
    p.add_argument("--key", default=None)
    p.add_argument("--verify", default=None, metavar="KEY:COUNTER")
    p.add_argument("--index", type=int, default=None,
                   help="redraw one enumerated bitmap by index")
    a = p.parse_args()

    global W, H
    if "x" in a.grid.lower():
        W, H = (int(v) for v in a.grid.lower().split("x"))
    else:
        W = H = int(a.grid)
    if not (1 <= W <= 400 and 1 <= H <= 400):
        raise SystemExit("grid out of range")

    if a.index is not None:
        rows = pattern(a.index)
        s = score(rows)
        print("\n".join((as_braille if a.render == "braille" else as_half)(rows)))
        print(f"index {a.index}  ink {s['ink']:.3f}  symmetry {s['sym']:.3f}  "
              f"largest blob {s['blob']}")
        return

    if a.verify:
        k, c = a.verify.split(":")
        rows = field(bytes.fromhex(k), int(c), a.ink)
        s = score(rows)
        print("\n".join((as_braille if a.render == "braille" else as_half)(rows)))
        print(f"ink {s['ink']:.3f}  symmetry {s['sym']:.3f}  largest blob {s['blob']}")
        return

    key = bytes.fromhex(a.key) if a.key else os.urandom(16)
    if a.ledger:
        print(f"ledger: {a.ledger}")
    live = a.frames == 0 and sys.stdout.isatty()
    counter = 0
    best = None
    best_rows = None
    best_at = 0
    tested = 0
    t0 = time.time()
    period = 1.0 / a.fps
    slice_s = max(0.002, period * a.cpu / 100.0)   # search this long between repaints

    if live:
        sys.stdout.write("\x1b[?25l\x1b[2J")
    try:
        painted = 0
        while True:
            work = time.time()
            rows = None
            while time.time() - work < slice_s:
                if a.random and not a.enumerate:
                    key = os.urandom(16)
                    counter = 0
                rows = pattern(counter) if a.enumerate else field(key, counter, a.ink)
                counter += 1
                tested += 1
                s = score(rows, 0.0 if best is None else best["sym"])
                if s and (best is None or s["value"] > best["value"]):
                    best, best_rows, best_at = s, rows, counter - 1
                    note_find(a.ledger, {
                        "grid": f"{W}x{H}", "mode": "enumerate" if a.enumerate else "hash",
                        "key": None if a.enumerate else key.hex(),
                        "address": (f"index {best_at}" if a.enumerate
                                    else f"{key.hex()}:{best_at}"),
                        "ink": round(s["ink"], 4), "symmetry": round(s["sym"], 4),
                        "blob": s["blob"],
                        "rows": ["".join(str(b) for b in r) for r in rows]})

            el = time.time() - t0
            done = (f"   {100 * counter / 2 ** (W * H):.4f}% of the space"
                    if a.enumerate and W * H <= 40 else "")
            where = f"index {best_at}" if a.enumerate else f"{key.hex()[:8]}:{best_at}"
            stats = (f"  {W}x{H}{done}   {tested:,} fields   {tested/max(el,1e-9):,.0f}/s   "
                     f"{el:,.0f}s   best: symmetry {best['sym']:.3f}  "
                     f"blob {best['blob']}  at {where}")
            lines = frame(rows, best_rows, a.render, stats)
            if live:
                sys.stdout.write("\x1b[H" + "\n".join(l + "\x1b[K" for l in lines))
                sys.stdout.flush()
            else:
                print("\n".join(lines) + "\n")
            painted += 1
            if a.frames and painted >= a.frames:
                break
            time.sleep(max(0.0, period - (time.time() - work)))
    except KeyboardInterrupt:
        pass
    finally:
        if live:
            sys.stdout.write("\x1b[?25h\n")
        el = time.time() - t0
        print(f"\n{tested:,} fields in {el:.0f}s ({tested/max(el,1e-9):,.0f}/s)")
        n = W * H
        print(f"space 2^{n} = 10^{n * 0.30103:.1f} bitmaps"
              + (f"  ({2 ** n:,} - exhaustible)" if n <= 46 else ""))
        addr = f"index {best_at}" if a.enumerate else f"{key.hex()}:{best_at}"
        print(f"best  symmetry {best['sym']:.3f}  largest blob {best['blob']}  {addr}")


if __name__ == "__main__":
    main()
