# PSP — Project Signal Protocol

**An append-only, tamper-evident record of who is doing what, to which artifact, when several AI agents (and humans) work on one project.**

PSP is deliberately **not** an authority. It never approves, blocks, assigns, locks, or kills anything. It records claims and observations, and it reports one of three signals about overlapping work:

- **CLEAR**: no conflict rule fired. *This is not permission, and it doesn't mean nobody else is working here.*
- **CONFLICT**: a recorded overlap matches a conflict rule (for example two WRITE claims on the same artifact).
- **UNKNOWN**: the evidence is insufficient to decide.

## Why it exists

Agent oversight often depends on what agents say about themselves, and on monitors the agents can reach. PSP keeps those apart:

- **Self-report vs observation.** An agent's own statements are recorded as *self-state*, separate from observed facts such as a file's content hash at claim time and at READY.
- **Tamper-evident history.** Every event is appended to a hash chain; `verify` detects edits inside the chain.
- **Visible uncertainty.** When liveness or identity cannot be established, PSP says so (for example `PROBE_UNAVAILABLE`) instead of reporting health.

## Status

**Research prototype.** `v0.2/psp2.py` is the frozen v0.2 implementation (release `psp-v0.2-impl-r2`), published byte-identical to the reviewed code (see `PROVENANCE.md`). It was built against written requirements, attacked by independent AI reviewers, and repaired only where defects were reproduced. Known limitations are listed in `v0.2/KNOWN-GAPS.md`.

A three-agent observational pilot (October 2026) exposed limits that PSP v0.2 does **not** yet handle:

- **Identity is physical.** The same content in two repository copies is two different artifacts.
- **Released claims drop out of live overlap.** They appear only as rejected candidates in later evaluations, and in `history`.
- **Intended overlap only links one way.** It can be declared only by the later claimant, through `--relates-to`.
- **Missing participants are invisible.**
- **Stored evaluations are point-in-time.** They are not refreshed.
- **Liveness is unknowable** when agents act through short-lived CLI processes.
- **`verify` rewrites SQLite header bytes.** Hash a ledger *after* verifying it, or verify a copy.

`psp.py` is the earlier v0.1 implementation, kept for reference.

## Quick start (v0.2)

Python standard library only; there are no third-party dependencies. Tested with Python 3.11 (freeze records) and 3.12 on Windows.

```bash
cd v0.2
python psp2.py --db ./demo.db --json claim --project demo --as agent-a --op WRITE --target notes.md --root .
python psp2.py --db ./demo.db --json claim --project demo --as agent-b --op WRITE --target notes.md --root .   # -> CONFLICT
python psp2.py --db ./demo.db --json status
python psp2.py --db ./demo.db --json history
python psp2.py --db ./demo.db --json verify
```

**Commands:** `claim`, `evaluate`, `ready`, `note`, `release`, `status`, `history`, `verify`, `metrics`, `why`, `verdict`, `intervention`.

**Database:** `--db PATH` or the `PSP2_DB` environment variable. Without either, it defaults to a per-user location.

**Enforcement:** `--enforce-exit` is an explicit, opt-in exit-code mode for callers that want it. PSP itself enforces nothing.

**Tests:** `cd v0.2 && python -m unittest -v test_psp2`

## Repository layout

| Path | What it is |
|---|---|
| `v0.2/psp2.py`, `v0.2/test_psp2.py` | Frozen v0.2 implementation and its test suite |
| `v0.2/PSP-v0.2-REQUIREMENTS-BASELINE.md` | Requirements the implementation is held to |
| `v0.2/PSP-v0.2-DESIGN-MAPPING.md` | Requirement-to-mechanism mapping (M-01 … M-12) |
| `v0.2/FREEZE-*.md` | Freeze records: what was frozen, attacked, repaired |
| `v0.2/KNOWN-GAPS.md` | Known gaps, stated plainly |
| `v0.2/experiment/` | First-success experiment results (redacted; see `PROVENANCE.md`) |
| `v0.2/evidence/` | Repair diffs and the re-run of the independent attack |
| `SPEC-v0.1.md`, `FREEZE-v0.1.md`, `psp.py`, `test_psp.py` | v0.1, for history |

## How it was built

The project lead directed several AI agents under documented roles: builder, independent attacker, and reviewer. No change was accepted on its author's own word. The freeze records name the reviewers and rulings.

## License

MIT; see `LICENSE`.
