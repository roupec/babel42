#!/usr/bin/env python3
# babel42 - a small public experiment in searching a finite space of 42-character fields.
# Reproducible by construction: every candidate has an address (key, counter) and can be
# regenerated exactly, on any machine, by anyone. Pure standard library. MIT licence.
#
#   python3 babel42.py                  run with default settings
#   python3 babel42.py --cpu 17         cap the work at roughly 17 % of one core
#   python3 babel42.py --seconds 60     stop after a minute
#   python3 babel42.py --verify KEY:N   regenerate the candidate at that address
#   python3 babel42.py --stats          print the size of the space and stop
#
import argparse, hashlib, json, math, os, random, sys, time

WIDTH = 42
ALPHABET = "abcdefghijklmnopqrstuvwxyz "          # 27 symbols
BASE = len(ALPHABET)
LEDGER = "babel42-finds.jsonl"

WORDS = """the be to of and a in that have i it for not on with he as you do at this but his by
from they we say her she or an will my one all would there their what so up out if about who get
which go me when make can like time no just him know take people into year your good some could
them see other than then now look only come its over think also back after use two how our work
first well way even new want because any these give day most us man thing woman life child world
school state family student group country problem hand part place case week company system program
question work government number night point home water room mother area money story fact month lot
right study book eye job word business issue side kind head house service friend father power hour
game line end member law car city community name president team minute idea kid body information
back parent face others level office door health person art war history party result change morning
reason research girl guy moment air teacher force education foot boy age policy process music market
sense nation plan college interest death experience effort rate paper example space ground form
event official matter center couple site project activity star table need court private best door
oil situation cost industry figure street image phone data effect south analysis note movie field
class period plant patient study wind message south truth road machine light noise signal random
formula number pattern search text page mind theory proof number code prime circle square root
value order chance error trial limit sample space state entropy energy heat time clock line curve
sound colour color image screen pixel letter symbol logic reason truth beauty music silence
dust stone river ocean mountain forest desert island storm cloud rain snow fire earth
""".split()
WORDSET = {w for w in WORDS if len(w) >= 3}
MINWORD, MAXWORD = 3, 12


def bigram_model():
    """Log-probability table over symbol pairs, learned from the built-in word list."""
    counts = {}
    for w in WORDS:
        s = " " + w + " "
        for i in range(len(s) - 1):
            counts[s[i:i + 2]] = counts.get(s[i:i + 2], 0) + 1
    total = sum(counts.values()) + BASE * BASE
    return {a + b: math.log((counts.get(a + b, 0) + 1) / total)
            for a in ALPHABET for b in ALPHABET}


BIGRAM = bigram_model()
FLOOR = min(BIGRAM.values())


def field(key: bytes, counter: int) -> str:
    """The candidate at one address. A keyed hash of the counter, so the stream is
    deterministic, seekable, and never overlaps another worker's key."""
    out = []
    block = 0
    while len(out) < WIDTH:
        h = hashlib.blake2b(counter.to_bytes(8, "big") + block.to_bytes(2, "big"),
                            key=key, digest_size=64).digest()
        out.extend(ALPHABET[b % BASE] for b in h)
        block += 1
    return "".join(out[:WIDTH])


def stage1_vowels(s: str) -> bool:
    v = sum(s.count(c) for c in "aeiou")
    return 0.26 <= v / WIDTH <= 0.56


def stage2_bigram(s: str) -> float:
    t = " " + s + " "
    return sum(BIGRAM.get(t[i:i + 2], FLOOR) for i in range(len(t) - 1)) / (len(t) - 1)


def stage3_words(s: str):
    """Longest dictionary words found, and how many characters they cover."""
    found, covered, i = [], 0, 0
    while i < WIDTH:
        best = None
        for n in range(min(MAXWORD, WIDTH - i), MINWORD - 1, -1):
            if s[i:i + n] in WORDSET:
                best = s[i:i + n]
                break
        if best:
            found.append(best)
            covered += len(best)
            i += len(best)
        else:
            i += 1
    return found, covered


