# PSP — Project Signal Protocol v0.1

**Built:** 2026-09-15 by Claude, on Ruben / GPT-Archivist instruction. **Attacker:** Grok. **Reviewer:** GPT/Archivist. **Owner:** Ruben.
**Files:** `psp.py` (module + CLI, stdlib only, SQLite), `test_psp.py` (24 tests, `python -m unittest -v test_psp`).

## The one question

> Who is doing what, to which artifact / revision, and since when?

PSP is a coordination and observability mechanism. It is **not** an authority mechanism, not an agent, not a runtime. `CLAIMED` means *this actor reports it is working on this target.* It never means *this actor may*, *this actor owns*, or *this actor is right*. PSP does not decide an internal task, example-project policy, epistemic correctness, or which AI is correct.

## Data model

One SQLite file (`%LOCALAPPDATA%\psp\psp.db`, or `--db`, or `$PSP_DB`). One table, `events`, append-only and hash-chained. Claims are a **view** derived from events; there is no claims table to get out of sync.

| Concept | Where |
|---|---|
| project | `events.project` (string) |
| actor ID | `events.actor` (subject) and `events.recorded_by` (writer). When they differ the event is **on-behalf** and flagged. |
| actor state | derived: `psp who` = active claims per actor with last event kind |
| operation / activity | `events.operation` (free text, e.g. `adversarial-review`) |
| target artifact | `events.target` (path relative to `root`) |
| target revision / hash | `events.target_hash` (sha256, hashed from disk at claim time unless `--hash` given) |
| READ_ONLY / WRITE | `events.mode` |
| timestamp | `events.ts` (UTC ISO, microseconds) plus `events.seq` (monotonic, authoritative for ordering) |
| claim / release lifecycle | `CLAIMED … RELEASED` on one `claim_id`; a claim is active until a RELEASED event names it |

Event vocabulary: `CLAIMED` `READY` `REVIEWING` `BREAK_FOUND` `SUPERSEDED` `RELEASED`. Nothing else. `SUPERSEDED` is never written directly; it is derived from a `READY`.

Every event also carries `host`, `pid`, `note`, `ref_claim` (another claim this one refers to), `cause_seq` (the event that caused it), `prev_hash`, `hash`.

## Lifecycle

```
claim   --mode READ_ONLY|WRITE      -> CLAIMED   (hash from disk, or --hash as the actor's belief)
event   --kind REVIEWING|BREAK_FOUND -> progress notes on a claim
ready   (WRITE only)                 -> READY with the new disk hash; every other active claim on the same
                                        target at a different hash gets SUPERSEDED (cause_seq = the READY)
release                              -> RELEASED; on behalf of another actor is allowed and labeled ON_BEHALF_OF
status / who / history / verify / check
```

## What PSP makes visible (and what it does about it: nothing)

| Situation | What is recorded | What the reader sees |
|---|---|---|
| Two READ_ONLY claims | both CLAIMED | no flag; compatible |
| WRITE claim while others are active on the target (any mode) | CLAIMED with `ref_claim` = the others, note `CONFLICT_AT_CLAIM …`, exit 2 | `CONFLICT` flag on **every** side, `live_conflicts` list |
| Two WRITE claims | both recorded; second flagged | `CONFLICT` on both |
| Target file changed after a claim, by anyone, by any means | nothing until someone looks | `DRIFT` (claimed hash ≠ disk hash now), `current_hash` shown |
| Writer publishes (`ready`) while reviewers hold the old hash | SUPERSEDED on each reviewer claim, `cause_seq`, `ref_claim` | `SUPERSEDED` + `DRIFT`; claim stays open until the reviewer releases |
| Actor claims with `--hash X` but disk is Y | `target_hash` = X (belief), note `HASH_MISMATCH expected=X actual=Y`, exit 3 | `DRIFT` |
| Target does not exist yet | note `TARGET_MISSING_AT_CLAIM` | `TARGET_MISSING` |
| Crashed / stale actor | nothing happens by itself; `age_seconds` grows | anyone may `release --as <self>`; recorded as RELEASED on behalf, with who and why |
| Same actor claims the same target twice | no conflict with itself | (by design; see limitations) |
| Someone edits or deletes a row under the engine | UPDATE/DELETE triggers abort; if triggers are dropped, `verify` fails at that seq | `verify` → `ok: false, at_seq` |

**Default when a collision is visible: record it, flag it, exit 2, and do nothing else.** PSP never refuses a claim, never blocks a write, never releases anyone's claim by itself, never expires anything. Whether a conflict should warn, require acknowledgment, pause, or block is an owner policy decision that v0.1 leaves to Ruben. The exit codes exist so a caller *can* enforce a policy; PSP does not.

Exit codes: `0` clean · `1` error (bad claim id, wrong mode) · `2` recorded but a collision/drift is visible · `3` recorded but the actor's stated hash does not match disk.

## Guarantees (mechanical)

- Append-only at the engine (triggers) and detectable if bypassed (hash chain over `seq`, `prev_hash`, and all row fields; `verify` recomputes it).
- Ordering is `seq`, assigned inside `BEGIN IMMEDIATE`; concurrent writers serialize. Timestamps are informational.
- A claim's stated hash and the disk's actual hash are both kept when they differ; PSP never picks one.
- Conflicts computed at claim time are stored on the claim (`ref_claim`); conflicts computed at read time (`live_conflicts`) are recomputed from current active claims. A released collision disappears from `status` but not from `history`.

## Known limitations (deliberate, for the attacker)

1. **Actor identity is asserted, not authenticated.** `--as grok` is a string. `recorded_by` and `host`/`pid` make on-behalf and cross-process writes visible; nothing stops an actor from lying. Signing is out of v0.1.
2. **Drift is polled, not watched.** A change made outside PSP is visible only when someone runs `status`/`check`. There is no filesystem watcher.
3. **Same-actor claims never conflict with each other**, including two windows of the same actor. Actor granularity is the caller's choice (`--as claude-window-2`).
4. **`ready` reads the disk at that moment.** If the file changes between the writer's last edit and `ready`, the READY hash is whatever is on disk.
5. **A single machine, a single file.** No network, no multi-host clock; `host` is recorded, not reconciled.
6. **No policy.** See above. A caller that ignores exit code 2 has coordinated nothing, and PSP will not stop it.

## Non-goals

Authority, permission, ownership, locking, merge, correctness, an internal task, another project's architecture, an internal evaluation. If any of those appear to be happening inside PSP, that is a bug in the review, not a feature.
