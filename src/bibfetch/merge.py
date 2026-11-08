"""Merge a registry record with the user's original entry (used by --tidy).

The registry is the authority on *which* paper and its metadata, but some
registry records are worse than the original in formatting details:
  - old IEEE records give initials only ("Gray, A.") or drop accents ("Cappe");
  - Crossref sometimes splits particles oddly ("Roux, Jonathan Le");
  - titles can lose internal capitals ("Parallel Wavegan").
These merges only choose between the two spellings of the *same* name/word.
"""

from __future__ import annotations

import re

from .bibtex import ascii_slug, protect_title


def _split_authors(s: str) -> list[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", s) if a.strip()]


def _parts(a: str) -> tuple[str, str]:
    if "," in a:
        fam, given = a.split(",", 1)
        return fam.strip(), given.strip()
    toks = a.split()
    return (toks[-1], " ".join(toks[:-1])) if toks else ("", "")


def _plain(s: str) -> str:
    return re.sub(r"\\[`'^\"~=.uvHckr]\s*|[{}\\]", "", s)


def _has_accent(s: str) -> bool:
    return "\\" in s or any(ord(c) > 127 for c in s)


def _fuller(a: str, b: str) -> str:
    """Prefer the more complete given name: 'Robert' over 'R.', 'Drew A.' over 'Drew A'."""
    la, lb = len(_plain(a).replace(".", "").replace(" ", "")), len(_plain(b).replace(".", "").replace(" ", ""))
    if la != lb:
        return a if la > lb else b
    return b if _has_accent(b) and not _has_accent(a) else a


def merge_authors(original: str, fetched: str, keep_etal: bool = False) -> str:
    """Author-by-author merge. By default the registry's full author list
    replaces an 'and others' truncation (full lists belong in the .bib; styles
    like biblatex/IEEEtran truncate at build time). keep_etal=True keeps the
    original truncation instead (for styles like IEEEbib that print every name)."""
    all_orig = _split_authors(original)
    truncated = keep_etal and any(a.lower() == "others" for a in all_orig)
    orig = [a for a in all_orig if a.lower() != "others"]
    new = _split_authors(fetched)
    if truncated:
        new = new[:len(orig)]
    merged = _merge_lists(orig, new, fetched)
    return merged + (" and others" if truncated and merged != fetched else "")


def _merge_lists(orig: list[str], new: list[str], fetched: str) -> str:
    out = []
    for i, fa in enumerate(new):
        if i >= len(orig):
            out.append(fa)
            continue
        of, og = _parts(orig[i])
        nf, ng = _parts(fa)
        if ascii_slug(_plain(of)) == ascii_slug(_plain(nf)):
            # same surname: keep accents if only one side has them, else take
            # the registry's capitalization (Mcewen -> McEwen)
            fam = of if _has_accent(of) and not _has_accent(nf) else nf
            out.append(f"{fam}, {_fuller(og, ng)}" if (og or ng) else fam)
        elif ascii_slug(_plain(of).split()[-1]) == ascii_slug(_plain(nf).split()[-1]) or \
                ascii_slug(_plain(of + og)) == ascii_slug(_plain(nf + ng)):
            out.append(orig[i])  # same person, particle/compound split differently: keep original
        else:
            return fetched  # lists don't line up: trust the registry wholesale
    return " and ".join(out)


def merge_title_case(original: str, fetched: str) -> str:
    """Restore original capitals the registry lost (WaveGAN, DNSMOS), word by word."""
    plain_fetched = re.sub(r"[{}]", "", fetched)
    orig_words = {w.lower(): w for w in re.findall(r"[A-Za-z0-9]+", re.sub(r"[{}]", "", original))}

    def fix(m: re.Match) -> str:
        w = m.group(0)
        o = orig_words.get(w.lower())
        if o and o != w and sum(c.isupper() for c in o) > sum(c.isupper() for c in w) and \
                sum(c.isupper() for c in o) >= 2:
            return o
        return w

    return protect_title(re.sub(r"[A-Za-z0-9]+", fix, plain_fetched))
