"""Minimal .bib reader (enough for check mode; never rewrites the input)."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BibItem:
    type: str
    key: str
    fields: dict[str, str]
    line: int


def _value(s: str, i: int) -> tuple[str, int]:
    while s[i].isspace():
        i += 1
    if s[i] == "{":
        depth, j = 0, i
        while True:
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    return s[i + 1:j], j + 1
            j += 1
    if s[i] == '"':
        j = i + 1
        while s[j] != '"' or s[j - 1] == "\\":
            j += 1
        return s[i + 1:j], j + 1
    m = re.match(r"[^,}\s]+", s[i:])
    return m.group(0), i + m.end()


def parse_bib(text: str) -> list[BibItem]:
    items = []
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        typ = m.group(1).lower()
        if typ in ("comment", "string", "preamble"):
            continue
        i, fields = m.end(), {}
        while True:
            fm = re.compile(r"\s*([\w\-]+)\s*=\s*").match(text, i)
            if not fm:
                break
            val, i = _value(text, fm.end())
            fields[fm.group(1).lower()] = re.sub(r"\s+", " ", val).strip()
            cm = re.compile(r"\s*,").match(text, i)
            if not cm:
                break
            i = cm.end()
        items.append(BibItem(typ, m.group(2), fields, text.count("\n", 0, m.start()) + 1))
    return items


PREPRINT_MARKERS = re.compile(r"arxiv|corr\b|preprint|biorxiv|medrxiv|ssrn|research square", re.I)


def is_preprint(item: BibItem) -> bool:
    f = item.fields
    blob = " ".join(f.get(k, "") for k in ("journal", "booktitle", "howpublished", "note", "archiveprefix", "eprinttype", "publisher"))
    return bool(PREPRINT_MARKERS.search(blob)) or f.get("doi", "").lower().startswith(("10.48550/", "10.1101/"))


def arxiv_id(item: BibItem) -> str | None:
    f = item.fields
    for k in ("eprint", "journal", "note", "url", "howpublished", "doi", "volume"):
        m = re.search(r"(\d{4}\.\d{4,5})", f.get(k, ""))
        if m and (k != "doi" or "48550" in f.get(k, "")):
            return m.group(1)
    return None


def latex_to_plain(s: str) -> str:
    """Rough LaTeX -> plain text for searching: {\\'e} -> e, \\& -> &, braces dropped."""
    s = re.sub(r"\\[`'^\"~=.uvHckrb]\s*(?=[{A-Za-z])", "", s)  # accent commands
    s = re.sub(r"\\(ss|ae|oe|o|l|i|AE|OE|O|L)\b", lambda m: {"ss": "ss", "ae": "ae", "oe": "oe", "o": "o", "l": "l", "i": "i",
                                                         "AE": "AE", "OE": "OE", "O": "O", "L": "L"}[m.group(1)], s)
    s = re.sub(r"\\([&%#_$])", r"\1", s)
    return re.sub(r"[{}]", "", s)


def first_author_family(item: BibItem) -> str:
    a = latex_to_plain(item.fields.get("author", "").split(" and ")[0].strip())
    return a.split(",")[0].strip() if "," in a else a.rsplit(" ", 1)[-1]


def plain_title(item: BibItem) -> str:
    return latex_to_plain(item.fields.get("title", ""))


def local_tidy(item: BibItem):
    """Formatting-only cleanup of an entry no registry could confirm.

    Never adds or changes content: braces acronyms in the title, converts
    accented characters, tidies page ranges, shortens known conference names
    (which also removes Scholar's doubled years). Journal names and author
    spellings are left as they are.
    """
    from .bibtex import Entry, drop_year_prefix, protect_title, short_venue, tidy_pages, to_latex

    f = dict(item.fields)
    if "title" in f:
        f["title"] = protect_title(to_latex(f["title"], escape_specials=False))
    for k in ("author", "editor", "journal", "publisher"):
        if k in f:
            f[k] = to_latex(f[k], escape_specials=False)
    if "booktitle" in f:
        f["booktitle"] = short_venue(f["booktitle"]) or to_latex(drop_year_prefix(f["booktitle"]), escape_specials=False)
    if "pages" in f:
        f["pages"] = tidy_pages(f["pages"])
    return Entry(item.type, item.key, f, published=not is_preprint(item))
