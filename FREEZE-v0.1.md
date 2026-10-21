# PSP v0.1 — frozen 2026-09-15

**Attack this exact version.** Do not repair it during the attack.

| Item | Value |
|---|---|
| Repo | `<home>\psp` (local git) |
| Tag | `psp-v0.1` (annotated, object `f097a25ba8ca530f50a39e9fb54f829067dab3c0`) |
| Commit | `4c92fd598ee81055f487f72cbb59e35f6d2159ea` |
| `psp.py` sha256 | `50239133134058045aa1f18b4c3a96240a2e3d2d12bce23af85375170b2a2980` |
| `test_psp.py` sha256 | `c2b627e83185d5c74759dd18c9422f573a57236137e98b15b2a7b3df8ace6d7e` |
| `SPEC-v0.1.md` sha256 | `8b0e709d8dae47e0326e457099c01ec724a4d470231f98dd958529d570493e2e` |
| Python | 3.11.9 (stdlib only: sqlite3, hashlib, argparse, json, uuid) |
| Tests | `python -m unittest -v test_psp` → 24 run, 24 OK (0.7 s), run twice, second run on the tagged tree |

Reproduce the freeze check:

```bash
cd <home>/psp && git status --short && git rev-parse HEAD psp-v0.1^{commit} && sha256sum psp.py test_psp.py && python -m unittest test_psp
```

`git status --short` must print nothing except this file until the attack is over.

## What the tests cover (map to the listed failure cases)

| Failure case from the instruction | Test |
|---|---|
| two simultaneous writers | `Concurrency.test_simultaneous_writers_all_recorded_one_unflagged` (8 threads, 8 connections, one `BEGIN IMMEDIATE` each) |
| write while reviewers inspect an older revision | `Supersession.test_ready_marks_reviewers_of_old_revision_superseded` |
| target changed after claim | `Drift.test_target_changed_after_claim_shows_drift`, `test_check_command_exit_codes` |
| hash / revision mismatch | `HashMismatch.test_actor_believes_hash_a_file_is_hash_b` |
| review running against a superseded revision | `Supersession…superseded` (claim stays open, flagged) |
| stale claim / crashed actor | `ReleaseAndStale.test_stale_claim_never_expires_by_itself_and_shows_age`, `test_release_on_behalf_is_recorded_as_such` |
| actor identity ambiguity | `test_claim_recorded_by_someone_else_is_flagged` (visible, not prevented; see SPEC limitation 1) |
| event ordering | `Chain.test_verify_ok_and_ordering`, `test_deleted_row_leaves_a_gap` |
| concurrent reads | `ReadOnlyCompatibility` |
| WRITE/READ conflict visible | `WriteConflicts.*` (both sides flagged) |
| "claimed" mistaken for "authorized" | `NotAuthority.*` (no such vocabulary; nothing is ever blocked) |
| coordination reported clean while history shows a collision | `WriteConflicts.test_collision_stays_in_history_after_release` |
| tampering | `Chain.test_engine_refuses_update_and_delete`, `test_tamper_after_dropping_triggers_is_caught` |

## PSP v0.1 ATTACK TARGET (GPT/Archivist checklist, recorded 2026-09-15)

GPT reviewed the source and ruled: freeze this exact version, do not patch until Grok's evidence is preserved. Working tree verified clean (`git status --short` empty) at the time of this record.

| # | Item | Value |
|---|---|---|
| 1 | Exact source file | `psp.py` at tag `psp-v0.1` (commit `4c92fd598ee81055f487f72cbb59e35f6d2159ea`), 1 file, module + CLI |
| 2 | SHA-256 of source | `50239133134058045aa1f18b4c3a96240a2e3d2d12bce23af85375170b2a2980` |
| 3 | Exact test files | `test_psp.py` sha256 `c2b627e83185d5c74759dd18c9422f573a57236137e98b15b2a7b3df8ace6d7e` (24 tests, 9 classes, stdlib `unittest`) |
| 4 | Test results | 24 run, 24 OK, 0.7 s; run three times (pre-tag, on tagged tree, at this record) |
| 5 | Runtime | Python 3.11.9, Windows 11 (10.0.26200); `sqlite3` module 2.6.0 over SQLite library 3.45.1 |
| 6 | DB / schema version | **No explicit schema version.** `PRAGMA user_version` = 0 (never set). `journal_mode` = delete. Objects: table `events`, table `sqlite_sequence` (autoincrement), indexes `ix_claim`, `ix_project_target`, triggers `no_update`, `no_delete`. The only version marker is the hash-chain domain string `psp/0.1` (from `psp.VERSION`) mixed into every row hash. Recorded as-is; not patched. |
| 7 | Assumptions the tests make | see below |

Other files at the tag: `SPEC-v0.1.md` `8b0e709d…`, `README.md` `7a80c3c7…`, `.gitignore` `66bf3c9e…`.

### 7. Assumptions the tests make

- One machine, one local filesystem, one clock. `host` is recorded, never compared.
- Each test gets a fresh temp directory and a fresh db; no test touches the default `%LOCALAPPDATA%` db.
- Targets are plain files under one `root`; tests never use `..`, absolute targets, a second root, symlinks, junctions, or case-variant paths. Target identity is the stored `(project, target)` string pair, not the resolved inode.
- Actor identity is whatever string the caller passes. The concurrency test uses eight *different* names; no test has two processes with the same name.
- Tampering is tested only as edit-without-rehash and delete-without-renumber. No test rewrites history and recomputes the whole chain.
- On-behalf events are tested for visibility (`recorded_by`, `ON_BEHALF` flag, note prefix), not for whether a misleading-but-valid history can be built from them.
- Ordering is asserted via `seq`; `ts` is never asserted.
- The concurrency test uses threads with separate connections in one process, not separate OS processes.
- `time.sleep(0.05)` is enough for `age_seconds > 0`.
- The CLI tests call `main(argv)` in-process; exit codes are asserted, stdout is only spot-checked.

### GPT hypotheses handed to Grok with this target

H1 same-name actor collision · H2 valid chain after full history reconstruction · H3 same artifact, different path identity · H4 on-behalf history manipulation. Whatever Grok finds is recorded as: source version/hash → attack procedure → observed → expected → visible? → history reconstructable? → classification (bug / intended limitation / missing assumption / threat-model boundary / future requirement). No repair before that record exists.

## Not covered on purpose (start here, Grok)

- Identity is a string. Two processes both saying `--as claude` are the same actor to PSP.
- Drift is only seen when someone runs `status` or `check`.
- `ready` hashes whatever is on disk at that instant.
- Exit code 2 is advice. A caller that ignores it has not coordinated.
- Clock: `ts` is informational; `seq` is the order.
