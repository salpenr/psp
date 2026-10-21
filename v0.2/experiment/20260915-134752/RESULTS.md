# PSP v0.2 first-success experiment — 20260915-134752

**Result:** 10/10 cases produced the expected signal. Chain verify: `{'ok': True, 'events': 38, 'head': '52b391f3623e31f09d9f0bc9a255de993a2d1ab98fa56d27c5a81aa6a9e0a928'}`.

| case | expected | produced | pass | row | unresolved | annotations | conflicts_with | why complete | note |
|---|---|---|---|---|---|---|---|---|---|
| 01-success-write-write-0-X_md | CONFLICT | CONFLICT | PASS | WRITE/WRITE | - | - | claude/WRITE/87a62eac5471 | True | grok reference 'X.md'; both workers are live separate processes |
| 01-success-write-write-1-__X_md | CONFLICT | CONFLICT | PASS | WRITE/WRITE | - | HISTORICAL_CONFLICT | claude/WRITE/87a62eac5471 | True | grok reference './X.md'; both workers are live separate processes |
| 01-success-write-write-2-foo____X_md | CONFLICT | CONFLICT | PASS | WRITE/WRITE | - | HISTORICAL_CONFLICT | claude/WRITE/87a62eac5471 | True | grok reference 'foo/../X.md'; both workers are live separate processes |
| 02-control-read-read | CLEAR | CLEAR | PASS | no baseline conflict row TRUE; CLEAR conditions 1-10 satisfied | - | HISTORICAL_CONFLICT | - | - | HISTORICAL_CONFLICT expected in annotations (B23) |
| 03-uncertainty-identity | UNKNOWN | UNKNOWN | PASS | - | SAME/DISTINCT(ac1f0a7a1093,d8faa796072a) | - | - | - | SAME/DISTINCT unresolved: exactly one reference exists |
| 04-uncertainty-dead-claimant | UNKNOWN | UNKNOWN | PASS | - | LIVE(06308ad09242) | HISTORICAL_CONFLICT,INSTANCE_PROCESS_GONE | - | - | claude's claiming process exited; KG-05 exposure |
| 05-after-operator-release | CLEAR | CLEAR | PASS | no baseline conflict row TRUE; CLEAR conditions 1-10 satisfied | - | HISTORICAL_CONFLICT | - | - | operator release (KG-04) closed the dead claim; HISTORICAL_CONFLICT expected |
| 06-review-then-write-owner-s23 | CONFLICT | CONFLICT | PASS | WRITE/REVIEW (owner §23: LIVE WRITE on same artifact alters the current reviewed state) | - | HISTORICAL_CONFLICT | grok/REVIEW/690e2d595e6d | - | review bound to current revision; T-B6 |
| 07-superseded-review | CLEAR | CLEAR | PASS | no baseline conflict row TRUE; CLEAR conditions 1-10 satisfied | - | HISTORICAL_CONFLICT,SUPERSEDED_REVIEW | - | - | B24: CLEAR + SUPERSEDED_REVIEW; no live writer |
| 08-cli-transient-pids | CONFLICT | CONFLICT | PASS | WRITE/WRITE | - | HISTORICAL_CONFLICT,PROBE_UNAVAILABLE | claude/WRITE/03ed773e97eb | - | IN-01: CLI pids are transient, probe unavailable, LIVE by rule; exit code 0 (observational) |

## Metrics after the run

```json
{
  "claims": 14,
  "evaluations": 11,
  "signals": {
    "CLEAR": 4,
    "CONFLICT": 5,
    "UNKNOWN": 2
  },
  "unresolved_propositions": {
    "SAME/DISTINCT": 1,
    "LIVE": 1
  },
  "annotations": {
    "HISTORICAL_CONFLICT": 9,
    "INSTANCE_PROCESS_GONE": 1,
    "SUPERSEDED_REVIEW": 1,
    "PROBE_UNAVAILABLE": 2
  },
  "conflicts_then_released_without_ready": 3,
  "operator_releases": 1,
  "interventions": 0,
  "attempted_release_other": 0,
  "reclassified": 0,
  "verdicts": {},
  "stale_instances": 1
}
```

## Environment

```json
{
  "python": "3.11.9",
  "platform": "win32",
  "psp2_version": "0.2-r2",
  "profile": "psp-v0.2-baseline",
  "store": "<home>\\psp\\v0.2\\experiment\\20260915-134752\\psp-v0.2.db",
  "workspace": "<home>\\psp\\v0.2\\experiment\\20260915-134752\\workspace",
  "run": "20260915-134752"
}
```

Bases: one `*.basis.json` per case beside this file. Store: `psp-v0.2.db` (append-only, hash-chained).