# bibfetch

BibTeX from registries — Crossref, DBLP, arXiv — never typed from memory.

Every entry `bibfetch` prints is built from one registry record. Authors,
titles, venues, pages and DOIs are copied from that record; the tool only
*formats* them (LaTeX accents, braces around acronyms, `--` page ranges,
short conference names). A `bibsource` field (ignored by bibliography styles)
records where each entry came from, so it's easy to tell fetched entries from
hand-typed or LLM-written ones.

It also prefers **published versions over arXiv**: give it an arXiv ID and it
returns the conference/journal version if one exists.

No dependencies beyond the Python standard library.

## Install

```sh
uv tool install git+https://github.com/morrisalp/bibfetch
# or, from a clone:  uv tool install .
```

## Usage

```sh
bibfetch "AST: Audio Spectrogram Transformer"   # by title
bibfetch 2104.01778                              # arXiv id or URL -> published version if any
bibfetch 10.21437/Interspeech.2021-698          # DOI
bibfetch --key gong2021ast 2104.01778           # choose the citation key
bibfetch "Some common title" --author Smith     # disambiguate by first author
```

Status messages go to stderr; BibTeX goes to stdout, so
`bibfetch ... >> refs.bib` works.

### Checking an existing `.bib`

```sh
bibfetch --check refs.bib            # preprint entries that now have published versions
bibfetch --check refs.bib -o new.bib # write the replacements (same keys) to new.bib
bibfetch --check refs.bib --verify   # look up *every* entry; flag ones found nowhere
```

`--check` never modifies your file. Replacement entries keep your existing
citation keys, so you can paste them over the old ones without touching the
`.tex`. `--verify` is a cheap guard against invented references: an entry
whose title matches nothing in Crossref, DBLP or arXiv deserves a manual look
(it may also just be a book, a website, or a very new paper).

### Tidying a whole `.bib` (end-of-paper pass)

```sh
bibfetch --tidy refs.bib -o refs.tidy.bib
git diff --no-index refs.bib refs.tidy.bib    # review, then copy over
```

Every entry is re-fetched (by DOI if it has one, else arXiv ID or title +
first author), keeping your keys and order. Preprints become their published
versions. Entries no registry confirms (books, standards, software, websites)
get **formatting-only** cleanup: acronyms braced, accents, page ranges, short
conference names. Nothing new is invented for them.

Safety checks before a fetched record replaces yours: titles must be ≥0.8
similar *and* contain the same numbers (so *DNSMOS* ≠ *DNSMOS P.835*), the
first author must match, a `@book` is never replaced by a non-book (e.g. a
book review with the same title), and years can't differ by more than one
(except preprint → published).