def run(args):
    key = bytes.fromhex(args.key) if args.key else os.urandom(16)   # entropy used exactly once
    keyhex = key.hex()
    if args.random:
        print("babel42  independent mode: fresh 16 bytes of OS entropy per field")
    print(f"babel42  width={WIDTH}  alphabet={BASE}  key={keyhex}")
    print(f"space = {BASE}^{WIDTH} = 10^{WIDTH * math.log10(BASE):.1f} fields\n")

    duty = max(0.01, min(1.0, args.cpu / 100.0))
    t0 = time.time()
    n = kept = 0
    best = 0
    counter = args.start
    batch = 20000
    last_status = 0.0
    show_at = 0
    with open(args.ledger, "a") as ledger:
        try:
            while True:
                t = time.time()
                for _ in range(batch):
                    if args.random:
                        # Every field gets its own key straight from the OS, so no field
                        # depends on any other. The address is that key with counter 0,
                        # which --verify reads unchanged.
                        key = os.urandom(16)
                        keyhex = key.hex()
                        counter = 0
                    s = field(key, counter)
                    counter += 1
                    n += 1
                    if not stage1_vowels(s):
                        continue
                    b = stage2_bigram(s)
                    if b < args.bigram:
                        continue
                    words, covered = stage3_words(s)
                    if covered < args.covered:
                        continue
                    kept += 1
                    rec = {"key": keyhex, "counter": counter - 1, "text": s,
                           "mode": "independent" if args.random else "sequential",
                           "bigram": round(b, 3), "covered": covered, "words": words}
                    ledger.write(json.dumps(rec) + "\n")
                    ledger.flush()
                    if covered >= best:
                        best = covered
                        print(f"  [{covered:2d}] {s}   {' '.join(words)}")
                spent = time.time() - t
                el = time.time() - t0
                if args.show and n >= show_at:
                    show_at = n + args.show
                    print(f"      . {field(key, counter - 1)}")
                if el - last_status >= 1.0:
                    last_status = el
                    sys.stdout.write(f"\r  {n:,} fields  {n / max(el, 1e-9):,.0f}/s  "
                                     f"kept {kept}  best {best}  {el:,.0f}s   ")
                    sys.stdout.flush()
                if args.seconds and el >= args.seconds:
                    break
                if duty < 1.0:
                    time.sleep(spent * (1 - duty) / duty)     # keep the machine free
        except KeyboardInterrupt:
            pass
    el = time.time() - t0
    print(f"\n\n{n:,} fields in {el:.0f}s ({n / max(el, 1e-9):,.0f}/s), {kept} kept, best cover {best}")
    print(f"that is 10^{math.log10(max(n, 1)):.1f} of 10^{WIDTH * math.log10(BASE):.1f} - "
          f"a fraction of 10^{math.log10(max(n, 1)) - WIDTH * math.log10(BASE):.1f}")
    if args.random:
        print(f"finds appended to {args.ledger}; each line carries its own key, "
              f"check one with --verify <key>:0")
    else:
        print(f"finds appended to {args.ledger}; anyone can check one with "
              f"--verify {keyhex}:<counter>")


def stats():
    tot = WIDTH * math.log10(BASE)
    meaning = 1.1 * WIDTH * math.log10(2)
    print(f"field           : {WIDTH} characters over {BASE} symbols")
    print(f"total fields    : 10^{tot:.1f}")
    print(f"meaningful ones : about 10^{meaning:.1f}  (English at 1.1 bits per character)")
    print(f"density         : 10^{meaning - tot:.1f}")
    print(f"one core-year   : about 10^{math.log10(50000 * 3600 * 24 * 365):.1f} fields")


def main():
    p = argparse.ArgumentParser(description="babel42 - random search of a 42-character space")
    p.add_argument("--cpu", type=float, default=17, help="percent of one core to use")
    p.add_argument("--seconds", type=float, default=0, help="stop after this long (0 = forever)")
    p.add_argument("--key", help="16-byte hex key, to reproduce or extend a run")
    p.add_argument("--start", type=int, default=0, help="starting counter")
    p.add_argument("--random", action="store_true",
                   help="draw fresh OS entropy for every field instead of counting "
                        "upward from one key")
    p.add_argument("--covered", type=int, default=8, help="minimum characters covered by words")
    p.add_argument("--bigram", type=float, default=-7.05, help="minimum mean bigram log-probability")
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--verify", help="KEY:COUNTER - regenerate one candidate and exit")
    p.add_argument("--show", type=int, default=0,
                   help="print one sample field every N candidates (screensaver mode)")
    p.add_argument("--stats", action="store_true")
    a = p.parse_args()
    if a.stats:
        return stats()
    if a.verify:
        k, c = a.verify.split(":")
        s = field(bytes.fromhex(k), int(c))
        w, cov = stage3_words(s)
        print(s)
        print(f"words {w}  covered {cov}  bigram {stage2_bigram(s):.3f}")
        return
    run(a)


if __name__ == "__main__":
    main()
