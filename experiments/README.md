# experiments

Two other ways of reading the same 42-cell field. Both are standalone, standard library
only, and use the same addressing idea as `babel42.py`: a field is a keyed hash of a
counter, so a find is reported as `key:counter` and anyone can regenerate it.

## multiscript.py — characters from several alphabets

Latin, Czech diacritics, Greek, mathematical operators and relations, digits,
superscripts — 116 symbols — placed at random positions with most cells left blank.

    python3 multiscript.py

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

    python3 melody42.py --seconds 20 --mode walk

Screen: key fit, interval profile, repeated motif (transposition-invariant), cadence.

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

## Licence

Code: MIT, as the rest of the repository. **Melodies and other output are dedicated to
the public domain under CC0** — they are combinatorial facts, and the point of finding
them is that anybody can use them. The precedent is the All the Music project, which
brute-forced tens of billions of melodies and released them under CC0 on exactly that
argument: https://allthemusic.info/faqs/
