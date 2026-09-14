#!/usr/bin/env python3
"""melody42 - the same 42-cell field, read as music instead of text.

42 cells, each one either a rest or one of 12 semitones across a two-octave span.
Addresses work exactly as in babel42: field = keyed hash of a counter, so a find is
reported as key:counter and anyone can regenerate and re-hear it.

Screen (arithmetic only, no model, no network):
  1. key fit      - all sounded pitches belong to one major or natural minor scale
  2. interval     - most moves are steps or small leaps, range inside ~an octave and a half
  3. motif        - some interval pattern of 3+ moves repeats inside the field
  4. cadence      - the last sounded note is the tonic, approached by step

Survivors are written as .mid and rendered to .wav with the standard library only.

Run:  python3 melody42.py --seconds 20
"""
import argparse, hashlib, json, math, os, shutil, struct, subprocess, sys, time, wave

WIDTH = 42
REST = -1
SPAN = 25                      # two octaves plus one, in semitones
MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)
# a bounded random walk over scale degrees: mostly steps, occasional leaps
STEPS = ([0] * 10 + [1] * 22 + [-1] * 22 + [2] * 11 + [-2] * 11
         + [3] * 6 + [-3] * 6 + [4] * 3 + [-4] * 3 + [5, -5, 7, -7])


