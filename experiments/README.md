# experiments

Two other ways of reading the same 42-cell field. Both are standalone, standard library
only, and use the same addressing idea as `babel42.py`: a field is a keyed hash of a
counter, so a find is reported as `key:counter` and anyone can regenerate it.

## multiscript.py — characters from several alphabets

Latin, Czech diacritics, Greek, mathematical operators and relations, digits,
superscripts — 116 symbols — placed at random positions with most cells left blank.

    python3 multiscript.py                                  the three measurements below
    python3 multiscript.py --list                            the named alphabets
    python3 multiscript.py --alphabet greek+math --k 10      one alphabet, 10 of 42 cells
    python3 multiscript.py --alphabet "0123456789+-*/=()pi" --k 7

`--alphabet` takes a named set (`latin_en`, `latin_cs`, `greek`, `math`, `mixed_all`),
several joined with `+`, or a literal string of characters. `--k` is how many of the 42
cells carry a character. Only expressions and English words are screened; Czech and Greek
get the script-coherence test but no vocabulary check, which would need word lists.

Measured here:

* A larger alphabet makes the space **worse**: 116 symbols in all 42 cells is 10^86.7
  against 10^60.1 for 27 symbols. Sparsity is the only free win — 8 of 42 cells filled
  is 10^24.6.
* **Script coherence is a good filter and costs nothing.** 67.8 % of runs survive the
  rule "stay inside one script, or inside the legitimate {Latin, Greek, math} mixture
  that real formulas use". Pure codepoint arithmetic.
* Out of 200,000 mixed sparse fields, **7** contained a well-formed expression, and all
  of them were junk (`--5`, `-π+v`). Math-only alphabet: 25 per 200,000, same story.
* Putting the randomness in the **derivation** instead of the characters produces
  400,000 well-formed expressions per second, of which 7.94 % equal a named constant and
  0.044 % survive removal of self-restatements — and those are still trivial
  (`√2 = √(3-1)`). The hard problem is canonicalisation, not generation.

If you extend this: normalise to NFC, store codepoints rather than glyphs in the ledger,
and use a curated codepoint list — Greek ο against Latin o will otherwise break
verification across platforms.

## melody42.py — the field read as music

42 cells, each a rest or a pitch. Survivors are written as `.mid` and rendered to `.wav`
with nothing but the standard library, so a find is audible immediately.

    python3 melody42.py --seconds 20
    python3 melody42.py --live                 play each new best as it is found
    python3 melody42.py --no-play --repeat 2

Screen: key fit, interval profile, repeated motif (transposition-invariant), cadence.

Finds are played automatically when the search ends, using whatever the machine already
has - `afplay` on macOS, `paplay`, `aplay`, `ffplay`, `play` or `mpv` on Linux, `winsound`
on Windows. Nothing is installed for you; without a player the files are still written.
`--live` plays each new best while the search continues, dropping a melody if the previous
one is still sounding.

One caveat visible in the output: the motif test rewards repetition, so the walk drifts to
the top of its range and finds ending in a dozen repeated notes score well. Bounding the
walk and penalising immediate repeats is the obvious next filter.

| generation | space | fits one scale | + interval profile | + repeated motif |
|---|---|---|---|---|
| free chromatic | 10^46.8 | 3 in 1,228,000 | 0 | 0 |
| in-key by construction | 10^50.6 | 100 % | 0 in 1,442,000 | 0 |
| melodic random walk | 10^50.6 | 99.98 % | 54.0 % | 31.4 % |

Compare the bottom row with text, where meaning sits at 10^-46.2. Music is roughly
forty-six orders of magnitude more forgiving, so random search genuinely works here. But
the middle row matters just as much: uniform random pitches inside a scale produced
**zero** melodies. Contour is a property of the walk, not of the alphabet — structure has
to go into the generator, exactly as with the formulas above.

The bottleneck therefore flips. In text you find nothing; in music you find too much, and
the real work becomes novelty and taste: fingerprint melodies by interval vector and
Parsons contour so "already known" is a hash lookup, and let people vote with their ears.

## pixels42.py - the field as a 42 x 42 bitmap, drawn live

    python3 pixels42.py                      live dots, 8 repaints/s, ~16 % of one core
    python3 pixels42.py --fps 4 --cpu 8      lighter
    python3 pixels42.py --render half        half-block pixels instead of braille
    python3 pixels42.py --verify KEY:COUNTER
    python3 pixels42.py --grid 7x6 --enumerate      walk the whole space instead
    python3 pixels42.py --grid 12 --render half

Two panes: the field being drawn now, and the best one so far. Braille packs eight pixels
per character, so 42 x 42 fits in 21 columns; 42 is not divisible by 4, so the bottom
braille row is a half row. Screening is mirror symmetry, largest 4-connected blob, and ink
fraction. Search rate and repaint rate are independent - the loop works for `--cpu` percent
of each frame interval and sleeps the rest, and repaints with cursor-home rather than a
screen clear, so it is usable as a screensaver.

Measured: one `shake_256` call per field gives 78,000 fields/s; symmetry runs on all of
them at 17,800/s; the blob scan costs 3,100/s and therefore runs only when a field already
beats the incumbent on symmetry. At the defaults, 2,800 fields/s tested at 16 % of one
core.

`--grid` is the real knob, and it is bits per cell rather than the count of cells that
decides everything. 42 cells of 27 symbols (the text variant) is 10^60. 42 cells of one bit
each - a 7x6 grid - is 2^42 = 4.4 x 10^12, small enough to walk end to end, so `--enumerate`
visits every bitmap exactly once instead of sampling. Plain counting is useless to watch,
because the low bits move first and the top rows stay blank for billions of steps; the
enumeration multiplies the index by an odd constant modulo 2^n, which is a full-cycle
permutation, so coverage stays complete and consecutive frames look unrelated. 12x12 sits
at 10^43.3, about where the music does. 42x42 remains the default.

At 7x6 the screens finally bite: 458,000 patterns in 6 s produced a perfectly symmetric
bitmap with a 7-pixel connected blob at index 33021, redrawable with `--index 33021`.
A blank field is also perfectly symmetric, which is why scoring now requires ink between
0.12 and 0.70 - the all-zero bitmap won the first enumeration run outright.

At 42x42 it finds nothing, which is the honest result. The space is 2^1764 = 10^531. Random
symmetry sits at 0.5; a few thousand fields reached 0.635, seven standard deviations out
and still visibly noise. Denser ink (`--ink 0.42`) grows blobs to a hundred pixels without
producing structure. Set against text at 10^60 and music at 10^50, the pixel reading shows
what the size of a space really costs.

## Licence

Code: MIT, as the rest of the repository. **Melodies and other output are dedicated to
the public domain under CC0** — they are combinatorial facts, and the point of finding
them is that anybody can use them. The precedent is the All the Music project, which
brute-forced tens of billions of melodies and released them under CC0 on exactly that
argument: https://allthemusic.info/faqs/
