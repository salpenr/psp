# PSP v0.2 — EXPERIMENTAL IMPLEMENTATION FREEZE (revision 2) — ATTACK TARGET

**Frozen 2026-09-15 by Claude per Ruben's impl-r2 repair authorization.** Exactly two reproduced defects from Grok's frozen impl-r1 attack were repaired. Nothing else changed. impl-r1 (`psp-v0.2-impl-r1` / `cae8afb`) preserved unchanged as evidence. Grok attacks these exact bytes next; GPT reconciles; Ruben decides on the shared-ledger trial. example-project HOLD.

| Item | Value |
|---|---|
| Tag | `psp-v0.2-impl-r2` (annotated, object `9548f7ff561ede5b544d32929ab8bd08f54d9f80`) |
| Commit | `a55aef945e598a0f1b3b9590254002ff7e5184cb` |
| Parent freeze | `psp-v0.2-impl-r1` / `cae8afb` (untouched: `git diff --quiet psp-v0.2-impl-r1 -- v0.2/experiment/20260915-133136` passes; v0.1 code untouched too) |
| Implementation | `v0.2/psp2.py` sha256 `f4033d823acadd9239efc2d606b4cea6527f36bb7f00c4033c2928115bba3ba3` (r1 was `a55285ea…`) |
| Tests | `v0.2/test_psp2.py` sha256 `715a125da7197df6d69a58ff564db8dba203a1e155155b782523d8901737bbb7` — **66 tests: 65 pass, 1 skipped (symlink privilege), 0 fail**; log `v0.2/TEST-LOG-impl-r2.txt` sha256 `dfbee62b…` |
| Experiment rerun | `experiment/20260915-134752/` **10/10** expected signals (same script, same cases as r1); `RESULTS.md` `d11c72af…`, `results.json` `ec24519e…`, store `679695c9…` (committed) |
| Change set | `v0.2/evidence/diff-r1-to-r2.psp2.patch` sha256 `9ca5e4ba…` (55 changed lines in psp2.py: +47 / −8) and `diff-r1-to-r2.test_psp2.patch` (+97 / −1) |
| Grok's own reproducer under r2 | `v0.2/evidence/grok-attack_impl_r1-rerun-under-r2.results.json` sha256 `5b64b3c6…` plus stdout; his original r1 results file was restored byte-for-byte after the run |
| Environment | Python 3.11.9, Windows 11 (10.0.26200), NTFS; `ENVIRONMENT-CAPABILITIES.json` unchanged |

Reproduce:

```bash
cd <home>/psp && git status --short && git rev-parse psp-v0.2-impl-r2^{commit} && sha256sum v0.2/psp2.py v0.2/test_psp2.py && git diff --quiet psp-v0.2-impl-r1 -- v0.2/experiment/20260915-133136 && echo r1-evidence-untouched && cd v0.2 && python -m unittest test_psp2 && python experiment_first_success.py
```

## Exactly what changed from r1 (and nothing else)

### Repair 1 — shared-instance false CLEAR (Grok impl-r1 hits IN-03 + IN-02)

**r1 behavior:** two distinct CLI processes claiming with the same `--instance` / `PSP2_INSTANCE`, both WRITE, evaluated **CLEAR + SELF_OVERLAP**, because `same_instance` was computed as `instance_id == instance_id`.

**r2 behavior:** "same working instance" is treated as the relational proposition it is (baseline §9.2, §14). New method `PSP2.same_instance(s, c)` returns `distinct` / `established` / `unresolved` with the rule that fired:

| Evidence | Result |
|---|---|
| tokens differ | `distinct` |
| same token, any pid on either claim is transient (CLI, IN-01) | `unresolved` — possession cannot be tied to a process |
| same token, the same non-transient process presented it for both claims | `established` |
| same token, two live non-transient processes | `unresolved` (TOKEN_SHARED) |
| same token, earlier process gone, later live process presents it | `established` — continuity by possession (KG-01 assumption kept) |
| same token, states unavailable / both gone | `unresolved` |

`SELF_OVERLAP` is annotated only on `established`. On `unresolved`, if the pair could conflict, the evaluation records `unresolved: same working instance(a,b)` and the signal is **UNKNOWN**; if the pair cannot conflict (READ/READ), the relationship is recorded as unresolved-but-harmless and the signal is CLEAR. The `claims()` view now carries `pid_kind` on each pid tuple to support this; no schema change.

**Grok's reproducer under r2:** case IN-03 signal is now `UNKNOWN` (was `CLEAR`), `SELF_OVERLAP` absent. His script still prints `HIT` for IN-03 because its predicate tests for the `TOKEN_SHARED` annotation specifically, not the signal; the repair routes this case through the same-instance proposition as Ruben's order specifies, not through TOKEN_SHARED. Recorded here so the reconciliation does not read his flag as "unrepaired."

### Repair 2 — NULL operation class (IN-06)

**r1 behavior:** a `CLAIMED` row with NULL `op_class` (reachable only by direct SQL insert) fell through `_baseline_row` into the REVIEW/WRITE branch, where the WRITE claim was selected as the "review," and produced **CONFLICT** by accident. Test B11 passed for the wrong reason.

**r2 behavior:** in `evaluate`, `classes_ok` is computed per candidate; an unestablished class cannot be assumed compatible (`could_conflict` is true) and, once the pair is SAME, records `unresolved: operation class(<claim>)` and continues without consulting any row. `_baseline_row` additionally guards its inputs and returns `UNRESOLVED` with the same proposition if it is ever called with a class outside `CLASSES`. Signal: **UNKNOWN**, conflicts empty. Test B11 now asserts UNKNOWN and the proposition text. Grok's reproducer case IN-06 under r2: `miss`, signal `UNKNOWN`.

### Supporting change

`HASH_DOMAIN = "psp/0.2-r1"` is pinned separately from `VERSION` (now `0.2-r2`) so that the r1 evidence store still verifies under r2 code (test `test_R2_r1_evidence_store_still_verifies` proves it on a temporary copy).

### Regression tests added (7)

`T_R2_GrokRegressions`: shared token across two CLI processes → UNKNOWN with the proposition; shared token READ/READ → CLEAR with the relationship recorded unresolved; same process same token → SELF_OVERLAP (IN-02 preserved); restart continuity by token → SELF_OVERLAP (KG-01 preserved); Grok's exact raw-insert NULL-class case → UNKNOWN with `operation class(deadbeef0001)`; `_baseline_row` guard direct; r1 store verifies under r2.

## Not repaired in this cycle (as ordered; still exposed by Grok's script under r2)

IN-01 CLI transient-pid liveness (`HIT`, CLEAR + PROBE_UNAVAILABLE); KG-13 rename / dead ARTIFACT_MOVED path (`HIT`); KG-09 two stores (`HIT`); IN-04/KG-15 annotation placement (`miss` in both r1 and r2: the annotation lands on the pre-replace subject, not the evaluated claim); superseded-review semantics; all other known gaps.

## One incident during this cycle, recorded

The first version of the new store-verification test opened the frozen r1 experiment store directly; the constructor's schema script and version pragma **wrote to that file**, and `git status` showed the r1 evidence modified. The bytes were restored from git (hash `964cfeb4…` re-verified) and the test was changed to verify a temporary copy. Consequence worth attacking: **any `PSP2(path)` construction, including CLI `verify`/`why`, mutates the store header**; a read-only open mode does not exist in r2. Not repaired (out of this cycle's scope); recorded as a candidate for the next known-gaps revision.

STOP. No further repairs. Grok attacks `psp-v0.2-impl-r2`.
