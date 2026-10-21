# PSP v0.2 — EXPERIMENTAL IMPLEMENTATION FREEZE (revision 1) — ATTACK TARGET

**Frozen 2026-09-15 by Claude per Ruben's implementation order.** Grok attacks this exact revision. No repairs before independent review. Production NOT authorized. example-project HOLD.

| Item | Value |
|---|---|
| Repo | `<home>\psp` (v0.1 code byte-identical to tag `psp-v0.1`, verified) |
| Tag | `psp-v0.2-impl-r1` (annotated, object `a62efda354ac839ebc222c8b03f04e973d4f4b5a`) |
| Commit | `cae8afb9b24b1e39d61ac78a3de463a071978408` |
| Frozen design implemented | `psp-v0.2-design-r1` / `a7b459c`; mapping sha256 `a6daf322…` |
| Frozen requirements | `v0.2/PSP-v0.2-REQUIREMENTS-BASELINE.md` sha256 `55e9002f…` (Draft 5 + owner §23) |
| Known gaps | `v0.2/KNOWN-GAPS.md` — KG-15 (path-stable replacement, Grok) added per order; nothing repaired |
| Implementation | `v0.2/psp2.py` sha256 `a55285eacffc59c6ad47fe674a75c04885a30fdf738b3cf2c3e3e3520079dbf7` (~560 lines, stdlib only) |
| Tests | `v0.2/test_psp2.py` sha256 `d39ff168be89b1486ab3aa430eb4715615bd7441f95b0b0b75442a1be2757d2b` — 59 tests |
| Test result | **58 pass, 1 skipped, 0 fail**; log `v0.2/TEST-LOG-impl-r1.txt` sha256 `693559e8…`; skipped: `test_ID07_symlink` (symlink creation needs privilege on this box; recorded in `ENVIRONMENT-CAPABILITIES.json`) |
| First-success experiment | `v0.2/experiment_first_success.py` sha256 `ce4ff5ee…`; run `experiment/20260915-133136/`: **10/10 expected signals**; `RESULTS.md` sha256 `fb037264…`, `results.json` `a6c313c3…`, store `psp-v0.2.db` `964cfeb4…` (committed as evidence; chain verifies, 38 events, head `b662ef27…`) |
| Environment | Python 3.11.9, Windows 11 (10.0.26200), NTFS; capabilities: junction yes, hard link yes, symlink no (privilege), case-insensitive fs yes, file identity available yes |

Reproduce the freeze check:

```bash
cd <home>/psp && git status --short && git rev-parse psp-v0.2-impl-r1^{commit} && sha256sum v0.2/psp2.py v0.2/test_psp2.py && git diff --quiet psp-v0.1 -- psp.py test_psp.py && echo v0.1-untouched && cd v0.2 && python -m unittest test_psp2
```

## What the experiment showed (order §14, §15)

| Case | Expected | Produced | Note |
|---|---|---|---|
| Claude LIVE WRITE X; Grok WRITE `X.md` / `./X.md` / `foo/../X.md` (separate live processes) | CONFLICT | CONFLICT ×3 | WHY complete: distinct instances, WRITE/WRITE, SAME by file identity, lifecycle evidence, row, evaluation time |
| Control: READ/READ | CLEAR | CLEAR | HISTORICAL_CONFLICT annotation carried (B23) |
| Uncertainty: one reference does not exist | UNKNOWN | UNKNOWN | unresolved proposition named: `SAME/DISTINCT(a,b)` |
| Uncertainty: claimant process exited without RELEASE | UNKNOWN | UNKNOWN | `LIVE(claim)` unresolved, INSTANCE_PROCESS_GONE (KG-05 exposure) |
| After operator release of the dead claim | CLEAR | CLEAR | OPERATOR_RELEASE evidence class (KG-04) |
| REVIEW of current revision, then WRITE (owner §23) | CONFLICT | CONFLICT | row text names the owner sentence; T-B5/T-B6 encode it and would fail the old reading |
| Superseded review, no live writer | CLEAR | CLEAR | SUPERSEDED_REVIEW annotation (B24, §26) |
| Same success case through the CLI | CONFLICT | CONFLICT | PROBE_UNAVAILABLE annotation (IN-01); exit code 0 |

