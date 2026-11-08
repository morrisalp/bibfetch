"""Registry lookups: Crossref, DBLP, arXiv.

Every Entry built here comes from a single source record; fields are copied,
then only *formatted* (see bibtex.py). A `bibsource` field records where the
record came from (ignored by bibliography styles).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from . import __version__
from .bibtex import (
    Entry, clean_whitespace, drop_year_prefix, format_authors, make_key,
    protect_title, short_venue, strip_html, tidy_pages, to_latex,
)

UA = f"bibfetch/{__version__} (https://github.com/morrisalp/bibfetch)"
# Optional: Crossref's "polite pool" asks for a contact address. Opt-in only.
MAILTO = os.environ.get("BIBFETCH_MAILTO")


class SourceUnavailable(Exception):
    """The registry refused or failed (rate limit, bot check, outage)."""


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _get(url: str, accept: str = "application/json", tries: int = 3) -> bytes:
    headers = {"User-Agent": UA, "Accept": accept}
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                if r.status == 202:  # DBLP's bot check answers 202 with an empty page
                    raise SourceUnavailable(f"{urllib.parse.urlparse(url).netloc} returned 202 (bot check?)")
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                wait = min(int(e.headers.get("Retry-After") or 0) or 2 ** (attempt + 1), 15)
                time.sleep(wait)
                continue
            raise SourceUnavailable(f"{urllib.parse.urlparse(url).netloc}: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise SourceUnavailable(f"{urllib.parse.urlparse(url).netloc}: {e.reason}") from e
        except (TimeoutError, ConnectionError, OSError) as e:
            if attempt < tries - 1:
                time.sleep(2)
                continue
            raise SourceUnavailable(f"{urllib.parse.urlparse(url).netloc}: {e}") from e
    raise SourceUnavailable(url)


def _get_json(url: str) -> dict:
    data = _get(url)
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise SourceUnavailable(f"{urllib.parse.urlparse(url).netloc}: non-JSON reply (bot check?)") from e


_PARTICLES = {"von", "van", "de", "der", "den", "da", "di", "del", "della", "des", "du", "dos", "das", "la", "le", "ten", "ter", "zu", "af", "al", "el", "bin", "ibn"}


def split_name(name: str) -> tuple[str, str]:
    """'Sydney von Arx' -> ('von Arx', 'Sydney'); 'Yuan Gong' -> ('Gong', 'Yuan')."""
    toks = name.split()
    if len(toks) < 2:
        return (name, "")
    i = len(toks) - 1
    while i > 1 and toks[i - 1].lower() in _PARTICLES:
        i -= 1
    return (" ".join(toks[i:]), " ".join(toks[:i]))


# ---------------------------------------------------------------- candidates


@dataclass
class Candidate:
    source: str  # "crossref" | "dblp" | "arxiv"
    title: str
    year: str
    venue: str
    published: bool
    first_author: str  # family name
    ref: str  # DOI, DBLP key or arXiv id
    raw: dict

    def describe(self) -> str:
        return f"[{self.source}] {self.title} — {self.venue} {self.year} ({self.ref})"


# Preprint DOI prefixes: arXiv, bioRxiv/medRxiv, Research Square, SSRN, Preprints.org, TechRxiv
_PREPRINT_DOI = re.compile(r"^10\.(48550|1101|21203|2139|20944|36227)/", re.I)


def is_preprint_doi(doi: str) -> bool:
    return bool(_PREPRINT_DOI.match(doi))


# ---------------------------------------------------------------- Crossref

_CROSSREF = "https://api.crossref.org/works"


def _cr_url(path: str = "", **params: str) -> str:
    if MAILTO:
        params["mailto"] = MAILTO
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return f"{_CROSSREF}{path}{q}"


def _cr_year(m: dict) -> str:
    """Publication year. Never Crossref's 'created'/'deposited' dates: for old
    IEEE proceedings those are the digitization date (e.g. 2005 for ICASSP '79).
    Falls back to a year encoded in the DOI (10.1109/icassp.1979.1170788), else ''."""
    for k in ("published-print", "published-online", "issued"):
        parts = (m.get(k) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    y = re.search(r"\.((?:19|20)\d{2})\.", m.get("DOI", ""))
    return y.group(1) if y else ""


def _cr_first(m: dict, key: str) -> str:
    v = m.get(key) or []
    return clean_whitespace(strip_html(v[0])) if v else ""


def crossref_search(title: str, rows: int = 10, author: str = "") -> list[Candidate]:
    params = {"rows": str(rows), "query.bibliographic": title}
    if author:  # short/generic titles ("Segment anything") need the author to surface
        params["query.author"] = author
    d = _get_json(_cr_url(**params))
    out = []
    for m in d["message"]["items"]:
        t = _cr_first(m, "title")
        if not t:
            continue
        doi = m.get("DOI", "")
        authors = m.get("author") or []
        typ = m.get("type", "")
        out.append(Candidate(
            source="crossref", title=t, year=_cr_year(m),
            venue=_cr_first(m, "container-title") or (m.get("institution") or [{}])[0].get("name", "") or typ,
            published=typ in ("journal-article", "proceedings-article", "book-chapter", "book")
            and not is_preprint_doi(doi),
            first_author=(authors[0].get("family") or authors[0].get("name", "")) if authors else "",
            ref=doi, raw=m,
        ))
    return out


def crossref_by_doi(doi: str) -> dict:
    return _get_json(_cr_url("/" + urllib.parse.quote(doi)))["message"]


def entry_from_crossref(m: dict, long_venues: bool = False) -> Entry:
    doi = m.get("DOI", "")
    typ = m.get("type", "")
    title = _cr_first(m, "title")
    subtitle = _cr_first(m, "subtitle")
    if subtitle and subtitle.lower() not in title.lower():
        title = f"{title}: {subtitle}"
    authors = [
        (a.get("family") or a.get("name", ""), a.get("given", ""))
        for a in (m.get("author") or [])
    ]
    year = _cr_year(m)
    container = _cr_first(m, "container-title")
    f: dict[str, str] = {"title": protect_title(to_latex(title)), "author": format_authors(authors)}
    published = not is_preprint_doi(doi)

    if typ == "journal-article":
        etype = "article"
        f["journal"] = to_latex(container)
        if m.get("volume"):
            f["volume"] = m["volume"]
        if m.get("issue"):
            f["number"] = m["issue"]
    elif typ == "proceedings-article":
        etype = "inproceedings"
        venue = None if long_venues else short_venue(container)
        f["booktitle"] = venue or to_latex(drop_year_prefix(container))
    elif typ == "book-chapter":
        etype = "incollection"
        f["booktitle"] = to_latex(container)
        if m.get("publisher"):
            f["publisher"] = to_latex(m["publisher"])
    elif typ == "book":
        etype = "book"
        if m.get("publisher"):
            f["publisher"] = to_latex(m["publisher"])
    elif typ == "posted-content" or is_preprint_doi(doi):
        etype = "article"
        server = (m.get("institution") or [{}])[0].get("name", "") or m.get("publisher", "")
        if doi.lower().startswith("10.1101/"):
            server = "medRxiv" if "medrxiv" in json.dumps(m).lower() else "bioRxiv"
        f["journal"] = to_latex(f"{server} preprint") if server else "Preprint"
        published = False
    else:
        etype = "misc"
        if container:
            f["howpublished"] = to_latex(container)

    if m.get("page"):
        f["pages"] = tidy_pages(m["page"])
    f["year"] = year
    if doi:
        f["doi"] = doi
    f["bibsource"] = f"Crossref, doi:{doi}"
    return Entry(etype, make_key(authors, year, title), f, published=published)


# ---------------------------------------------------------------- DBLP

_DBLP = "https://dblp.org/search/publ/api"


def _dblp_authors(info: dict) -> list[tuple[str, str]]:
    a = (info.get("authors") or {}).get("author") or []
    if isinstance(a, dict):
        a = [a]
    out = []
    for x in a:
        name = re.sub(r"\s+\d{4}$", "", x.get("text", "") if isinstance(x, dict) else x)  # "Jane Doe 0001"
        out.append(split_name(name))
    return out


def dblp_search(title: str, hits: int = 10) -> list[Candidate]:
    d = _get_json(f"{_DBLP}?" + urllib.parse.urlencode({"q": title, "format": "json", "h": str(hits)}))
    out = []
    for h in (d["result"]["hits"].get("hit") or []):
        i = h["info"]
        authors = _dblp_authors(i)
        venue = i.get("venue", "")
        venue = venue[0] if isinstance(venue, list) else venue
        out.append(Candidate(
            source="dblp", title=clean_whitespace(i.get("title", "").rstrip(".")), year=i.get("year", ""),
            venue=venue, published=venue not in ("CoRR", "") and not is_preprint_doi(i.get("doi", "")),
            first_author=authors[0][0] if authors else "", ref=i.get("key", ""), raw=i,
        ))
    return out


def entry_from_dblp(i: dict, long_venues: bool = False) -> Entry:
    """Used when a DBLP record has no DOI (e.g. ICLR/NeurIPS via OpenReview)."""
    authors = _dblp_authors(i)
    title = clean_whitespace(i.get("title", "").rstrip("."))
    venue = i.get("venue", "")
    venue = venue[0] if isinstance(venue, list) else venue
    year = i.get("year", "")
    f: dict[str, str] = {"title": protect_title(to_latex(title)), "author": format_authors(authors)}
    if "Journal" in i.get("type", ""):
        etype = "article"
        f["journal"] = to_latex(venue)
        if i.get("volume"):
            f["volume"] = i["volume"]
        if i.get("number"):
            f["number"] = i["number"]
    else:
        etype = "inproceedings"
        f["booktitle"] = (None if long_venues else short_venue(venue)) or to_latex(venue)
    if i.get("pages"):
        f["pages"] = tidy_pages(i["pages"])
    f["year"] = year
    if i.get("ee") and "doi.org" not in str(i.get("ee")):
        ee = i["ee"][0] if isinstance(i["ee"], list) else i["ee"]
        f["url"] = ee
    f["bibsource"] = f"DBLP, {i.get('key', '')}"
    return Entry(etype, make_key(authors, year, title), f, published=venue != "CoRR")


# ---------------------------------------------------------------- arXiv

_ARXIV = "http://export.arxiv.org/api/query"
_ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

ARXIV_ID = re.compile(
    r"(?:arxiv(?:\.org)?[:/\s]*(?:abs/|pdf/)?|^)(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?(?:\.pdf)?/?$", re.I
)


def _arxiv_entries(xml: bytes) -> list[dict]:
    root = ET.fromstring(xml)
    out = []
    for e in root.findall("a:entry", _ATOM):
        idurl = e.findtext("a:id", "", _ATOM)
        m = re.search(r"abs/(.+?)(v\d+)?$", idurl)
        if not m:
            continue
        names = [clean_whitespace(a.findtext("a:name", "", _ATOM)) for a in e.findall("a:author", _ATOM)]
        prim = e.find("arxiv:primary_category", _ATOM)
        out.append({
            "id": m.group(1),
            "title": clean_whitespace(e.findtext("a:title", "", _ATOM)),
            "authors": [split_name(n) for n in names],
            "year": e.findtext("a:published", "", _ATOM)[:4],
            "primary": prim.get("term") if prim is not None else "",
            "doi": e.findtext("arxiv:doi", "", _ATOM),
            "journal_ref": clean_whitespace(e.findtext("arxiv:journal_ref", "", _ATOM)),
        })
    return out


def arxiv_by_id(aid: str) -> dict:
    res = _arxiv_entries(_get(f"{_ARXIV}?id_list={aid}", accept="application/atom+xml"))
    if not res or not res[0]["title"] or res[0]["title"].lower() == "error":
        raise LookupError(f"arXiv:{aid} not found")
    return res[0]


def arxiv_search(title: str, n: int = 5) -> list[Candidate]:
    # exact-phrase title search; punctuation confuses arXiv's parser
    phrase = " ".join(re.findall(r"[A-Za-z0-9]+", title))
    q = f'ti:"{phrase}"'
    res = _arxiv_entries(_get(f"{_ARXIV}?" + urllib.parse.urlencode({"search_query": q, "max_results": str(n)}),
                              accept="application/atom+xml"))
    return [Candidate("arxiv", r["title"], r["year"], "arXiv", False,
                      r["authors"][0][0] if r["authors"] else "", r["id"], r) for r in res]


def entry_from_arxiv(r: dict) -> Entry:
    f = {
        "title": protect_title(to_latex(r["title"])),
        "author": format_authors(r["authors"]),
        "journal": f"arXiv preprint arXiv:{r['id']}",
        "year": r["year"],
        "bibsource": f"arXiv API, arXiv:{r['id']}",
    }
    return Entry("article", make_key(r["authors"], r["year"], r["title"]), f, published=False)
