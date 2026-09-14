# babel42

A small public experiment. Fields of **42 characters** over an alphabet of 27 symbols
(a–z and space) are drawn at random, screened locally for anything that looks like
language, and the survivors are written to a ledger. Nothing else happens. There is no
server yet, no account, no upload — one file, standard library only, runs on macOS,
Linux and Windows.

    python3 babel42.py --stats            how big the space is
    python3 babel42.py                    run it, capped at ~17 % of one core
    python3 babel42.py --seconds 60       run for a minute
    python3 babel42.py --show 200000      screensaver mode: sample fields on screen
    python3 babel42.py --verify KEY:N     regenerate one field from its address

## The space

| | |
|---|---|
| field | 42 characters over 27 symbols |
| total fields | 27^42 = 10^60.1 |
| fields that mean something | about 10^13.9 (English at ~1.1 bits per character) |
| density of meaning | 10^-46.2 |
| one core-year of drawing | about 10^12.2 fields |

So a full sentence will never appear. That is not a defect of the program, it is the
arithmetic, and it is the first thing the project is here to make felt rather than
asserted. What *does* appear, several dozen times per million fields, is word soup —
three or four real words sitting in noise. The point of the exercise is the machinery
around that: cheap local screening, reproducible addresses, and an honest ledger.

## Addresses, not files

There is no stored library. Each field is produced by a keyed hash of a counter:

    field(key, counter) -> 42 characters

The key is 16 bytes, taken from the operating system's entropy **once**. Everything
after that is deterministic, which is what makes the project workable:

* **Reproducible.** A find is reported as `key:counter`, a few bytes. Anybody can
  regenerate the exact field on any machine with `--verify`, and check it.
* **Non-overlapping.** Two volunteers with different keys never tread the same ground,
  and one volunteer can be handed a counter range to work through. Coverage becomes
  bookkeeping instead of hope.
* **Seekable.** Any position in the stream can be reached instantly, with no state.

This is the counter-based generator idea from
[Random123 / Philox](https://www.thesalmons.org/john/random123/papers/random123sc11.pdf),
and it is the same trick that lets libraryofbabel.info answer a search instantly without
storing anything: the mapping between an address and its contents runs in both
directions.

True hardware randomness (`RDRAND`, `/dev/urandom`) is used for exactly one thing —
choosing the key. After that, unpredictability would only destroy the ability to verify.

## The screen

Three stages, cheapest first, arithmetic only, no model and no network:

1. **Vowel band** — the fraction of vowels must fall in a plausible range. Passes ~15 %.
2. **Bigram plausibility** — mean log-probability of adjacent symbol pairs, from a table
   built out of the bundled word list.
3. **Dictionary coverage** — greedy scan for words of 3 letters or more; a field is kept
   when enough of its characters are covered.

Measured on this machine: about **108 000 fields per second** on one core at full tilt,
and roughly **20 000 per second** at the default 17 % cap. Around **36 finds per
million** fields at the default thresholds, best coverage seen so far 12 of 42
characters (`way boy any new`).

Survivors are appended to `babel42-finds.jsonl`, one JSON object per line, with key,
counter, text, scores and the words found.

## What this is for

Curiosity, in public. The plan is a repository anyone can read, a client small enough to
audit in one sitting, and a ledger of finds with the finder credited. Later stages, not
in this file yet: a work-unit server, a canonicaliser and known-item database so the
already-known is rejected automatically, and the same funnel pointed at symbolic
mathematics, where the space is small enough (10^13–10^19) for random search to actually
land.

## Tuning

    --cpu 17          percent of one core to use (duty cycle, measured at ~19 %)
    --covered 8       minimum characters covered by dictionary words
    --bigram -7.05    minimum mean bigram log-probability
    --key HEX         reuse a key, to extend or reproduce a run
    --start N         starting counter

## Licence

MIT. Findings are free to use by anyone.
