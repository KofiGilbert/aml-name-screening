"""Watchlist loading.

Entries model the shape OFAC's SDN list actually publishes: a primary name, any
number of aliases (AKAs), an entity type, a programme, and a country. Aliases
are first-class — a large share of true hits match on an AKA rather than the
primary name, so they are screened with equal weight.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WatchlistEntry:
    uid: str
    name: str
    entity_type: str = "individual"   # individual | entity | vessel
    programs: tuple[str, ...] = ()
    country: str = ""
    aliases: tuple[str, ...] = ()
    list_name: str = "OFAC-SDN"

    def all_names(self) -> tuple[str, ...]:
        """Primary name plus aliases — every string worth screening against."""
        return (self.name,) + self.aliases


@dataclass
class Watchlist:
    entries: list[WatchlistEntry] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    @classmethod
    def from_csv(cls, path: str | Path) -> "Watchlist":
        """Load from CSV. `aliases` and `programs` are pipe-delimited, matching
        the flattened exports most compliance teams work with."""
        rows = []
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                rows.append(WatchlistEntry(
                    uid=row["uid"].strip(),
                    name=row["name"].strip(),
                    entity_type=(row.get("entity_type") or "individual").strip(),
                    programs=tuple(p for p in (row.get("programs") or "").split("|") if p),
                    country=(row.get("country") or "").strip(),
                    aliases=tuple(a.strip() for a in (row.get("aliases") or "").split("|") if a.strip()),
                    list_name=(row.get("list_name") or "OFAC-SDN").strip(),
                ))
        return cls(rows)

    @classmethod
    def from_json(cls, path: str | Path) -> "Watchlist":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([WatchlistEntry(
            uid=str(d["uid"]), name=d["name"],
            entity_type=d.get("entity_type", "individual"),
            programs=tuple(d.get("programs", ())),
            country=d.get("country", ""),
            aliases=tuple(d.get("aliases", ())),
            list_name=d.get("list_name", "OFAC-SDN"),
        ) for d in data])
