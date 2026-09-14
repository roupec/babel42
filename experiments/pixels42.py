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
import argparse, hashlib, os, sys, time

SIDE = 42
BRAILLE = ((0x01, 0x08), (0x02, 0x10), (0x04, 0x20), (0x40, 0x80))


# --------------------------------------------------------------- the field
_TABLES = {}


def field(key, counter, ink=0.30):
    """42 x 42 bits as 42 rows of bytes, one keyed hash call per field."""
    table = _TABLES.get(ink)
    if table is None:
        thr = int(255 * ink)
        table = _TABLES[ink] = bytes(1 if i <= thr else 0 for i in range(256))
    flat = hashlib.shake_256(key + counter.to_bytes(8, "big")).digest(
        SIDE * SIDE).translate(table)
    return [flat[r * SIDE:(r + 1) * SIDE] for r in range(SIDE)]


# --------------------------------------------------------------- the screen
H = SIDE // 2


def symmetry(rows):
    """Fraction of cells matching their mirror image about the vertical axis."""
    same = 0
    for r in rows:
        same += sum(a == b for a, b in zip(r[:H], r[:H - 1:-1]))
    return same / (SIDE * H)


def largest_blob(rows):
    seen = [[False] * SIDE for _ in range(SIDE)]
    best = 0
    for y in range(SIDE):
        for x in range(SIDE):
            if rows[y][x] and not seen[y][x]:
                stack = [(y, x)]
                seen[y][x] = True
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < SIDE and 0 <= nx < SIDE \
                                and rows[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            stack.append((ny, nx))
                if n > best:
                    best = n
    return best


def score(rows, sym_floor=0.0):
    """Symmetry is cheap and runs on every field; the connected-component scan is
    twenty times dearer, so it runs only when the field is already a contender."""
    sym = symmetry(rows)
    if sym < sym_floor:
        return None
    ink = sum(bytes(r).count(1) for r in rows) / (SIDE * SIDE)
    blob = largest_blob(rows)
    return {"ink": ink, "sym": sym, "blob": blob,
            "value": round(sym * 100 + blob / 10, 2)}


# --------------------------------------------------------------- rendering
def as_braille(rows):
    out = []
    for by in range(0, SIDE, 4):
        line = []
        for bx in range(0, SIDE, 2):
            v = 0
            for dy in range(4):
                for dx in range(2):
                    y, x = by + dy, bx + dx
                    if y < SIDE and x < SIDE and rows[y][x]:
                        v |= BRAILLE[dy][dx]
            line.append(chr(0x2800 + v))
        out.append("".join(line))
    return out


def as_half(rows):
    out = []
    for y in range(0, SIDE, 2):
        line = []
        for x in range(SIDE):
            t = rows[y][x]
            b = rows[y + 1][x] if y + 1 < SIDE else 0
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
    p.add_argument("--frames", type=int, default=0, help="print N frames and exit")
    p.add_argument("--key", default=None)
    p.add_argument("--verify", default=None, metavar="KEY:COUNTER")
    a = p.parse_args()

    if a.verify:
        k, c = a.verify.split(":")
        rows = field(bytes.fromhex(k), int(c), a.ink)
        s = score(rows)
        print("\n".join((as_braille if a.render == "braille" else as_half)(rows)))
        print(f"ink {s['ink']:.3f}  symmetry {s['sym']:.3f}  largest blob {s['blob']}")
        return

    key = bytes.fromhex(a.key) if a.key else os.urandom(16)
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
                rows = field(key, counter, a.ink)
                counter += 1
                tested += 1
                s = score(rows, 0.0 if best is None else best["sym"])
                if s and (best is None or s["value"] > best["value"]):
                    best, best_rows, best_at = s, rows, counter - 1

            el = time.time() - t0
            stats = (f"  {tested:,} fields   {tested/max(el,1e-9):,.0f}/s   "
                     f"{el:,.0f}s   best: symmetry {best['sym']:.3f}  "
                     f"blob {best['blob']}  at {key.hex()[:8]}:{best_at}")
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
        print(f"space 2^{SIDE*SIDE} = 10^{SIDE*SIDE*0.30103:.0f} bitmaps")
        print(f"best  symmetry {best['sym']:.3f}  largest blob {best['blob']}  "
              f"address {key.hex()}:{best_at}")


if __name__ == "__main__":
    main()
