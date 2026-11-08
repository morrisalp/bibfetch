"""Turn a query (DOI, arXiv id/URL, or title) into one source-backed Entry."""

from __future__ import annotations

import re
import urllib.error
from dataclasses import dataclass, field

from .bibtex import Entry, ascii_slug, same_numbers, title_similarity
from .sources import (
    ARXIV_ID, Candidate, SourceUnavailable, arxiv_by_id, arxiv_search, crossref_by_doi,
    crossref_search, dblp_search, entry_from_arxiv, entry_from_crossref, entry_from_dblp,
    is_preprint_doi, log,
)

DOI = re.compile(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)", re.I)
TITLE_MATCH = 0.93


@dataclass
class Result:
    entry: Entry | None
    note: str = ""
    alternatives: list[Candidate] = field(default_factory=list)


def classify(q: str) -> tuple[str, str]:
    q = q.strip()
    m = DOI.fullmatch(q)
    if m:
        doi = m.group(1).rstrip(".,;")
        a = re.match(r"10\.48550/arxiv\.(.+)$", doi, re.I)
        return ("arxiv", a.group(1)) if a else ("doi", doi)
    m = ARXIV_ID.search(q)
    if m and (" " not in q or q.lower().startswith("arxiv")):
        return "arxiv", m.group(1)
    return "title", q


def _same_author(a: str, b: str) -> bool:
    """Family-name match, tolerant of particles split differently across
    registries ('Le Roux' vs. Crossref's 'Roux', given 'Jonathan Le')."""
    if not (a and b):
        return False
    if ascii_slug(a) == ascii_slug(b):
        return True
    return ascii_slug(a.split()[-1]) == ascii_slug(b.split()[-1])


def find_candidates(title: str, first_author: str = "") -> list[Candidate]:
    """Title search across Crossref + DBLP; keep near-exact title matches."""
    cands: list[Candidate] = []
    # Crossref twice: plain title search, plus title+author (short/generic titles
    # like "Segment anything" only surface with the author; but author search
    # is accent-sensitive, e.g. arXiv's "Defossez" misses Crossref's "Défossez").
    searches = [("Crossref", crossref_search), ("DBLP", dblp_search)]
    if first_author:
        searches.insert(1, ("Crossref", lambda t: crossref_search(t, author=first_author)))
    for name, fn in searches:
        try:
            cands += fn(title)
        except SourceUnavailable as e:
            log(f"  ! {name} unavailable: {e}")
    good = [c for c in cands if title_similarity(c.title, title) >= TITLE_MATCH and same_numbers(c.title, title)]
    if first_author:
        good = [c for c in good if _same_author(c.first_author, first_author)]
    return good


def _pick_published(cands: list[Candidate]) -> Candidate | None:
    pub = [c for c in cands if c.published]
    if not pub:
        return None
    # Crossref (has DOI, full venue names) before DBLP; then earliest year
    pub.sort(key=lambda c: (c.source != "crossref", c.year or "9999"))
    return pub[0]


def _entry_from_candidate(c: Candidate, long_venues: bool) -> Entry:
    if c.source == "crossref":
        return entry_from_crossref(c.raw, long_venues)
    if c.source == "dblp":
        doi = c.raw.get("doi")
        if doi:
            try:
                return entry_from_crossref(crossref_by_doi(doi), long_venues)
            except (SourceUnavailable, urllib.error.HTTPError) as e:
                log(f"  ! Crossref lookup of {doi} failed ({e}); using DBLP record")
        return entry_from_dblp(c.raw, long_venues)
    return entry_from_arxiv(c.raw)


def resolve(query: str, prefer_published: bool = True, long_venues: bool = False,
            first_author: str = "") -> Result:
    kind, val = classify(query)

    if kind == "doi":
        try:
            m = crossref_by_doi(val)
        except urllib.error.HTTPError:
            return Result(None, f"DOI {val} not found in Crossref")
        e = entry_from_crossref(m, long_venues)
        if e.published or not prefer_published:
            return Result(e)
        title = (m.get("title") or [""])[0]
        authors = m.get("author") or []
        fa = (authors[0].get("family") or "") if authors else ""
        pub = _pick_published(find_candidates(title, fa))
        if pub:
            return Result(_entry_from_candidate(pub, long_venues), f"published version of preprint doi:{val}")
        return Result(e, "preprint; no published version found")

    if kind == "arxiv":
        try:
            r = arxiv_by_id(val)
        except LookupError as ex:
            return Result(None, str(ex))
        if prefer_published:
            fa = r["authors"][0][0] if r["authors"] else ""
            if r.get("doi") and not is_preprint_doi(r["doi"]):
                try:
                    return Result(entry_from_crossref(crossref_by_doi(r["doi"]), long_venues),
                                  f"published version of arXiv:{val} (DOI listed on arXiv)")
                except (SourceUnavailable, urllib.error.HTTPError):
                    pass
            pub = _pick_published(find_candidates(r["title"], fa))
            if pub:
                return Result(_entry_from_candidate(pub, long_venues), f"published version of arXiv:{val}")
            note = "no published version found"
            if r.get("journal_ref"):
                note += f" (arXiv journal-ref says: {r['journal_ref']}; check by hand)"
            return Result(entry_from_arxiv(r), note)
        return Result(entry_from_arxiv(r))

    # title
    cands = find_candidates(val, first_author)
    pub = _pick_published(cands) if prefer_published else None
    if pub:
        return Result(_entry_from_candidate(pub, long_venues), alternatives=[c for c in cands if c is not pub])
    try:
        ax = [c for c in arxiv_search(val) if title_similarity(c.title, val) >= TITLE_MATCH and same_numbers(c.title, val)]
    except SourceUnavailable as e:
        log(f"  ! arXiv unavailable: {e}")
        ax = []
    if first_author:
        ax = [c for c in ax if _same_author(c.first_author, first_author)]
    if ax:
        return Result(entry_from_arxiv(ax[0].raw), "preprint; no published version found")
    if cands:  # e.g. only a preprint DOI record (bioRxiv)
        return Result(_entry_from_candidate(cands[0], long_venues), "preprint; no published version found")
    return Result(None, "no record with a matching title in Crossref, DBLP or arXiv")