Where the registry's formatting is *worse* than yours, the better spelling of
the same name/word is kept: full given names over initials ("Gray, Augustine"
over "Gray, A."), accents ("Cappé" over "Cappe"), your particle split ("Le
Roux, Jonathan" over "Roux, Jonathan Le"), and your internal capitals
("WaveGAN" over "Wavegan"). Registry capitalization fixes still apply
("Mcewen" → "McEwen").

**Journal years follow the issue (print) date** from the registry, which can
be a year later than the online date that Google Scholar and IEEE Xplore's
"Date of Publication" show. This is deliberate: once an article is assigned to
a volume/issue, the convention is to cite the year of that volume (it's what
makes volume/issue/pages findable); the online year is only for early-access
articles without a volume yet. See the
[IEEE Reference Guide](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf)
and [this Academia.SE thread](https://academia.stackexchange.com/questions/16585/).

### Reviewing a tidy pass

Build the paper before and after `--tidy`, copying `main.bbl` each time, then:

```sh
bibfetch --review before.bbl after.bbl --bib refs.bib refs.tidy.bib \
         -o review.html --title "My paper refs"
open review.html
```

One card per changed reference, as the PDF prints it, with word-level
red/green highlights. Tick **Accept** and/or add a comment per entry
(saved in the browser). With `--bib`, each card also has a collapsed
**BibTeX** panel showing the source entry before/after. **Copy feedback** exports `key: ACCEPT|NOT ACCEPTED — comment`
lines to hand back to whoever applies the changes. Much easier to review than
the raw `.bib` diff.

### Options

| Flag | Effect |
|---|---|
| `--keep-preprint` | don't swap arXiv/bioRxiv entries for published versions |
| `--keep-etal` | `--tidy`: keep `and others` truncations instead of full author lists (for styles like IEEEbib that print every name; biblatex `maxbibnames` / IEEEtran's control entry truncate at build time instead) |
| `--long-venues` | keep full proceedings names instead of `Proc. Interspeech` etc. |
| `--author NAME` | require this first-author family name in title searches |
| `--delay SEC` | pause between lookups in `--check` (default 1s) |

Set `BIBFETCH_MAILTO=you@example.org` to use Crossref's "polite pool"
(optional; nothing is sent otherwise beyond a generic User-Agent).

## How it decides

1. **DOI** → Crossref record. If it's a preprint DOI (arXiv, bioRxiv, …), it
   looks for a published version by title + first author.
2. **arXiv ID** → arXiv API for title/authors → published DOI listed on arXiv,
   else Crossref + DBLP title search → else the arXiv entry
   (`journal = {arXiv preprint arXiv:XXXX.XXXXX}`).
3. **Title** → Crossref + DBLP, keeping only near-exact title matches
   (similarity ≥ 0.93) → published version preferred → else arXiv → else it
   fails loudly rather than guessing.

DBLP records with a DOI are re-fetched from Crossref (fuller venue names);
DBLP-only records (e.g. ICLR/NeurIPS papers without DOIs) are used directly.

## Limitations

- **Proper nouns** in titles ("Haitian", "Python") aren't braced
  automatically — only acronyms and mixed-case words are. Add braces by hand
  where a style would lowercase a name.
- DBLP sometimes answers automated requests with a bot check; bibfetch then
  warns and carries on with Crossref + arXiv.
- Registries can lag a few months behind new proceedings; re-check recent
  preprints before camera-ready.
- Short venue names cover common NLP/speech/ML/vision conferences (see
  `_VENUES` in `bibtex.py`); anything else keeps the registry's name.

## TODO

Known issues from the first real run (CallCleaner, 48 entries, Nov 2026):

- **Speed:** `--tidy` makes several requests per entry and takes a few minutes
  on ~50 entries. Cache registry responses on disk and/or run lookups in
  parallel (Crossref allows modest concurrency).
- **Multi-word proper names** in titles ("SAM Audio" → "{SAM} audio") aren't
  braced as a unit; only the acronym is. Could reuse the original entry's
  braces, or brace a capitalized word that follows a protected acronym.
- **Non-registry entries** (ITU/ISO standards, Zenodo software, websites) get
  formatting-only cleanup; their entry types (`@software`, fake `@article` for
  standards) still need fixing by hand. Zenodo/DataCite DOIs could be fetched
  from DataCite's API.
- **DBLP** often answers with a bot check; ICML/ICLR/NeurIPS papers without DOIs
  then aren't found. Try the DBLP XML/SPARQL endpoints, or the ACL Anthology
  and OpenReview for those venues.
- **Journal year:** maybe an `--online-year` option for venues/fields that
  prefer it (default stays the issue year; see above).
- **Author merging** is heuristic (full names over initials, accents, particle
  splits). Edge cases: different author
  order, consortium authors.
- **`--max-authors N`:** full list up to N, `and others` beyond (for IEEEbib-style
  papers, without losing full lists elsewhere).
- **`--review` automation:** build the paper before/after itself (latexmk) instead of
  taking two `.bbl` files; feed the copied feedback back in to apply accepts/rejects.

