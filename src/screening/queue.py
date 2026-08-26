"""The alert review queue.

Screening produces alerts; the regulatory value is in what happens to them
afterwards. This module is the audit trail: every alert, every disposition,
and who made it, in SQLite so a remediation run is reproducible months later.

Design rule: dispositions are append-only. Correcting a decision writes a new
row rather than overwriting the old one, because an examiner asking "what did
you know and when" needs the history, not just the current answer.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .engine import ScreeningResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject       TEXT NOT NULL,
    case_ref      TEXT,
    list_name     TEXT NOT NULL,
    entry_uid     TEXT NOT NULL,
    entry_name    TEXT NOT NULL,
    matched_name  TEXT NOT NULL,
    matched_alias INTEGER NOT NULL,
    score         REAL NOT NULL,
    band          TEXT NOT NULL,
    programs      TEXT,
    country       TEXT,
    review_thr    REAL NOT NULL,
    escalate_thr  REAL NOT NULL,
    screened_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dispositions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id   INTEGER NOT NULL REFERENCES alerts(id),
    decision   TEXT NOT NULL,
    rationale  TEXT NOT NULL,
    analyst    TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_band ON alerts(band);
CREATE INDEX IF NOT EXISTS idx_alerts_subject ON alerts(subject);
CREATE INDEX IF NOT EXISTS idx_disp_alert ON dispositions(alert_id);
"""

VALID_DECISIONS = {"true_match", "false_positive", "escalated", "pending_info"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ReviewQueue:
    db_path: str | Path = "alerts.db"

    def __post_init__(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        # Enforced per-connection, not once at setup: SQLite defaults foreign
        # keys OFF, so a disposition could otherwise reference a missing alert.
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def record(self, result: ScreeningResult, *, case_ref: str = "") -> list[int]:
        """Persist every non-clear hit. Returns the new alert ids."""
        ids: list[int] = []
        with closing(self._connect()) as conn:
            for hit in result.hits:
                cur = conn.execute(
                    """INSERT INTO alerts (subject, case_ref, list_name, entry_uid,
                           entry_name, matched_name, matched_alias, score, band,
                           programs, country, review_thr, escalate_thr, screened_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (result.query, case_ref, hit.entry.list_name, hit.entry.uid,
                     hit.entry.name, hit.matched_name, int(hit.matched_alias),
                     hit.score, hit.band, "|".join(hit.entry.programs),
                     hit.entry.country, result.thresholds.review,
                     result.thresholds.escalate, _now()))
                ids.append(int(cur.lastrowid))
            conn.commit()
        return ids

    def disposition(self, alert_id: int, decision: str, rationale: str,
                    analyst: str) -> int:
        """Record an analyst decision. A rationale is mandatory — an alert
        closed without a documented reason is an audit finding waiting to
        happen, so the queue refuses to store one."""
        if decision not in VALID_DECISIONS:
            raise ValueError(
                f"decision must be one of {sorted(VALID_DECISIONS)}, got {decision!r}")
        if not rationale.strip():
            raise ValueError("a disposition requires a written rationale")
        with closing(self._connect()) as conn:
            exists = conn.execute("SELECT 1 FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            if not exists:
                raise KeyError(f"no alert with id {alert_id}")
            cur = conn.execute(
                """INSERT INTO dispositions (alert_id, decision, rationale, analyst, decided_at)
                   VALUES (?,?,?,?,?)""",
                (alert_id, decision, rationale.strip(), analyst, _now()))
            conn.commit()
            return int(cur.lastrowid)

    def open_alerts(self, band: str | None = None) -> list[sqlite3.Row]:
        """Alerts with no disposition yet — the analyst's actual worklist."""
        sql = ("""SELECT a.* FROM alerts a
                  LEFT JOIN dispositions d ON d.alert_id = a.id
                  WHERE d.id IS NULL""")
        params: tuple = ()
        if band:
            sql += " AND a.band = ?"
            params = (band,)
        sql += " ORDER BY a.score DESC, a.id"
        with closing(self._connect()) as conn:
            return conn.execute(sql, params).fetchall()

    def history(self, alert_id: int) -> list[sqlite3.Row]:
        """Full disposition history for one alert, oldest first."""
        with closing(self._connect()) as conn:
            return conn.execute(
                "SELECT * FROM dispositions WHERE alert_id = ? ORDER BY id",
                (alert_id,)).fetchall()

    def stats(self) -> dict[str, int]:
        """Queue health: the numbers a team lead actually reports upward."""
        with closing(self._connect()) as conn:
            total = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            closed = conn.execute(
                "SELECT COUNT(DISTINCT alert_id) FROM dispositions").fetchone()[0]
            by_band = dict(conn.execute(
                "SELECT band, COUNT(*) FROM alerts GROUP BY band").fetchall())
            fp = conn.execute(
                "SELECT COUNT(*) FROM dispositions WHERE decision = 'false_positive'"
            ).fetchone()[0]
        return {"alerts": total, "closed": closed, "open": total - closed,
                "escalate": by_band.get("ESCALATE", 0),
                "review": by_band.get("REVIEW", 0),
                "false_positives": fp}
