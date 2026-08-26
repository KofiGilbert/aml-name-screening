import pytest

from screening.engine import Thresholds, screen, screen_batch


def test_exact_name_escalates(watchlist):
    result = screen("Viktor Anatolyevich Petrov", watchlist)
    assert result.band == "ESCALATE"
    assert result.hits[0].entry.uid == "10001"


def test_alias_hit_is_flagged_as_alias(watchlist):
    result = screen("Muhammad Al Amin Hassan", watchlist)
    hit = result.hits[0]
    assert hit.entry.uid == "10002"
    assert hit.matched_alias is True


def test_unrelated_name_is_clear(watchlist):
    assert screen("Margaret Thompson-Reilly", watchlist).is_clear


def test_corporate_suffix_variant_still_matches(watchlist):
    result = screen("Northern Star Trading Co., Ltd.", watchlist)
    assert result.hits and result.hits[0].entry.uid == "10003"


def test_entity_type_filter_excludes_other_types(watchlist):
    # Screening a company name against individuals only must find nothing.
    assert screen("Golden Horizon Shipping SA", watchlist,
                  entity_type="individual").is_clear


def test_hits_are_sorted_by_descending_score(watchlist):
    result = screen("Sergey Volkov", watchlist, thresholds=Thresholds(review=0.3))
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)


def test_unscreenable_name_raises(watchlist):
    # Silently returning CLEAR would pass an unscreened party through.
    with pytest.raises(ValueError):
        screen("   ", watchlist)


def test_batch_skips_unscreenable_rows_without_aborting(watchlist):
    results = screen_batch(["Viktor Anatolyevich Petrov", "  ", "Olena Kovalenko"],
                           watchlist)
    assert len(results) == 2


def test_lowering_threshold_widens_the_net(watchlist):
    # "Sergey Volkoff" is a plausible misspelling of the alias "Sergey Volkov":
    # far enough off to clear a strict bar, close enough to surface on a loose one.
    strict = screen("Sergey Volkoff", watchlist, thresholds=Thresholds(review=0.95))
    loose = screen("Sergey Volkoff", watchlist, thresholds=Thresholds(review=0.60))
    assert len(loose.hits) > len(strict.hits)


def test_thresholds_are_recorded_on_the_result(watchlist):
    th = Thresholds(review=0.6, escalate=0.9)
    result = screen("Viktor Petrov", watchlist, thresholds=th)
    assert result.thresholds == th
