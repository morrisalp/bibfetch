"""BibTeX formatting: LaTeX escaping, title protection, venue names, keys, rendering.

Only formatting happens here. Nothing in this module adds or changes
bibliographic content (authors, titles, venues, numbers): it reshapes what a
source record already says.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"}

# ---------------------------------------------------------------- data model


@dataclass
class Entry:
    type: str  # article, inproceedings, ...
    key: str
    fields: dict[str, str] = field(default_factory=dict)
    published: bool = True  # False for arXiv / bioRxiv / other preprints

    def render(self) -> str:
        order = [
            "title", "author", "booktitle", "journal", "volume", "number",
            "pages", "publisher", "year", "doi", "url", "bibsource",
        ]
        names = [f for f in order if f in self.fields]
        names += [f for f in self.fields if f not in order]
        width = max(len(n) for n in names) if names else 0
        lines = [f"@{self.type}{{{self.key},"]
        for n in names:
            v = self.fields[n]
            if n == "month" and v.lower() in _MONTHS:  # BibTeX macro: jun -> "June"
                lines.append(f"  {n.ljust(width)} = {v.lower()},")
            else:
                lines.append(f"  {n.ljust(width)} = {{{v}}},")
        lines[-1] = lines[-1].rstrip(",")
        lines.append("}")
        return "\n".join(lines)


# ---------------------------------------------------------------- escaping

_ACCENTS = {
    "́": "'", "̀": "`", "̂": "^", "̈": '"', "̃": "~",
    "̄": "=", "̆": "u", "̇": ".", "̊": "r", "̋": "H",
    "̌": "v", "̧": "c", "̨": "k",
}
_SPECIAL_CHARS = {
    "ø": r"{\o}", "Ø": r"{\O}", "ß": r"{\ss}", "æ": r"{\ae}", "Æ": r"{\AE}",
    "œ": r"{\oe}", "Œ": r"{\OE}", "ł": r"{\l}", "Ł": r"{\L}", "ı": r"{\i}",
    "–": "--", "—": "---", "‘": "`", "’": "'", "“": "``", "”": "''",
    "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_", " ": " ",
}


_ASCII_SPECIALS = set("&%#_")


def to_latex(s: str, escape_specials: bool = True) -> str:
    """Unicode -> pdflatex-safe text (accents as {\\'e}, specials escaped).

    escape_specials=False is for text that is already LaTeX (an existing .bib
    field), where & % # _ are presumably escaped already.
    """
    out = []
    for ch in unicodedata.normalize("NFC", s):
        if ch in _ASCII_SPECIALS and not escape_specials:
            out.append(ch)
            continue
        if ch in _SPECIAL_CHARS:
            out.append(_SPECIAL_CHARS[ch])
            continue
        if ord(ch) < 128:
            out.append(ch)
            continue
        base, *marks = unicodedata.normalize("NFD", ch)
        if marks and len(marks) == 1 and marks[0] in _ACCENTS and ord(base) < 128:
            cmd = _ACCENTS[marks[0]]
            sep = " " if cmd.isalpha() else ""
            out.append(f"{{\\{cmd}{sep}{base}}}")
        else:
            out.append(ch)  # leave as UTF-8 (works with inputenc/xelatex)
    return "".join(out)


def clean_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_html(s: str) -> str:
    """Crossref titles sometimes carry JATS/HTML tags (<i>, <sub>, ...)."""
    return re.sub(r"<[^>]+>", "", s)


# ---------------------------------------------------------------- titles

_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9']*")  # hyphen parts judged separately


def _needs_protection(word: str) -> bool:
    """Acronyms and mixed-case names that bibliography styles would lowercase:
    SAM, BioSEN, FSD50K, wav2vec-style tokens with capitals, CLAPSep."""
    caps = sum(c.isupper() for c in word)
    return caps >= 2 or (caps >= 1 and not word[0].isupper())


def protect_title(title: str) -> str:
    """Wrap acronyms / mixed-case words in braces so styles keep their case.

    Proper nouns with ordinary capitalization (e.g. "Haitian") can't be told
    apart from title-cased words, so those are left alone.
    """
    if "{" in title:  # already hand-protected; don't touch
        return title
    # standard/version codes: "P.835", "G.711" (single capital + dot + digits)
    title = re.sub(r"\b([A-Z])\.(\d+)", r"{\1}.\2", title)

    def repl(m: re.Match) -> str:
        w = m.group(0)
        return "{" + w + "}" if _needs_protection(w) else w

    return _WORD.sub(repl, title)


# ---------------------------------------------------------------- venues

# (pattern, short name). Matched case-insensitively against the source's
# venue string (Crossref container-title or DBLP venue). Order matters.
_VENUES = [
    (r"\bICASSP\b|International Conference on Acoustics,? Speech,? and Signal Processing", "Proc. IEEE ICASSP"),
    (r"^INTERSPEECH\b|^Interspeech \d{4}|^Proc\.? Interspeech", "Proc. Interspeech"),
    (r"\bWASPAA\b|Applications of Signal Processing to Audio and Acoustics", "Proc. IEEE WASPAA"),
    (r"\bEUSIPCO\b|European Signal Processing Conference", "Proc. EUSIPCO"),
    (r"^ACL\b|Annual Meeting of the Association for Computational Linguistics", "Proc. ACL"),
    (r"^EMNLP\b|Empirical Methods in Natural Language Processing", "Proc. EMNLP"),
    (r"^NAACL\b|North American Chapter of the Association for Computational Linguistics", "Proc. NAACL"),
    (r"^EACL\b|European Chapter of the Association for Computational Linguistics", "Proc. EACL"),
    (r"^COLING\b|International Conference on Computational Linguistics", "Proc. COLING"),
    (r"^LREC\b|Language Resources and Evaluation Conference", "Proc. LREC"),
    (r"^NeurIPS\b|^NIPS\b|Neural Information Processing Systems", "Proc. NeurIPS"),
    (r"^ICML\b|International Conference on Machine Learning(?! and Applications)", "Proc. ICML"),
    (r"^ICLR\b|International Conference on Learning Representations", "Proc. ICLR"),
    (r"^CVPR\b|Computer Vision and Pattern Recognition", "Proc. CVPR"),
    (r"^ICCV\b|International Conference on Computer Vision", "Proc. ICCV"),
    (r"^ECCV\b|European Conference on Computer Vision", "Proc. ECCV"),
    (r"^WACV\b|Winter Conference on Applications of Computer Vision", "Proc. WACV"),
    (r"^AAAI\b|AAAI Conference on Artificial Intelligence", "Proc. AAAI"),
    (r"^IJCAI\b|International Joint Conference on Artificial Intelligence", "Proc. IJCAI"),
    (r"^ICDAR\b|International Conference on Document Analysis and Recognition", "Proc. ICDAR"),
]


def short_venue(name: str) -> str | None:
    """Short conference name ("Proc. Interspeech"), or None if unknown.

    Only used for conference proceedings; journals keep their full name.
    """
    for pat, short in _VENUES:
        if re.search(pat, name, re.I):
            return short
    return None


def drop_year_prefix(name: str) -> str:
    """'2023 IEEE Workshop on X (Y)' -> 'IEEE Workshop on X (Y)' (the year
    is already in the year field; Scholar-style doubled years look odd)."""
    return re.sub(r"^\s*(Proceedings of the\s+)?\d{4}\s+", lambda m: m.group(1) or "", name)


# ---------------------------------------------------------------- misc fields


def tidy_pages(p: str) -> str:
    p = p.replace("–", "-").replace("—", "-")
    return re.sub(r"\s*-+\s*", "--", p.strip())


def format_authors(authors: list[tuple[str, str]]) -> str:
    """[(family, given), ...] -> 'Family, Given and Family2, Given2'."""
    parts = []
    for family, given in authors:
        family, given = to_latex(family.strip()), to_latex(given.strip())
        parts.append(f"{family}, {given}" if given else f"{{{family}}}")
    return " and ".join(parts)


_STOP = {"a", "an", "the", "on", "of", "in", "for", "to", "and", "with", "from", "via", "towards", "toward", "is", "are", "do", "does", "can", "what", "how", "why", "when"}


def ascii_slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def make_key(authors: list[tuple[str, str]], year: str, title: str) -> str:
    """Scholar-like key: firstauthorYYYYfirstword (e.g. gong2021ast)."""
    last = ascii_slug(authors[0][0]) if authors else "anon"
    words = [ascii_slug(w) for w in re.findall(r"[\w\-]+", title)]
    first = next((w for w in words if w and w not in _STOP), "")
    return f"{last}{year}{first}"


# ---------------------------------------------------------------- comparison


def norm_title(t: str) -> str:
    t = strip_html(t)
    t = re.sub(r"[{}\\]", "", t)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", t))


def same_numbers(a: str, b: str) -> bool:
    """'DNSMOS P.835: ...' vs 'DNSMOS: ...' are different papers despite ~0.96
    similarity; so are 'X v2' vs 'X v3'. Numbers in titles must agree."""
    return re.findall(r"\d+", norm_title(a)) == re.findall(r"\d+", norm_title(b))


def title_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher

    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()
