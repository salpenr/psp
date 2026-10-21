# Provenance

This repository was built from a private development repository, so that the published code can be checked against what was reviewed.

- **Frozen release:** `psp-v0.2-impl-r2` (private commit `a55aef945e598a0f1b3b9590254002ff7e5184cb`). Private HEAD at publication: `03b348d59504b18bcb8ae92e91915a0d87fe7bd8`.
- **`PROVENANCE.json`** lists every file in the private tree, with its private SHA-256 and one of four statuses:
  - **identical**: published byte-for-byte. This covers all implementation code, tests, and the repair diffs, including `v0.2/psp2.py` (SHA-256 `f4033d823acadd9239efc2d606b4cea6527f36bb7f00c4033c2928115bba3ba3`).
  - **redacted**: documents and experiment data where local machine details were replaced with placeholders: `<home>` (local user directory), `<host>` (machine name), `<dev>` (the storage-volume part of file identities), `<private-notes>` (private note paths), `example-project` and generic phrases (internal project and task names). Only the public SHA-256 is listed. The original's hash is **withheld**, because publishing it would let anyone confirm guesses of the redacted values. Nothing else was changed.
  - **excluded**: an internal coordination memo, a superseded requirements draft, and two raw SQLite ledgers that contained machine details. Their experiment results remain as redacted JSON.
  - **replaced**: `README.md`, rewritten for outside readers.
- **Added for publication:** `LICENSE`, `SECURITY.md` and this file.

**Expected limits of redaction:** redacted experiment JSON no longer matches byte-for-byte what the original run produced, but the signals, rules and counts are unchanged. To regenerate equivalent results on your own machine, run `v0.2/experiment_first_success.py`.
