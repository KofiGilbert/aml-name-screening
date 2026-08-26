"""Similarity scoring for sanctions screening.

No single metric is sufficient. Edit distance catches typos but not reordering;
token overlap catches reordering but not typos; phonetic keys catch
transliteration variants ("Mohammed"/"Muhammad") that defeat both. The engine
runs all three and combines them, because in screening a missed true match is a
regulatory failure while a false positive only costs analyst time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .normalize import normalize, tokens

# Weights favour recall: token overlap dominates because real-world name
# variation is far more often reordering/partial than character-level typos.
WEIGHT_JARO = 0.35
WEIGHT_TOKEN = 0.45
WEIGHT_PHONETIC = 0.20


def jaro_winkler(a: str, b: str, *, prefix_scale: float = 0.1) -> float:
    """Jaro-Winkler similarity in [0, 1]. Rewards a shared prefix, which is
    where deliberate obfuscation is least common."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    match_window = max(len(a), len(b)) // 2 - 1
    if match_window < 0:
        match_window = 0
    a_matched = [False] * len(a)
    b_matched = [False] * len(b)
    matches = 0
    for i, ch in enumerate(a):
        lo = max(0, i - match_window)
        hi = min(i + match_window + 1, len(b))
        for j in range(lo, hi):
            if b_matched[j] or b[j] != ch:
                continue
            a_matched[i] = b_matched[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    # Transpositions: matched characters that appear in a different order.
    transpositions = 0
    k = 0
    for i, ch in enumerate(a):
        if not a_matched[i]:
            continue
        while not b_matched[k]:
            k += 1
        if ch != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2
    jaro = (matches / len(a) + matches / len(b)
            + (matches - transpositions) / matches) / 3
    prefix = 0
    for x, y in zip(a[:4], b[:4]):
        if x != y:
            break
        prefix += 1
    return jaro + prefix * prefix_scale * (1 - jaro)


def token_set_ratio(a: str, b: str) -> float:
    """Jaccard overlap of normalized token sets — order-independent, so
    "Ivanov Sergei" scores identically to "Sergei Ivanov"."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


_VOWELS = re.compile(r"[aeiou]")
_DOUBLES = re.compile(r"(.)\1+")


def phonetic_key(name: str) -> str:
    """A deliberately coarse consonant skeleton.

    Transliteration from non-Latin scripts varies mostly in vowels and doubled
    consonants ("Muhammad"/"Mohamed"/"Mohammad"), so collapsing both leaves a
    stable key. Coarser than Double Metaphone on purpose: this is a recall
    signal feeding a weighted score, not a standalone decision.
    """
    canon = normalize(name)
    if not canon:
        return ""
    out = []
    for word in canon.split():
        # Keep the leading character even when it is a vowel — initial vowels
        # are stable across transliterations and distinguish Ali from Li.
        head, tail = word[0], _VOWELS.sub("", word[1:])
        skeleton = _DOUBLES.sub(r"\1", head + tail)
        skeleton = skeleton.replace("ph", "f").replace("ck", "k")
        skeleton = skeleton.replace("kh", "k").replace("gh", "g")
        out.append(skeleton)
    return " ".join(sorted(out))


@dataclass(frozen=True)
class Similarity:
    """The component scores behind a decision, kept separate so an analyst can
    see WHY something matched rather than being handed one opaque number."""
    jaro: float
    token: float
    phonetic: float
    combined: float


def similarity(query: str, candidate: str) -> Similarity:
    """Score a query name against one list entry."""
    qn, cn = normalize(query), normalize(candidate)
    if not qn or not cn:
        return Similarity(0.0, 0.0, 0.0, 0.0)
    jaro = jaro_winkler(qn, cn)
    token = token_set_ratio(query, candidate)
    qk, ck = phonetic_key(query), phonetic_key(candidate)
    phonetic = 1.0 if (qk and qk == ck) else jaro_winkler(qk, ck)
    combined = (WEIGHT_JARO * jaro
                + WEIGHT_TOKEN * token
                + WEIGHT_PHONETIC * phonetic)
    # An exact canonical match must never be dragged below 1.0 by the
    # component weights.
    if qn == cn:
        combined = 1.0
    return Similarity(jaro, token, phonetic, round(combined, 4))
