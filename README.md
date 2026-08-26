# aml-name-screening

Sanctions and PEP name screening: fuzzy matching against a watchlist, banded
outcomes, and an auditable review queue.

Screening is the control that decides whether a bank onboards a sanctioned
party. The hard part is not string comparison — it is being *right about the
tradeoff*. A missed true match is a regulatory failure; a false positive only
costs analyst time. This engine is tuned accordingly, and every decision it
produces is reproducible months later.

## Why three matching signals, not one

No single metric survives real-world name data:

| Signal | Catches | Misses |
| --- | --- | --- |
| Jaro-Winkler | typos, character drops | reordered names |
| Token-set (Jaccard) | reordering, partial names | spelling variation |
| Phonetic key | transliteration (`Mohammed`/`Muhammad`) | unrelated homophone-ish names |

All three run, and the weighted combination (`0.35 / 0.45 / 0.20`, favouring
token overlap) decides the band. The component scores travel with the result,
so an analyst sees *why* something matched rather than one opaque number.

## Bands

| Band | Meaning |
| --- | --- |
| `CLEAR` | below the review floor — no analyst time spent |
| `REVIEW` | plausible; a human adjudicates before onboarding proceeds |
| `ESCALATE` | strong enough to go to the AML officer, not the queue |

Thresholds (default `0.72` / `0.88`) are configurable and are **recorded on
every alert**, because a screening decision you cannot reproduce is worthless
in an examination.

## Install

```bash
pip install -e ".[dev]"
```

## Use

Screen one name:

```bash
screen name "Muhammad Al Amin Hassan"
```

```
SUBJECT : Muhammad Al Amin Hassan
OUTCOME : ESCALATE   (1 hit(s))
------------------------------------------------------------------------------
[ESCALATE] 1.000  Mohammed Al-Amin Hassan  (via alias 'Muhammad Al Amin Hassan')
            OFAC-SDN · uid 10002 · Syria · SDGT
            jaro=1.000 token=1.000 phonetic=1.000
```

Batch-screen a remediation file into a review queue:

```bash
screen --db alerts.db --case-ref REMED-2026-Q3 batch onboarding.csv --column customer_name
screen --db alerts.db stats
```

Exit code is `2` when anything is flagged, so it drops straight into a pipeline.

As a library:

```python
from screening import Watchlist, screen, ReviewQueue

wl = Watchlist.from_csv("data/sample_sdn.csv")
result = screen("Northern Star Trading Co., Ltd.", wl, entity_type="entity")

queue = ReviewQueue("alerts.db")
for alert_id in queue.record(result, case_ref="CASE-1"):
    queue.disposition(alert_id, "false_positive",
                      "Different jurisdiction and registration number", "kgilbert")
```

## The audit trail

Dispositions are **append-only**. Correcting a decision writes a new row rather
than overwriting the old one, because an examiner asking "what did you know and
when" needs the history, not just the current answer. A disposition without a
written rationale is rejected outright.

## Design notes

- **Aliases are first-class.** A large share of true hits match on an AKA, not
  the primary name, so aliases are screened with equal weight and the alert
  records which string actually matched.
- **Unscreenable input raises.** A name that normalizes to empty returns an
  error, never `CLEAR` — silently passing an unscreened party is the exact
  failure mode this tool exists to prevent.
- **Batch runs skip bad rows, not the run.** One malformed row in a 10k-row
  remediation file must not abort it.
- **Entity-type filtering** narrows comparison when the onboarding form already
  says whether the party is a person or a company.

## Tests

```bash
pytest
```

35 tests covering normalization, the three matching signals, banding,
threshold behaviour, and the queue's audit guarantees.

## Data

`data/sample_sdn.csv` is a small synthetic list in the shape OFAC's SDN file
publishes (primary name, AKAs, entity type, programme, country). It contains
**invented names for testing** — point `--watchlist` at the real consolidated
list for actual use.

## Licence

MIT
