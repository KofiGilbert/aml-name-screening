"""The screening engine: score a name against a watchlist and band the result.

Three bands, because screening output feeds a human workflow rather than an
automated block:

  CLEAR      below the review floor — no analyst time spent
  REVIEW     plausible; a human must adjudicate before onboarding proceeds
  ESCALATE   strong enough that it goes to the AML officer, not the queue

Thresholds are configurable and recorded on every result. A screening decision
that cannot be reproduced later is worthless in an audit, so the score, the
threshold set, and the matched alias are all persisted with the hit.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .match import Similarity, similarity
from .normalize import normalize
from .watchlist import Watchlist, WatchlistEntry

REVIEW_THRESHOLD = 0.72
ESCALATE_THRESHOLD = 0.88


@dataclass(frozen=True)
class Thresholds:
    review: float = REVIEW_THRESHOLD
    escalate: float = ESCALATE_THRESHOLD

    def band(self, score: float) -> str:
        if score >= self.escalate:
            return "ESCALATE"
        if score >= self.review:
            return "REVIEW"
        return "CLEAR"


@dataclass(frozen=True)
class Hit:
    entry: WatchlistEntry
    matched_name: str          # the primary name or alias that actually matched
    score: float
    band: str
    detail: Similarity

    @property
    def matched_alias(self) -> bool:
        return normalize(self.matched_name) != normalize(self.entry.name)


@dataclass(frozen=True)
class ScreeningResult:
    query: str
    hits: tuple[Hit, ...]
    thresholds: Thresholds

    @property
    def band(self) -> str:
        """The result's band is its worst hit — one escalation is enough."""
        return self.hits[0].band if self.hits else "CLEAR"

    @property
    def is_clear(self) -> bool:
        return not self.hits


def screen(name: str,
           watchlist: Watchlist,
           *,
           thresholds: Thresholds | None = None,
           entity_type: str | None = None,
           limit: int = 10) -> ScreeningResult:
    """Screen one name against the watchlist.

    `entity_type` narrows the comparison set when the onboarding form already
    tells us whether the party is a person or a company — screening an
    individual against vessel names produces nothing but noise.
    """
    th = thresholds or Thresholds()
    canon = normalize(name)
    if not canon:
        # Empty after normalization means there is nothing to screen. Returning
        # CLEAR here would silently pass an unscreened party, so callers get an
        # explicit error instead.
        raise ValueError(f"name {name!r} normalizes to empty; cannot screen")

    hits: list[Hit] = []
    for entry in watchlist.entries:
        if entity_type and entry.entity_type != entity_type:
            continue
        best: tuple[float, str, Similarity] | None = None
        for candidate in entry.all_names():
            detail = similarity(name, candidate)
            if best is None or detail.combined > best[0]:
                best = (detail.combined, candidate, detail)
        if best is None:
            continue
        score, matched_name, detail = best
        if score >= th.review:
            hits.append(Hit(entry=entry, matched_name=matched_name, score=score,
                            band=th.band(score), detail=detail))

    hits.sort(key=lambda h: h.score, reverse=True)
    return ScreeningResult(query=name, hits=tuple(hits[:limit]), thresholds=th)


def screen_batch(names, watchlist: Watchlist, **kw) -> list[ScreeningResult]:
    """Screen many names, skipping unscreenable ones rather than aborting the
    run — a single bad row in a 10k-row remediation file must not stop it."""
    out = []
    for name in names:
        try:
            out.append(screen(name, watchlist, **kw))
        except ValueError:
            continue
    return out
