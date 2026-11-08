"""bibfetch: BibTeX from registries (Crossref, DBLP, arXiv), never from memory.

  bibfetch "AST: Audio Spectrogram Transformer"     # title
  bibfetch 2104.01778                                # arXiv id / URL
  bibfetch 10.21437/Interspeech.2021-698            # DOI
  bibfetch --check refs.bib                          # preprints with published versions
  bibfetch --check refs.bib --verify                 # also flag entries found nowhere
  bibfetch --tidy refs.bib -o refs.tidy.bib          # cleaned copy of the whole .bib
"""

from __future__ import annotations

import argparse
import re
import sys
import time

from . import __version__
import os
import urllib.error

from .bibparse import arxiv_id, first_author_family, is_preprint, local_tidy, parse_bib, plain_title
from .bibtex import ascii_slug, same_numbers, title_similarity
from .merge import merge_authors, merge_title_case
from .resolve import resolve
from .sources import SourceUnavailable, crossref_by_doi, entry_from_crossref, log

# fields carried over from the original entry when the registry record lacks them
_CARRY = ("url", "note")


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


def _fetched_matches(e, it) -> bool:
    """Guard against a wrong DOI / wrong title hit: same paper as the original?
    (Real failure: a book title matching an author-less book *review*.)"""
    if it.type == "book" and e.type != "book":
        return False
    if not is_preprint(it):
        y_old, y_new = it.fields.get("year", ""), e.fields.get("year", "")
        if y_old.isdigit() and y_new.isdigit() and abs(int(y_old) - int(y_new)) > 1:
            return False
    if not e.fields.get("author") and it.fields.get("author"):
        return False
    t_new = e.fields.get("title", "")
    if title_similarity(t_new, plain_title(it)) < 0.8 or not same_numbers(t_new, plain_title(it)):
        return False
    fa_old = ascii_slug(first_author_family(it))
    a_new = e.fields.get("author", "").split(" and ")[0]
    fa_new = ascii_slug(a_new.split(",")[0] if "," in a_new else a_new)
    return not fa_old or not fa_new or fa_old == fa_new or fa_old in fa_new or fa_new in fa_old


def cmd_tidy(args) -> int:
    if args.output and os.path.abspath(args.output) == os.path.abspath(args.tidy):
        log("Refusing to overwrite the input; pick another -o path and diff the two.")
        return 2
    with open(args.tidy, encoding="utf-8") as fh:
        items = parse_bib(fh.read())
    log(f"{args.tidy}: {len(items)} entries\n")

    out, counts = [], {"fetched": 0, "published": 0, "local": 0}
    for it in items:
        title, pre = plain_title(it), is_preprint(it)
        e, how = None, ""
        try:
            doi = it.fields.get("doi", "")
            if doi and not pre:
                try:
                    e, how = entry_from_crossref(crossref_by_doi(doi), args.long_venues), f"Crossref doi:{doi}"
                except urllib.error.HTTPError:
                    log(f"  ! {it.key}: DOI {doi} not in Crossref")
            if e is None and title:
                q = arxiv_id(it) if pre and arxiv_id(it) else title
                r = resolve(q, prefer_published=True, long_venues=args.long_venues,
                            first_author=first_author_family(it) if q == title else "")
                if r.entry and (r.entry.published or pre):
                    e, how = r.entry, r.entry.fields.get("bibsource", "")
        except SourceUnavailable as ex:
            log(f"  ! {it.key}: lookup failed ({ex})")
        time.sleep(args.delay)

        if e is not None and not _fetched_matches(e, it):
            log(f"  ! {it.key}: registry record looks like a different paper ({e.fields.get('title', '')[:60]}); kept original")
            e = None
        if e is None:
            out.append(local_tidy(it))
            counts["local"] += 1
            log(f"  · {it.key} (l.{it.line}): not found; formatting-only cleanup")
            continue
        e.key = it.key
        if it.fields.get("author") and e.fields.get("author"):
            e.fields["author"] = merge_authors(it.fields["author"], e.fields["author"], keep_etal=args.keep_etal)
        if it.fields.get("title") and e.fields.get("title"):
            e.fields["title"] = merge_title_case(it.fields["title"], e.fields["title"])
        if not e.fields.get("year") and it.fields.get("year"):
            e.fields["year"] = it.fields["year"]  # registry has no date (old proceedings)
        for k in _CARRY:
            if k in it.fields and k not in e.fields and not re.search(r"arxiv|preprint", it.fields[k], re.I):
                e.fields[k] = it.fields[k]
        if pre and e.published:
            counts["published"] += 1
            venue = e.fields.get("booktitle") or e.fields.get("journal", "")
            log(f"  → {it.key} (l.{it.line}): preprint → {venue} {e.fields.get('year', '')}")
        else:
            counts["fetched"] += 1
            log(f"  ✓ {it.key} (l.{it.line}): {how}")
        out.append(e)

    text = "\n\n".join(e.render() for e in out) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        print(text)
    log(f"\n{counts['fetched']} re-fetched, {counts['published']} preprints → published, "
        f"{counts['local']} kept with formatting-only cleanup.")
    if args.output:
        log(f"Wrote {args.output} (same keys, same order). Review: git diff --no-index {args.tidy} {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="bibfetch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("query", nargs="*", help="title, DOI, or arXiv id/URL (one or more)")
    p.add_argument("--check", metavar="BIB", help="report preprint entries in BIB that have published versions")
    p.add_argument("--tidy", metavar="BIB", help="write a cleaned copy of BIB: re-fetch every entry from registries "
                   "(same keys/order), formatting-only cleanup for entries not found")
    p.add_argument("--verify", action="store_true", help="with --check: look up every entry, flag ones not found")
    p.add_argument("-o", "--output", help="with --check/--tidy: write output here instead of stdout")
    p.add_argument("--key", help="citation key to use (single query only)")
    p.add_argument("--author", help="first author's family name, to disambiguate a title search")
    p.add_argument("--keep-preprint", action="store_true", help="don't swap preprints for published versions")
    p.add_argument("--keep-etal", action="store_true", help="with --tidy: keep 'and others' truncations instead of "
                   "full registry author lists (for styles like IEEEbib that can't truncate)")
    p.add_argument("--long-venues", action="store_true", help="keep full conference names (no 'Proc. X')")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between lookups in --check (default 1)")
    p.add_argument("-V", "--version", action="version", version=f"bibfetch {__version__}")
    args = p.parse_args(argv)

    if args.tidy:
        return cmd_tidy(args)
    if args.check:
        return cmd_check(args)
    if not args.query:
        p.print_help()
        return 2
    return cmd_fetch(args)


if __name__ == "__main__":
    sys.exit(main())
