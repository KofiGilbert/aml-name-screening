import pytest

from screening.engine import screen


def test_hits_are_recorded(queue, watchlist):
    ids = queue.record(screen("Viktor Anatolyevich Petrov", watchlist), case_ref="CASE-1")
    assert len(ids) == 1
    assert len(queue.open_alerts()) == 1


def test_clear_result_records_nothing(queue, watchlist):
    assert queue.record(screen("Margaret Thompson-Reilly", watchlist)) == []


def test_disposition_closes_the_alert(queue, watchlist):
    alert_id = queue.record(screen("Viktor Anatolyevich Petrov", watchlist))[0]
    queue.disposition(alert_id, "false_positive", "DOB and nationality differ", "kgilbert")
    assert queue.open_alerts() == []


def test_disposition_requires_a_rationale(queue, watchlist):
    # An alert closed with no documented reason is an audit finding.
    alert_id = queue.record(screen("Viktor Anatolyevich Petrov", watchlist))[0]
    with pytest.raises(ValueError):
        queue.disposition(alert_id, "false_positive", "   ", "kgilbert")


def test_invalid_decision_is_rejected(queue, watchlist):
    alert_id = queue.record(screen("Viktor Anatolyevich Petrov", watchlist))[0]
    with pytest.raises(ValueError):
        queue.disposition(alert_id, "looks_fine", "n/a", "kgilbert")


def test_disposition_on_missing_alert_raises(queue):
    with pytest.raises(KeyError):
        queue.disposition(999, "true_match", "n/a", "kgilbert")


def test_dispositions_are_append_only(queue, watchlist):
    # A correction must add a row, not overwrite the original decision.
    alert_id = queue.record(screen("Viktor Anatolyevich Petrov", watchlist))[0]
    queue.disposition(alert_id, "false_positive", "initial read", "analyst1")
    queue.disposition(alert_id, "true_match", "DOB confirmed on review", "analyst2")
    history = queue.history(alert_id)
    assert [h["decision"] for h in history] == ["false_positive", "true_match"]


def test_stats_track_open_and_closed(queue, watchlist):
    alert_id = queue.record(screen("Viktor Anatolyevich Petrov", watchlist))[0]
    queue.record(screen("Muhammad Al Amin Hassan", watchlist))
    queue.disposition(alert_id, "true_match", "confirmed", "kgilbert")
    stats = queue.stats()
    assert stats["alerts"] == 2 and stats["closed"] == 1 and stats["open"] == 1


def test_open_alerts_can_filter_by_band(queue, watchlist):
    queue.record(screen("Viktor Anatolyevich Petrov", watchlist))
    assert all(a["band"] == "ESCALATE" for a in queue.open_alerts(band="ESCALATE"))
