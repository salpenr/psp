# Security

## What PSP does and doesn't protect

**PSP gives tamper-*evidence*, not tamper-*proofing*:**
- The hash chain detects edits *inside* the ledger.
- It does not stop anyone with filesystem access from deleting or replacing the whole file. If agents can write to the ledger file directly, they can destroy it.

**For adversarial settings:**
- Keep the ledger where the agents can append but not rewrite or delete it: a separate account, process or host.
- Copy the chain head (from `verify`) somewhere the agents can't reach, at regular intervals.

**Other limits:**
- **Actor labels are self-declared strings, not authenticated identities.**
- **Liveness probes are host-local.** When agents act through short-lived CLI processes, liveness is `PROBE_UNAVAILABLE`.
- **`verify` opens the database through PSP's constructor, which can rewrite SQLite header bytes.** Pin evidence hashes *after* verification, or verify a copy.

## Reporting a vulnerability

Please report suspected vulnerabilities privately to **security@bastioncounsel.com** rather than opening a public issue. Include steps to reproduce and the commit you tested.
