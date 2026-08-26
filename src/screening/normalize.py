"""Name normalization — the step that decides whether screening works at all.

Sanctions lists and onboarding forms spell the same party differently: accents,
corporate suffixes, honorifics, name order, punctuation. Comparing raw strings
produces both misses and noise, so every name is reduced to a canonical form
before any comparison happens.
"""
from __future__ import annotations

import re
import unicodedata

# Corporate suffixes carry no identifying signal — "Acme Ltd" and "Acme Limited"
# are the same party, and leaving them in inflates similarity between unrelated
# companies that merely share a legal form.
CORPORATE_SUFFIXES = {
    "ltd", "limited", "llc", "lc", "plc", "inc", "incorporated", "corp",
    "corporation", "co", "company", "gmbh", "ag", "sa", "sarl", "bv", "nv",
    "pty", "pte", "srl", "spa", "oy", "ab", "as", "aps", "kft", "zrt", "doo",
    "ooo", "oao", "pao", "jsc", "cjsc", "llp", "lp", "trust", "holdings",
    "holding", "group", "international", "intl",
}

HONORIFICS = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam", "mme", "hon",
    "rev", "capt", "col", "gen", "lt", "sgt", "sheikh", "sheik", "haji",
}

# Latin-script stand-ins for characters that survive NFKD unchanged.
_TRANSLITERATIONS = {
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "å": "a", "đ": "d",
    "ð": "d", "þ": "th", "ł": "l", "ı": "i", "ŋ": "n",
}

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """Fold accented characters onto their base letter (José -> Jose).

    Case-preserving: the map is written in lowercase, but names arrive in mixed
    case, so an uppercase Ø must fold to O rather than survive unchanged.
    """
    for src, dst in _TRANSLITERATIONS.items():
        text = text.replace(src, dst).replace(src.upper(), dst.upper() if len(dst) == 1 else dst.capitalize())
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def normalize(name: str, *, drop_corporate: bool = True) -> str:
    """Reduce a name to its canonical comparison form.

    Lowercased, accent-folded, punctuation-stripped, with honorifics and (by
    default) corporate suffixes removed. Returns "" for input that is entirely
    noise, which callers must treat as unscreenable rather than as a match.
    """
    if not name:
        return ""
    text = strip_accents(str(name)).lower()
    text = _PUNCT.sub(" ", text)
    tokens = _WS.sub(" ", text).strip().split()
    drop = HONORIFICS | (CORPORATE_SUFFIXES if drop_corporate else set())
    kept = [t for t in tokens if t not in drop]
    # An all-suffix string ("The Company Ltd") would otherwise normalize to
    # nothing; fall back to the punctuation-stripped tokens so it stays
    # screenable instead of silently becoming an empty match-everything key.
    return " ".join(kept or tokens)


def tokens(name: str, *, drop_corporate: bool = True) -> frozenset[str]:
    """Normalized tokens as a set — order-independent, for reordered names."""
    return frozenset(normalize(name, drop_corporate=drop_corporate).split())
