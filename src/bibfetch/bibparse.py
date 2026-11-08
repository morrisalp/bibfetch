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


def first_author_family(item: BibItem) -> str:
    a = item.fields.get("author", "").split(" and ")[0].strip()
    a = re.sub(r"[{}]", "", a)
    return a.split(",")[0].strip() if "," in a else a.rsplit(" ", 1)[-1]


def plain_title(item: BibItem) -> str:
    return re.sub(r"[{}]", "", item.fields.get("title", ""))