# ------------------------------------------------------------------ addressing
def field(key, counter, rest_prob=0.22, mode="chromatic", tonic=0, scale=MAJOR):
    """mode='chromatic': any of 25 semitones. mode='diatonic': only scale degrees,
    so key fit is true by construction and the screen can do real work."""
    cells = []
    cells_deg = []
    buf = b""
    block = 0
    while len(buf) < 2 * WIDTH + 8:
        buf += hashlib.blake2b(counter.to_bytes(8, "big") + block.to_bytes(2, "big"),
                               key=key, digest_size=64).digest()
        block += 1
    for i in range(WIDTH):
        a, b = buf[2 * i], buf[2 * i + 1]
        if a < 256 * rest_prob:
            cells.append(REST)
        elif mode == "diatonic":
            d = b % 15                      # two octaves of the seven degrees
            cells.append(tonic + 12 * (d // 7) + scale[d % 7])
        elif mode == "walk":
            step = STEPS[b % len(STEPS)]
            d = max(0, min(14, (cells_deg[-1] if cells_deg else 7) + step))
            cells_deg.append(d)
            cells.append(tonic + 12 * (d // 7) + scale[d % 7])
        else:
            cells.append(b % SPAN)
    return cells


# ------------------------------------------------------------------ the screen
def sounded(cells):
    return [c for c in cells if c != REST]


def key_fit(cells):
    """Return (tonic, scale_name) if every sounded pitch fits one scale, else None."""
    pcs = {c % 12 for c in sounded(cells)}
    if len(pcs) < 4:
        return None
    for tonic in range(12):
        for name, scale in (("major", MAJOR), ("minor", MINOR)):
            if all((p - tonic) % 12 in scale for p in pcs):
                return tonic, name
    return None


def interval_ok(cells):
    s = sounded(cells)
    if len(s) < 12:
        return False
    if max(s) - min(s) > 19:
        return False
    moves = [abs(s[i + 1] - s[i]) for i in range(len(s) - 1)]
    if not moves or max(moves) > 12:
        return False
    small = sum(1 for m in moves if m <= 2) / len(moves)
    same = sum(1 for m in moves if m == 0) / len(moves)
    return small >= 0.55 and same <= 0.30


def motif(cells, minlen=3):
    """Longest interval pattern that occurs at least twice (transposition-invariant)."""
    s = sounded(cells)
    iv = tuple(s[i + 1] - s[i] for i in range(len(s) - 1))
    best = 0
    for L in range(minlen, len(iv) // 2 + 1):
        pats = {}
        for i in range(len(iv) - L + 1):
            pats.setdefault(iv[i:i + L], []).append(i)
        for p, at in pats.items():
            if len(at) >= 2 and at[-1] - at[0] >= L:
                best = max(best, L)
    return best


def cadence(cells, tonic):
    s = sounded(cells)
    if len(s) < 2 or s[-1] % 12 != tonic:
        return False
    return abs(s[-1] - s[-2]) <= 2


def score(cells):
    k = key_fit(cells)
    if not k:
        return None
    if not interval_ok(cells):
        return None
    m = motif(cells)
    if m < 3:
        return None
    tonic, name = k
    return {"tonic": tonic, "scale": name, "motif": m,
            "cadence": cadence(cells, tonic), "notes": len(sounded(cells))}


# ------------------------------------------------------------------ output
def midi(cells, path, base=60, ticks=120, bpm=100):
    ev = bytearray()
    ev += b"\x00\xff\x51\x03" + struct.pack(">I", int(60_000_000 / bpm))[1:]
    delta = 0
    for c in cells:
        if c == REST:
            delta += ticks
            continue
        ev += vlq(delta) + bytes((0x90, base + c, 0x50))
        ev += vlq(ticks) + bytes((0x80, base + c, 0x00))
        delta = 0
    ev += b"\x00\xff\x2f\x00"
    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    open(path, "wb").write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks) + trk)


def vlq(n):
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(out)


def wav(cells, path, base=60, sr=22050, note=0.20, gap=0.0):
    """Plain-Python plucked tone: three harmonics with a decaying envelope."""
    frames = bytearray()
    n = int(sr * note)
    for c in cells:
        for i in range(n):
            t = i / sr
            if c == REST:
                v = 0.0
            else:
                f = 440.0 * 2 ** ((base + c - 69) / 12)
                env = math.exp(-4.0 * t) * min(1.0, i / 120)
                v = env * (0.6 * math.sin(2 * math.pi * f * t)
                           + 0.25 * math.sin(4 * math.pi * f * t)
                           + 0.15 * math.sin(6 * math.pi * f * t))
            frames += struct.pack("<h", int(max(-1, min(1, v)) * 22000))
    w = wave.open(path, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(bytes(frames))
    w.close()


NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def show(cells):
    return " ".join("." if c == REST else NAMES[c % 12] + str(c // 12) for c in cells)


def note_find(path, rec):
    if not path:
        return
    rec = dict(rec)
    rec["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ playback
def player():
    """First working audio player on this machine, or None.

    macOS ships afplay; Linux desktops have paplay, aplay or ffplay; Windows uses the
    winsound module in the standard library. Nothing is installed for you.
    """
    if sys.platform == "darwin" and shutil.which("afplay"):
        return ("afplay",)
    if sys.platform.startswith("win"):
        return ("winsound",)
    for c in ("paplay", "aplay", "ffplay", "play", "mpv"):
        if shutil.which(c):
            return (c, "-nodisp", "-autoexit") if c == "ffplay" else (c,)
    return None


_playing = [None]


def play(path, cmd, blocking=True):
    """Play a .wav. Non-blocking calls are dropped while something is still sounding."""
    if cmd is None:
        return False
    if cmd[0] == "winsound":
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME |
                           (0 if blocking else winsound.SND_ASYNC))
        return True
    if not blocking:
        if _playing[0] is not None and _playing[0].poll() is None:
            return False
        _playing[0] = subprocess.Popen(list(cmd) + [path],
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
        return True
    subprocess.run(list(cmd) + [path], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    return True


# ------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seconds", type=float, default=20)
    p.add_argument("--key", default=None)
    p.add_argument("--out", default=".")
    p.add_argument("--keep", type=int, default=3)
    p.add_argument("--mode", choices=("chromatic", "diatonic", "walk"), default="walk")
    p.add_argument("--play", dest="play", action="store_true", default=True,
                   help="play the finds when the search ends (default)")
    p.add_argument("--no-play", dest="play", action="store_false")
    p.add_argument("--live", action="store_true",
                   help="also play each new best melody as it is found")
    p.add_argument("--ledger", default="melody42-finds.jsonl",
                   help="append the kept melodies to this JSON-lines file")
    p.add_argument("--no-ledger", dest="ledger", action="store_const", const=None)
    p.add_argument("--repeat", type=int, default=1,
                   help="how many times to play each find")
    a = p.parse_args()

    if a.ledger:
        print(f"ledger: {a.ledger}")
    cmd = player() if (a.play or a.live) else None
    if (a.play or a.live) and cmd is None:
        print("  no audio player found - writing files only "
              "(macOS: afplay, Linux: install pulseaudio-utils or alsa-utils)")

    key = bytes.fromhex(a.key) if a.key else os.urandom(16)
    A = {"diatonic": 16, "walk": 16}.get(a.mode, 26)
    print(f"key {key.hex()}   42 cells, mode={a.mode}, alphabet {A} (incl. rest)")
    print(f"space  {A}^42 = 10^{42 * math.log10(A):.1f} fields\n")

    t0 = time.time()
    last = [0.0]
    n = fit = iv = kept = 0
    best = []
    while time.time() - t0 < a.seconds:
        for _ in range(2000):
            cells = field(key, n, mode=a.mode)
            n += 1
            if key_fit(cells):
                fit += 1
                if interval_ok(cells):
                    iv += 1
                    s = score(cells)
                    if s:
                        kept += 1
                        cand = (s["motif"], s["cadence"], n - 1, cells, s)
                        if a.live and (not best or cand[:2] > max(b[:2] for b in best)):
                            stem = os.path.join(a.out,
                                                f"melody42-{key.hex()[:8]}-{n-1}")
                            wav(cells, stem + ".wav")
                            if play(stem + ".wav", cmd, blocking=False):
                                print(f"\r  playing counter {n-1}: "
                                      f"{NAMES[s['tonic']]} {s['scale']}, "
                                      f"motif {s['motif']} moves        ")
                        best.append(cand)
                        if len(best) > 400:          # keep the list bounded
                            best.sort(key=lambda x: (x[0], x[1]), reverse=True)
                            del best[a.keep * 4:]
        el = time.time() - t0
        if el - last[0] >= 2.0:
            last[0] = el
            print(f"\r  {n:,} fields  {n/el:,.0f}/s  in-key {fit:,}  +interval {iv:,}  "
                  f"kept {kept}   ", end="", flush=True)

    el = time.time() - t0
    print(f"\n\n{n:,} fields in {el:.0f}s ({n/el:,.0f}/s)")
    print(f"  fits one scale        : {fit:,}  ({fit/n:.4%})")
    print(f"  + interval profile    : {iv:,}  ({iv/n:.4%})")
    print(f"  + repeated motif      : {kept:,}  ({kept/n:.4%})")
    best.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for rank, (m, cad, ctr, cells, s) in enumerate(best[:a.keep], 1):
        stem = os.path.join(a.out, f"melody42-{key.hex()[:8]}-{ctr}")
        midi(cells, stem + ".mid")
        wav(cells, stem + ".wav")
        print(f"\n#{rank}  counter {ctr}  {NAMES[s['tonic']]} {s['scale']}  "
              f"motif {m} moves  cadence {'yes' if cad else 'no'}  "
              f"{s['notes']} notes")
        print(f"    {show(cells)}")
        print(f"    {stem}.mid / .wav")
        note_find(a.ledger, {"key": key.hex(), "counter": ctr, "mode": a.mode,
                             "tonic": NAMES[s["tonic"]], "scale": s["scale"],
                             "motif": m, "cadence": bool(cad), "notes": s["notes"],
                             "cells": list(cells), "names": show(cells),
                             "wav": stem + ".wav", "mid": stem + ".mid"})
        if a.play and cmd:
            for _ in range(max(1, a.repeat)):
                play(stem + ".wav", cmd, blocking=True)


if __name__ == "__main__":
    main()