Metrics from the run: 14 claims, 11 evaluations (4 CLEAR / 5 CONFLICT / 2 UNKNOWN), 3 "conflict then released without READY", 1 operator release, 0 verdicts yet.

## Implementation decisions made during build (visible, for attack; not repairs of known gaps)

| ID | Decision | Why | Consequence to attack |
|---|---|---|---|
| IN-01 | A claim made through the CLI records the CLI's own pid as `pid_kind=transient`; the liveness probe (M-08) reports `unavailable` for transient pids and the claim is LIVE by rule with `PROBE_UNAVAILABLE`. A worker may pass `--worker-pid` to register a long-lived pid (`declared`); module-API callers are probed as `process`. | The CLI process exits immediately; probing it would mark every CLI-made claim dead within a second and turn the first-success test into UNKNOWN. The frozen design named "claimed from a shell that closed" as a failure mode without saying which pid to record. | CLI-made claims are never detected as dead (KG-05 does not fire for them); a dead CLI worker is closed only by operator release. Whether real workers can supply a long-lived pid is an open experimental question. |
| IN-02 | `instance_id` is minted per claim unless the worker presents an existing token at claim time, which binds the new claim to that instance (`--instance` / `PSP2_INSTANCE`). | Otherwise a worker's own sequential claims (REVIEW then WRITE) would conflict with itself. Same-instance overlap is annotated `SELF_OVERLAP`, never a row. | A worker that forgets to present its token becomes two instances and conflicts with itself (position 2 in the mapping, now observable). |
| IN-03 | TOKEN_SHARED fires only when the same token has been used from two **non-transient** pids that are both alive at evaluation time. | Restart-with-token (KG-01 continuity) must not look like sharing; transient CLI pids cannot be probed. | Token sharing through the CLI is invisible. |
| IN-04 | Identity is computed from **current** file identities at evaluation time for every claim's resolved path; claim-time fileid is kept and, if different at the same path, `ARTIFACT_REPLACED` is annotated (KG-15). | Grok's path-stable replacement case: current-fileid comparison keeps SAME. | A replaced file inherits the old claims' relationships; whether that is right is the KG-15 experiment. |
| IN-05 | v0.1's REVIEWING / BREAK_FOUND collapse into `note` (no lifecycle effect); SUPERSEDED is an annotation computed at evaluation, never an event; the v0.1 `--hash` on events is gone. | v0.1 findings B, K; design §3. | Notes cannot move a review to a new revision; a reviewer who wants to review B must claim again. |
| IN-06 | A `CLAIMED` row with a NULL operation class is reachable only by direct insert (the API and CLI refuse it). Traced in `_baseline_row`: a NULL class is neither READ/REVIEW nor WRITE, so the pair `(None, WRITE)` falls through to the REVIEW/WRITE branch, where `review = s if a == "REVIEW" else c` selects the **WRITE** claim as the "review"; its bound revision equals the current revision, so the branch returns CONFLICT. Test B11 asserts "not CLEAR" and passes for that accidental reason. | — | **Recorded as a defect candidate:** the baseline wants UNRESOLVED → UNKNOWN for an unestablished class (B11); the code yields CONFLICT by accident. Not repaired (freeze). Attack this and any other path where `_baseline_row` receives a class outside `CLASSES`. |

## Not covered (start here, Grok)

- IN-06 above: NULL operation class reaches the NON-CONFLICT branch rather than UNRESOLVED.
- Symlink alias class untested on this box (privilege).
- KG-13 rename mid-claim: the moved file makes the old claim's reference unresolvable → UNKNOWN, but `ARTIFACT_MOVED` is only computed when the old resolved path still resolves to the same fileid, which after a rename it does not; the annotation path is effectively dead in revision 1. Recorded, not repaired.
- Two stores on one workspace: honest but silent beyond the claim-domain string (KG-09).
- Pid reuse (M-08 falsifier) not exercised by a test; needs a forced pid collision.
- `metrics.conflicts_then_released_without_ready` is a proxy; the experiment run shows 3 that were the harness releasing claims between alias runs, not workers yielding.

STOP. No repairs before Grok's attack and GPT's reconciliation. Ruben decides whether PSP proceeds, changes, or stops.
