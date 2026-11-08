"""bibfetch: BibTeX from registries (Crossref, DBLP, arXiv), never from memory.

  bibfetch "AST: Audio Spectrogram Transformer"     # title
  bibfetch 2104.01778                                # arXiv id / URL
  bibfetch 10.21437/Interspeech.2021-698            # DOI
  bibfetch --check refs.bib                          # preprints with published versions
  bibfetch --check refs.bib --verify                 # also flag entries found nowhere
"""

from __future__ import annotations

import argparse
import sys
import time

from . import __version__
from .bibparse import arxiv_id, first_author_family, is_preprint, parse_bib, plain_title
from .resolve import resolve
from .sources import log


def cmd_fetch(args) -> int:
    rc = 0
    for q in args.query:
        log(f"> {q}")
        r = resolve(q, prefer_published=not args.keep_preprint, long_venues=args.long_venues,
                    first_author=args.author or "")
        if not r.entry:
            log(f"  ✗ {r.note}")
            rc = 1
            continue
        if args.key and len(args.query) == 1:
            r.entry.key = args.key
        if r.note:
            log(f"  · {r.note}")
        for c in r.alternatives[:3]:
            log(f"  · also matched: {c.describe()}")
        print(r.entry.render() + "\n")
    return rc


def cmd_check(args) -> int:
    with open(args.check, encoding="utf-8") as fh:
        items = parse_bib(fh.read())
    targets = items if args.verify else [i for i in items if is_preprint(i)]
    log(f"{args.check}: {len(items)} entries; checking {len(targets)}"
        f"{' (all, --verify)' if args.verify else ' preprint entries'}\n")

    replacements, missing, unchanged = [], [], []
    for it in targets:
        title = plain_title(it)
        if not title:
            continue
        fa = first_author_family(it)
        q = arxiv_id(it) if is_preprint(it) and arxiv_id(it) else title
        r = resolve(q, prefer_published=True, long_venues=args.long_venues, first_author=fa if q == title else "")
        time.sleep(args.delay)
        if not r.entry:
            missing.append(it)
            log(f"  ✗ {it.key} (l.{it.line}): NOT FOUND in any registry — check by hand")
            continue
        if is_preprint(it) and r.entry.published:
            r.entry.key = it.key
            replacements.append(r.entry)
            venue = r.entry.fields.get("booktitle") or r.entry.fields.get("journal", "")
            log(f"  → {it.key} (l.{it.line}): published in {venue} {r.entry.fields.get('year', '')}")
        else:
            unchanged.append(it)
            log(f"  ✓ {it.key}: {'still preprint only' if is_preprint(it) else 'found'}"
                f"{' — ' + r.note if r.note and 'no published' not in r.note else ''}")

    log(f"\n{len(replacements)} with published versions, {len(missing)} not found, {len(unchanged)} unchanged.")
    if replacements:
        out = "\n\n".join(e.render() for e in replacements) + "\n"
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(out)
            log(f"Replacement entries (same keys) written to {args.output}; review, then paste over the old ones.")
        else:
            print(out)
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bibfetch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="*", help="title, DOI, or arXiv id/URL (one or more)")
    p.add_argument("--check", metavar="BIB", help="report preprint entries in BIB that have published versions")
    p.add_argument("--verify", action="store_true", help="with --check: look up every entry, flag ones not found")
    p.add_argument("-o", "--output", help="with --check: write replacement entries here instead of stdout")
    p.add_argument("--key", help="citation key to use (single query only)")
    p.add_argument("--author", help="first author's family name, to disambiguate a title search")
    p.add_argument("--keep-preprint", action="store_true", help="don't swap preprints for published versions")
    p.add_argument("--long-venues", action="store_true", help="keep full conference names (no 'Proc. X')")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between lookups in --check (default 1)")
    p.add_argument("-V", "--version", action="version", version=f"bibfetch {__version__}")
    args = p.parse_args(argv)

    if args.check:
        return cmd_check(args)
    if not args.query:
        p.print_help()
        return 2
    return cmd_fetch(args)


if __name__ == "__main__":
    sys.exit(main())
