"""Command-line entry point.

Two modes, matching how screening is actually run in a remediation programme:
one-off lookups while an analyst is on a case, and batch runs over an
onboarding or remediation file.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .engine import Thresholds, screen, screen_batch
from .queue import ReviewQueue
from .watchlist import Watchlist

BANNER_WIDTH = 78


def _load(path: str) -> Watchlist:
    p = Path(path)
    if not p.exists():
        sys.exit(f"watchlist not found: {p}")
    return Watchlist.from_json(p) if p.suffix == ".json" else Watchlist.from_csv(p)


def _print_result(result) -> None:
    print("=" * BANNER_WIDTH)
    print(f"SUBJECT : {result.query}")
    print(f"OUTCOME : {result.band}   ({len(result.hits)} hit(s))")
    if result.is_clear:
        print("No watchlist entry scored above the review threshold.")
        return
    print("-" * BANNER_WIDTH)
    for hit in result.hits:
        via = f"  (via alias {hit.matched_name!r})" if hit.matched_alias else ""
        print(f"[{hit.band:<8}] {hit.score:.3f}  {hit.entry.name}{via}")
        print(f"{'':11} {hit.entry.list_name} · uid {hit.entry.uid} · "
              f"{hit.entry.country or 'n/a'} · {'|'.join(hit.entry.programs) or 'n/a'}")
        d = hit.detail
        print(f"{'':11} jaro={d.jaro:.3f} token={d.token:.3f} phonetic={d.phonetic:.3f}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="screen", description="AML sanctions / PEP name screening")
    ap.add_argument("--watchlist", default="data/sample_sdn.csv",
                    help="watchlist CSV or JSON (default: %(default)s)")
    ap.add_argument("--review-threshold", type=float, default=Thresholds().review)
    ap.add_argument("--escalate-threshold", type=float, default=Thresholds().escalate)
    ap.add_argument("--entity-type", choices=["individual", "entity", "vessel"],
                    help="restrict comparison to one party type")
    ap.add_argument("--db", help="record hits to this SQLite review queue")
    ap.add_argument("--case-ref", default="", help="case reference stored with alerts")

    sub = ap.add_subparsers(dest="cmd", required=True)
    one = sub.add_parser("name", help="screen a single name")
    one.add_argument("value")
    batch = sub.add_parser("batch", help="screen a CSV column of names")
    batch.add_argument("path")
    batch.add_argument("--column", default="name")
    sub.add_parser("stats", help="show review-queue statistics")

    args = ap.parse_args(argv)
    th = Thresholds(review=args.review_threshold, escalate=args.escalate_threshold)
    if th.escalate < th.review:
        sys.exit("escalate threshold cannot be below the review threshold")

    if args.cmd == "stats":
        if not args.db:
            sys.exit("stats needs --db")
        for k, v in ReviewQueue(args.db).stats().items():
            print(f"{k:16} {v}")
        return 0

    wl = _load(args.watchlist)
    queue = ReviewQueue(args.db) if args.db else None

    if args.cmd == "name":
        result = screen(args.value, wl, thresholds=th, entity_type=args.entity_type)
        _print_result(result)
        if queue:
            queue.record(result, case_ref=args.case_ref)
        # Non-zero exit on a hit lets this drop straight into a pipeline.
        return 0 if result.is_clear else 2

    with open(args.path, newline="", encoding="utf-8") as fh:
        names = [r[args.column] for r in csv.DictReader(fh) if r.get(args.column)]
    results = screen_batch(names, wl, thresholds=th, entity_type=args.entity_type)
    flagged = [r for r in results if not r.is_clear]
    for r in flagged:
        _print_result(r)
        if queue:
            queue.record(r, case_ref=args.case_ref)
    print("=" * BANNER_WIDTH)
    print(f"screened {len(results)} name(s) against {len(wl)} watchlist entries; "
          f"{len(flagged)} flagged for review")
    return 0 if not flagged else 2


if __name__ == "__main__":
    raise SystemExit(main())
