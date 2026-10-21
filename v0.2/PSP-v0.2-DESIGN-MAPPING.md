# PSP v0.2 — DESIGN MAPPING (revision 1, for attack)

**Date:** 2026-09-15. **Author:** Claude (design lane, per Ruben's order §13). **Status:** DESIGN — NOT CODE. Frozen and hashed in `FREEZE-v0.2-DESIGN.md`. Grok attacks this exact revision; GPT reconciles; Ruben authorizes implementation or not.
**Baseline:** `PSP-v0.2-REQUIREMENTS-BASELINE.md` (Draft 5 + §23 correction). **Gaps:** `KNOWN-GAPS.md` (KG-01…KG-14). Section numbers below refer to the baseline unless marked *order* (Ruben's design order).
**Design rule (order §6):** every mechanism points upward to a frozen requirement or a known gap and names the new failure it introduces. No mechanism without a reason. No filesystem watcher (order §12). No auto-expiry (order §10). No authentication (baseline §9 boundary). No second runtime. No YELLOW.

---

## 0. Shape in one paragraph

PSP v0.2 is the v0.1 program grown into the baseline: one Python module plus tests, stdlib only, one SQLite file holding one append-only hash-chained event log, claims and evaluations derived as views. What v0.1 lacked and v0.2 adds is exactly what the baseline requires and nothing more: a PSP-minted working-instance token instead of an actor string; artifact identity from resolved path plus file identity instead of the target string; revision bound by content hash at claim time; operation class as a proposition with intent and observation as separate evidence; a lifecycle whose LIVE state has three defeaters (own RELEASE, operator release, instance process gone) instead of one; discovery that enumerates every claim in the store before asking identity questions; an evaluation record with the full §30 basis; and a three-state signal with mandatory annotations. Estimated size: 900–1200 lines of module, 600–800 of tests. Reused unchanged in concept from v0.1: append-only triggers, hash chain and `verify`, claims-as-view, CLI shape, `--db` store selection, on-Windows behaviors already tested.

---

## 1. Mechanism inventory

Each mechanism: **Requirement** (what it exists to satisfy) → **Mechanism** → **Evidence produced** (and its baseline evidence class, §10 of the baseline: participant assertion / protocol observation / derived relationship / independent observation / historical record) → **Falsifier** (what shows the evidence is wrong) → **New failure mode** (what this mechanism makes possible that was not possible before) → **Test**.

### M-01 — Store, discovery domain, claim domain

| | |
|---|---|
| Requirement | §2 claim domain; §3 discovery contract; §4 anti-gerrymandering; §6 no omission; §30 basis; KG-09 store scope; order §4 "shared PSP state" |
| Mechanism | One SQLite file (`--db`, default `%LOCALAPPDATA%\psp\psp-v0.2.db`). Every evaluation's discovery domain is **all claims in this store, every state, every project label, every target string**. No filter by any representation happens before identity evaluation (§4). The claim domain string written into every basis is `store=<absolute db path>; operation=<claim id>; scope=all participating claims at T=<evaluation time>`. |
| Evidence produced | Enumeration of the store at T (protocol observation / historical record). Coverage proposition for CLEAR (§25.2 item 2) is TRUE by construction of the enumeration; the basis lists the count and ids enumerated. |
| Falsifier | A second store on the same machine (KG-09): a CLEAR from store A says nothing about store B, and the basis must say `store=A`. A claim inserted after T is outside this evaluation by definition (§2). |
| New failure mode | O(N) identity evaluations per query (N = live claims; trivial at experimental scale). Store-path aliasing (a junction to the db) is the same store; harmless. Two workers pointing at different `--db` by mistake are two worlds; visible only if someone reads the basis. |
| Test | T-M01-a: two stores, same file, each CLEAR names its store. T-M01-b: project labels differ, same artifact ⇒ candidates still compared (B16). T-M01-c: basis lists every enumerated claim id. |

### M-02 — Working instance = PSP-minted token

| | |
|---|---|
| Requirement | §9.1 self-state; §14 working-instance identity; §16 `working instance → performs → operation`, `claim → working instance`; B10, B20; KG-01, KG-06, KG-14; order §7 "IDENTIFY WORKING INSTANCE" |
| Mechanism | At `claim`, PSP mints `instance_id` (128-bit random, hex) and records with it: `actor` (free label, self-declared), `host`, `pid`, `claim_time`. The token is returned to the caller and must be presented (`--instance` or `PSP_INSTANCE` env) on every later self-state action for that claim (`ready`, `release`, `note`). **Distinctness of two claims' instances = tokens differ.** **Continuity = the token is presented.** Actor label is never used for identity; it is display only. |
| Evidence produced | Token minted and bound by PSP at claim time (protocol observation). Presentation of the token later (protocol observation of possession). Actor label (participant assertion, display only). |
| Falsifier | The same token presented from two different `pid`s or hosts ⇒ `TOKEN_SHARED` annotation, instance distinctness for the affected claims UNRESOLVED (⇒ UNKNOWN where it matters, B10). A worker that lost its token cannot act on its claim (KG-01) ⇒ continuity UNRESOLVED; only M-07's operator route closes the claim. |
| New failure mode | Token leakage or deliberate sharing (laundering one instance into two claims, or two workers into one). Two windows of one human are two instances and will CONFLICT with each other on WRITE/WRITE; accepted and documented (they can clobber each other). Nothing here is authentication: a token proves possession, not who. |
| Test | T-M02-a: two claims `--as claude` from two processes ⇒ two tokens ⇒ distinct ⇒ B4 CONFLICT (v0.1 case 1b/C2 fixed). T-M02-b: same token from two pids ⇒ TOKEN_SHARED ⇒ UNKNOWN. T-M02-c: release without token ⇒ refused as self-state; recorded as attempt. T-M02-d: restart with token kept ⇒ release accepted (KG-01). |

### M-03 — Artifact identity = resolved canonical path + file identity

| | |
|---|---|
| Requirement | §11 SAME/DISTINCT with acceptance and rejection rules; §12 representation rule; §13 identity regression family; B8, B9, B17, B18, B19, B20; KG-12, KG-13 |
| Mechanism | For a reference `r` under root `R`: `resolved = normcase(realpath(join(R, r)))` (realpath resolves `.`, `..`, junctions, symlinks; normcase folds case on Windows). If the file exists: `fileid = (st_dev, st_ino)` from `os.stat` (on Windows this is the volume serial and NTFS file index). **SAME acceptance:** both exist and `fileid` equal; or neither exists and `resolved` equal (evidence class marked `path-only`, KG-12). **SAME rejection:** both exist and `fileid` differ. **DISTINCT acceptance:** both exist and `fileid` differ; or neither exists and `resolved` differ (`path-only`). **DISTINCT rejection:** `fileid` equal. **UNRESOLVED:** exactly one exists; `stat` fails; `st_ino == 0` (filesystem does not supply file identity); realpath fails. Target strings are stored for display and never compared for identity (§12). ARTIFACT_MOVED annotation when `fileid` matches a claim but `resolved` differs from the claim-time resolved path (KG-13). |
| Evidence produced | Resolved path and file identity computed by PSP at claim time and again at evaluation time (protocol observation). The two claims' references never establish anything by themselves (§9.2, §10, B17, B18). |
| Falsifier | Hard links: two paths, one `fileid` ⇒ SAME. That is the correct answer for coordination (one file), recorded as a design position. `st_ino == 0` on network or FAT volumes ⇒ UNRESOLVED honestly. Case folding on a case-sensitive volume (rare on Windows, possible with per-directory case sensitivity) ⇒ two files judged SAME by path when they do not exist yet (`path-only`); once both exist, `fileid` differs and DISTINCT wins. |
| New failure mode | Realpath and stat are filesystem calls at evaluation time: a file deleted between claim and evaluation goes from SAME to UNRESOLVED. Pre-creation identity (KG-12) rests on path. A reference to a path outside the workspace resolves anywhere on the machine; the design does not confine references (PSP observes, it does not permit). |
| Test | The §13 family, each as its own test with the environment capability table: `./`, `foo/../`, absolute vs relative, `MAP.md`/`map.md` (NTFS folds ⇒ SAME), junction (`mklink /J`, ⇒ SAME by fileid), hard link (`mklink /H` ⇒ SAME), symlink (needs privilege; documented as instantiable-or-not on the test box), same string under two roots with two files (⇒ DISTINCT, no false CONFLICT, B19), same basename different dirs (⇒ DISTINCT), one missing (⇒ UNRESOLVED ⇒ B8 UNKNOWN), two nonexistent aliases (⇒ SAME `path-only`, KG-12). |

### M-04 — Revision binding by content hash

| | |
|---|---|
| Requirement | §16 `operation → binds-to → revision`, `REVIEW → reviews → revision`; §20 temporal basis; §22 conditional rows; §23 (corrected); §26 superseded review; B5, B6, B7, B24; KG-03, KG-07 |
| Mechanism | At `claim`, PSP hashes the artifact (`sha256`, or `null` if it does not exist) and binds the claim to that revision. A REVIEW is bound to it as "the reviewed state." A WRITE's base is it; `ready` records the produced revision by hashing again. At evaluation PSP hashes again: **current observed revision**. **Transition established** A→B = a READY row exists from a claim bound to the same artifact whose produced revision is B (historical protocol record). **Unattributed change** = current revision differs from the last established revision and no READY explains it ⇒ `UNATTRIBUTED_CHANGE` annotation; never attributed to any worker (order §12, KG-07). |
| Evidence produced | Claim-time hash, READY hash, evaluation-time hash (protocol observation). Transition chain (derived relationship over READY records). |
| Falsifier | A WRITE in progress produces intermediate hashes: an evaluation during a live write sees a revision that no READY explains. The design records it as `CHANGE_DURING_LIVE_WRITE(<claim>)`, an inference (derived), not an attribution; if the write later READYs to that hash the inference is confirmed, otherwise it stays an inference. Hash of a large file at every evaluation is I/O; acceptable at scale. |
| New failure mode | Two artifacts with identical bytes have identical revisions; revision equality is never used as artifact identity (M-03 does that), so no confusion in the rule, but a reader of the basis could conflate them. A `null` revision (pre-creation) means "reviewed state" is undefined; a REVIEW on a nonexistent file is UNRESOLVED on revision ⇒ B7. |
| Test | T-M04-a: reviewer at A, writer READY to B ⇒ transition established; writer released ⇒ B24 CLEAR + SUPERSEDED_REVIEW. T-M04-b: hand edit, no READY ⇒ UNATTRIBUTED_CHANGE, reviewer CLEAR, no attribution (KG-07). T-M04-c: evaluate mid-write ⇒ CHANGE_DURING_LIVE_WRITE inference, later confirmed by READY. |

### M-05 — Operation class as a proposition: intent then observation

| | |
|---|---|
| Requirement | §15 class is a proposition; §9.1 intent is admissible self-state; B11, B12; KG-02, KG-03, KG-08; order §7 "DECLARE OPERATION" |
| Mechanism | `claim --op READ|WRITE|REVIEW` records **declared class** (participant assertion, self-state, admissible provisionally). **Observed class:** a `ready` from the claim's own instance with a changed hash establishes WRITE regardless of declaration (B12); the re-classification is a new event, earlier evaluations keep their basis (§2, KG-08). A declared READ or REVIEW with no READY keeps its declared class; a mutation with no READY is M-04's unattributed change, not a re-classification (KG-03). Basis field `class_evidence: declared | observed`. |
| Evidence produced | Declared class (assertion). Observed WRITE (protocol observation of the instance's own READY). |
| Falsifier | A participant that writes under READ and never calls `ready` is never re-classified; the only trace is UNATTRIBUTED_CHANGE while its claim is LIVE (KG-03). The metric for the experiment is how often that happens. |
| New failure mode | Under-classification of writes (declared READ, writes silently). Over-trust of intent between claim and first observation (KG-02). |
| Test | T-M05-a: declared READ, READY with new hash ⇒ class WRITE, re-class event appended, prior CLEAR evaluation unchanged (B12, KG-08). T-M05-b: declared READ, hand mutation, no READY ⇒ class unchanged, UNATTRIBUTED_CHANGE present. T-M05-c: class missing (`--op` absent) ⇒ refused at claim, never UNRESOLVED downstream (B11 reachable only via a malformed record, tested by direct insert). |

### M-06 — Discovery contract table (supporting and defeating evidence per proposition)

| | |
|---|---|
| Requirement | §3 items 3–4; §5 discovery falsifiability; §17 lifecycle discovery; §19; B13; order §10 |
| Mechanism | A fixed table shipped with the module and printed in every basis: for each proposition the evidence classes that support and defeat it, and where each lives. LIVE: support = CLAIMED (own token); defeat = RELEASED (own token) ∨ OPERATOR_RELEASE ∨ instance-process-gone (M-08). SAME/DISTINCT: support/defeat = M-03 observations. Class: support = declared or observed; defeat = observed WRITE over declared READ. Revision: support = hashes; defeat = differing current hash. Instance distinctness: support = distinct tokens; defeat = TOKEN_SHARED. All of these are in the one store table plus two host probes (stat, process existence), so no discovery rule can admit a supporter while structurally excluding its defeater (§5, B13). |
| Evidence produced | The table itself (design constant) and, per evaluation, which classes were consulted (protocol record). |
| Falsifier | A future event kind added to the store without a row in this table would be undiscoverable by evaluations; the test suite asserts every event kind the module can write has a table entry. |
| New failure mode | The table is code; a wrong row is a silent gerrymander. Mitigation is only the test above and the attack lane. |
| Test | T-M06-a: enumerate event kinds ⊆ table. T-M06-b: CLAIMED admitted, RELEASED present ⇒ INACTIVE (B14); a contrived evaluation that reads CLAIMED only is impossible by construction (single query), asserted by test. |

### M-07 — Lifecycle: LIVE / INACTIVE / UNRESOLVED with three defeaters

| | |
|---|---|
| Requirement | §17, §18, §19, §20; B13, B14, B22; KG-04, KG-05; order §10; v0.1 bugs E/F (READY/event after RELEASE) |
| Mechanism | **LIVE acceptance:** accepted CLAIMED (token minted), no RELEASED by that token, no OPERATOR_RELEASE for that claim, and M-08 probe returns alive or unavailable. **LIVE rejection:** RELEASED by own token, or OPERATOR_RELEASE. **INACTIVE acceptance:** the same two. **INACTIVE rejection:** none of them present. **UNRESOLVED:** M-08 probe returns "process gone" with no release (KG-05) or TOKEN_SHARED. **OPERATOR_RELEASE** is a distinct event kind, allowed only with `--as-operator <name>` and recorded with evidence class `operator` (non-participant), never as the claimant's own release (KG-04). A participant's `release` on another's claim is recorded as an `ATTEMPTED_RELEASE_OTHER` event and establishes nothing. `ready`, `note`, `break` on an INACTIVE claim are refused and recorded as attempts (B22; v0.1 E/F). No auto-expiry; ages are shown. |
| Evidence produced | Lifecycle events (historical record) and probe results (protocol observation, one host). |
| Falsifier | KG-05's falsifying experiment: kill a worker; expect UNKNOWN (not CONFLICT) at the next evaluation; expect OPERATOR_RELEASE to close it. Pid reuse (M-08) makes a dead claim look alive ⇒ CONFLICT persists; that is the recorded failure mode. |
| New failure mode | OPERATOR_RELEASE is a human assertion with a label; the design trusts the `--as-operator` flag as a declaration of role, not an authentication (visible in basis as `operator`). Anyone at the keyboard can use it. |
| Test | T-M07-a: release by own token ⇒ INACTIVE. T-M07-b: release by other participant ⇒ still LIVE, attempt recorded. T-M07-c: operator release ⇒ INACTIVE, evidence class operator. T-M07-d: READY on released claim ⇒ refused, no SUPERSEDED written (v0.1 E). T-M07-e: BREAK_FOUND after release ⇒ refused (v0.1 F). |

### M-08 — Instance-process liveness probe (one machine)

| | |
|---|---|
| Requirement | order §10 ("if PSP cannot establish whether a worker remains LIVE ⇒ UNKNOWN where that changes the answer"); §19 no unfalsifiable LIVE; KG-05 |
| Mechanism | Each claim records `host` and `pid` at mint time. At evaluation, for each LIVE candidate on the same host, PSP queries process existence for that pid (Win32 process-existence query that sends no signal; on other hosts the probe is `unavailable`). **Gone ⇒ LIVE UNRESOLVED** with annotation `INSTANCE_PROCESS_GONE` and age; **alive ⇒ no change**; **unavailable (other host) ⇒ no change** with annotation `PROBE_UNAVAILABLE`. The probe never terminates anything and never auto-releases. |
| Evidence produced | Process existence at T (protocol observation, host-local). |
| Falsifier | Pid reuse: a new unrelated process holding the old pid makes a dead claim look alive; a test creates that condition deliberately and records the false "alive". Process start time would close it and is deferred as a design question (stdlib has no portable start-time; deliberately not adding a dependency in revision 1). |
| New failure mode | Alive ≠ working: a hung worker keeps its claim LIVE. A worker whose claiming process legitimately exited while its work continues elsewhere (e.g., claimed from a shell that closed) is judged gone. Both are honest failures of a cheap probe and the experiment will count them. |
| Test | T-M08-a: kill claimant ⇒ UNKNOWN with INSTANCE_PROCESS_GONE. T-M08-b: pid reuse ⇒ recorded false-alive. T-M08-c: claim from another host (simulated `host` field) ⇒ PROBE_UNAVAILABLE, LIVE by rule. |

### M-09 — Evaluation: rows, precedence, annotations, recorded as events

| | |
|---|---|
| Requirement | §21 baseline is a protocol; §22 compatibility rows; §23 corrected; §24 profile by definition; §25 precedence; §26, §27 annotations; §2 cross-evaluation; B1–B9, B21, B23, B24, B25; order §8 duplicated-work distinctions |
| Mechanism | `evaluate <claim>` runs the pipeline: M-01 enumeration → for each other LIVE-or-UNRESOLVED claim: M-03 identity, M-02 distinctness, M-05 classes, M-04 revisions, M-07 lifecycle → §22 row lookup with §23 as corrected → §25 precedence: CONFLICT if any row TRUE; else UNKNOWN if any proposition that could flip to CONFLICT is UNRESOLVED; else CLEAR with all ten §25.2 conditions listed as satisfied. Governing profile is the baseline by definition (§24); no runtime profile selection exists in revision 1. Annotations (never a fourth state): `SUPERSEDED_REVIEW` (§26), `HISTORICAL_CONFLICT` (B23), `UNATTRIBUTED_CHANGE`, `CHANGE_DURING_LIVE_WRITE`, `INSTANCE_PROCESS_GONE`, `PROBE_UNAVAILABLE`, `TOKEN_SHARED`, `ARTIFACT_MOVED`, `INTENDED_OVERLAP` (M-11). Every evaluation is appended to the log as an `EVALUATED` event with its id, time, claim domain, and full basis, so a later narrower evaluation cannot erase an earlier one (§2, B25). |
| Evidence produced | The evaluation record (historical protocol record) with every proposition's state and evidence class. |
| Falsifier | B1–B26 as executable tests; the wrong-result list (§29) as negative tests. |
| New failure mode | The log now contains evaluations, not only claims; `history` grows faster. An implementer error in the row table is a silent semantic bug; the conformance suite is the only guard. |
| Test | One test per B-row (§4 below). Precedence tests: CONFLICT with unrelated UNRESOLVED (B21); UNKNOWN never emitted when a row is TRUE. |

### M-10 — Basis and presentation; transport neutrality

| | |
|---|---|
| Requirement | §30 required basis; order §9; §1 non-authority; Draft-2/4 transport findings; KG-11 |
| Mechanism | Every command that produces a signal writes the full §30 basis as JSON (fields: evaluation id, time, claim domain, discovery domain and rule, supporting and defeating classes consulted, observations admitted and rejected with reason, lineage of each decisive item, identity propositions with evidence class, instance propositions, class with `class_evidence`, bindings, lifecycle with evidence, profile = baseline, row fired, unresolved list, annotations, signal). The CLI prints one summary line (color, row, other live work by id, unresolved, annotations) followed by the JSON path or the JSON itself with `--json`. **Exit code is 0 for every computed signal.** `--enforce-exit` is an opt-in, labeled enforcement flag (exit 2 on CONFLICT, 3 on UNKNOWN) off by default; when used, the basis records `enforcement: exit-code`. |
| Evidence produced | The basis document itself. |
| Falsifier | KG-11's experiment: which fields did Ruben read. |
| New failure mode | Consumers that read only the summary line; the summary must contain nothing that is not in the JSON, asserted by test. |
| Test | T-M10-a: every §30 field present in every basis. T-M10-b: exit 0 on CONFLICT by default; 2 only with the flag; basis shows enforcement flag state. |

### M-11 — Intended-overlap relation tag (order §8)

| | |
|---|---|
| Requirement | order §8 (accidental duplication vs independent attack / reproduction / dependent review / complementary); order §1 purpose |
| Mechanism | Optional claim fields `--relation independent-attack|independent-reproduction|dependent-review|complementary|unspecified` and `--relates-to <claim id>`. Self-state assertion of intent, recorded as such. On a NON-CONFLICT row (READ/READ, REVIEW/REVIEW, READ/REVIEW) where both claims declare a relation to each other, the evaluation adds `INTENDED_OVERLAP(<relation>)`. It never changes the color and never applies to a CONFLICT row. |
| Evidence produced | Declared relation (participant assertion). |
| Falsifier | Mislabeling; a "dependent review" declared independent. The experiment can only count declarations; lineage of the actual work is outside PSP. |
| New failure mode | A consumer reading INTENDED_OVERLAP as permission. Documented: it is a declaration. |
| Test | T-M11-a: two REVIEW claims, both `independent-attack` referencing each other ⇒ CLEAR + INTENDED_OVERLAP. T-M11-b: WRITE/WRITE with relation tags ⇒ CONFLICT, no INTENDED_OVERLAP. |

### M-12 — Metrics and operator ground truth (order §15)

| | |
|---|---|
| Requirement | order §15 resource test; order §14 first success test |
| Mechanism | `psp metrics [--since]` derives from the log: CONFLICT evaluations whose claim was later released without READY (proxy for "conflict detected before execution"), CLEAR evaluations, UNKNOWN evaluations with the unresolved proposition histogram, claims with INSTANCE_PROCESS_GONE (stale), OPERATOR_RELEASE count and `psp note --intervention` count (manual interventions), INTENDED_OVERLAP count (independent reviews preserved). `psp verdict --eval <id> --truth false-conflict|false-clear|false-unknown|true --as-operator <name>` records ground truth as an operator-class event so false rates can be computed. |
| Evidence produced | Counts derived from the log (derived relationship); verdicts (operator assertion). |
| Falsifier | Ground truth is Ruben's judgment; disagreement between Ruben's verdict and a later reproduction is itself a record. |
| New failure mode | Proxies are proxies: "released without READY after CONFLICT" may be a worker giving up for another reason. |
| Test | T-M12-a: synthetic session ⇒ expected counts. T-M12-b: verdict events appear in metrics as false-rate numerators. |

---

## 2. Requirement → mechanism table

| Baseline requirement | Mechanism(s) | Evidence produced | Falsifier | New failure mode | Test |
|---|---|---|---|---|---|
| §1 core boundary | M-10 (exit 0; enforcement opt-in and labeled) | basis `enforcement` field | a consumer script that stops on CONFLICT anyway | consumers ignoring the label | T-M10-b |
| §2 claim domain; B25 | M-01, M-09 (evaluations are events) | claim domain string; EVALUATED records | narrow eval after broad CONFLICT | log growth | T-B25 |
| §3 discovery contract | M-01, M-06 | enumeration + table | second store; missing table row | table is code | T-M01, T-M06 |
| §4 anti-gerrymandering; B16 | M-01 (no representation filter before identity) | enumeration of all claims | any prefilter | none beyond O(N) | T-M01-b |
| §5 falsifiability; B13 | M-06, M-07 | supporter and defeater in one table | contrived single-kind read | none | T-M06-b |
| §6 no omission after discovery | M-09 (every enumerated claim appears in basis as admitted or rejected with reason) | admitted/rejected lists | a claim missing from both | none | T-M01-c |
| §7 evidence lineage; §8 independence; B26 | M-02, M-03, M-04 (PSP computes; assertions recorded with class `assertion`) | every decisive item carries `evidence_class` and origin | an assertion labeled observation | mislabel in code | T-M10-a lineage check |
| §9 self-state vs relational; B17, B18 | M-02 (token = self), M-03 (identity = observation), M-05 (intent = self-state provisional) | class per proposition | `distinct_from` field honored | none: fields are recorded and ignored for relations | T-B17, T-B18 |
| §10 corroboration | M-03 (no assertion path exists) | — | two claims asserting | dormant (KG-06) | T-B18 |
| §11, §12, §13 identity; B8, B9, B19, B20 | M-03 | resolved path, file id, `path-only` marker | §13 family | hard link = SAME; `st_ino 0` | §13 suite |
| §14 working instance; B10 | M-02, M-08 | token, pid, probe | TOKEN_SHARED; restart without token | leakage; two windows = two instances | T-M02 |
| §15 operation class; B11, B12 | M-05 | declared / observed | mutation without READY | under-classification | T-M05 |
| §16 bindings | M-02, M-03, M-04 (every binding is a computed record, never inferred from endpoints) | binding rows | binding missing ⇒ UNRESOLVED | none | T-B7 |
| §17, §18, §19 lifecycle; B14, B22 | M-07, M-08 | events + probe | dead claimant; pid reuse | operator flag is a declaration | T-M07, T-M08 |
| §20 temporal basis; B15 | M-04 (hash at evaluation), M-09 (evaluation time), M-10 | times in basis; cached signals never consulted (no cache exists) | reading an old EVALUATED record as current | none: evaluations are records, not inputs | T-B15 |
| §21 baseline is a protocol | M-01…M-09 together | — | any missing part | — | whole suite |
| §22 compatibility rows; B1–B6 | M-09 | row fired | row table error | silent semantic bug | T-B1…T-B6 |
| §23 corrected revision rule; B5, B6, B7 | M-04, M-09 | reviewed revision vs current; live WRITE on same artifact ⇒ CONFLICT | reviewer bound to non-current revision (⇒ §26 path) | none | T-B5, T-B6, T-B7, T-B24 |
| §24 profile binding | M-09 (constant) | `profile: baseline` | — | none in revision 1 | T-M10-a |
| §25 precedence; B21 | M-09 | ordered checks in basis | UNKNOWN when a row is TRUE | none | T-B21 |
| §26 superseded review; B24 | M-04, M-07, M-09 | SUPERSEDED_REVIEW | reviewer ignores it (KG-10) | annotation blindness | T-B24, KG-10 experiment |
| §27 annotations | M-09 | annotation list | annotation on a CONFLICT that "softens" it | none: annotations never alter precedence | T-M09 annotation-never-changes-color |
| §28 conformance key | §4 below | — | — | — | B1–B26 |
| §29 wrong-result criterion | negative tests | — | — | — | T-WR-* |
| §30 basis | M-10 | JSON | missing field | consumers reading summary only | T-M10-a |
| §31 vocabulary | design text reviewed against the list | — | — | — | (review) |
| §32 no mechanism selected | this document | — | — | — | — |
| order §5 no simulated presence; KG-14 | M-02 (no instance without a claim; relay claims labeled `recorded_by`) | relay-assertion class | a "GPT view" | none | T-KG14 |
| order §7 minimum flow | M-02 → M-01/M-03 → M-05 → M-09 → M-10 → M-07 | — | — | — | T-FLOW |
| order §8 duplicated work | M-11 | relation tag | mislabel | permission misreading | T-M11 |
| order §10 stale state | M-08, M-07 | INSTANCE_PROCESS_GONE ⇒ UNKNOWN | pid reuse | alive ≠ working | T-M08 |
| order §12 no invisible manual writer claim; KG-07 | M-04 (UNATTRIBUTED_CHANGE, never attributed) | annotation | none | none | T-M04-b |
| order §15 resource test | M-12 | metrics + verdicts | proxies | self-reported truth | T-M12 |

---

## 3. Minimum coordination flow (order §7) as commands

```
psp claim   --project P --as <label> --op READ|WRITE|REVIEW --target <ref> --root <R> [--relation … --relates-to …]
            → mints instance token; hashes artifact; resolves identity; records CLAIMED;
              immediately runs evaluate → prints color + WHY; exit 0
psp evaluate --claim <id>                 → re-evaluates now (fresh hashes, fresh probes); records EVALUATED
psp ready    --claim <id> --instance <tok> → records READY with produced revision; re-classifies to WRITE if changed
psp note     --claim <id> --instance <tok> --text …   (REVIEWING / BREAK_FOUND collapse into notes; no lifecycle effect)
psp release  --claim <id> --instance <tok> → RELEASED (own); or --as-operator <name> → OPERATOR_RELEASE
psp status   [--project P]                 → every LIVE/UNRESOLVED claim with its last evaluation summary
psp why      --eval <id>                   → full basis
psp history / verify / metrics / verdict
```

The v0.1 events REVIEWING and BREAK_FOUND become `note` kinds with no lifecycle or signal effect; SUPERSEDED is no longer an event but an annotation computed at evaluation (§26, v0.1 finding K). The v0.1 `--hash` on events is gone (v0.1 finding B); revision is always PSP-observed.

---

## 4. Conformance test plan (baseline §28 → tests)

| Row | Test | Setup sketch |
|---|---|---|
| B1 | T-B1 | two tokens, READ/READ, same fileid ⇒ CLEAR |
| B2, B3 | T-B2, T-B3 | READ/WRITE either order ⇒ CONFLICT |
| B4 | T-B4 | WRITE/WRITE ⇒ CONFLICT (also T-M02-a from two processes) |
| B5, B6 | T-B5, T-B6 | REVIEW bound to current revision, live WRITE ⇒ CONFLICT (corrected §23) |
| B7 | T-B7 | REVIEW on nonexistent file (revision null) + WRITE ⇒ UNKNOWN(revision) |
| B8 | T-B8 | one reference resolves, other missing ⇒ UNKNOWN(identity) |
| B9 | T-B9 | two files, distinct fileid ⇒ CLEAR |
| B10 | T-B10 | TOKEN_SHARED ⇒ UNKNOWN(instance) |
| B11 | T-B11 | malformed class record inserted directly ⇒ UNKNOWN(class) |
| B12 | T-B12 | declared READ, READY with new hash ⇒ WRITE; earlier eval unchanged |
| B13 | T-B13 | asserted by construction (M-06 test) |
| B14 | T-B14 | CLAIMED then RELEASED ⇒ INACTIVE |
| B15 | T-B15 | old EVALUATED record is never an input; fresh evaluate differs after change |
| B16 | T-B16 | different project labels, same file ⇒ compared ⇒ CONFLICT (not CLEAR) |
| B17, B18 | T-B17, T-B18 | `distinct_from` fields present ⇒ ignored for identity; identity from M-03 |
| B19 | T-B19 | same basename, two dirs ⇒ DISTINCT ⇒ no CONFLICT |
| B20 | T-B20 | `MAP.md` vs `./MAP.md` (and the §13 family) ⇒ SAME ⇒ CONFLICT on WRITE/WRITE |
| B21 | T-B21 | CONFLICT + an unrelated UNRESOLVED (e.g., third claim's identity) ⇒ CONFLICT |
| B22 | T-B22 | READY on released claim refused; no live effect |
| B23 | T-B23 | past CONFLICT, both released, new READ ⇒ CLEAR + HISTORICAL_CONFLICT |
| B24 | T-B24 | §26 scenario ⇒ CLEAR + SUPERSEDED_REVIEW |
| B25 | T-B25 | broad CONFLICT then narrow CLEAR ⇒ both EVALUATED records retained |
| B26 | T-B26 | assertion copied into two claims ⇒ one lineage, zero relational weight |
| §29 list | T-WR-01…16 | one negative test per bullet |
| §13 family | T-ID-01…10 | with `ENVIRONMENT-CAPABILITIES.md` recording which cases the test box instantiates (junction yes; hard link yes; symlink privilege-dependent; case-fold yes on NTFS) |
| KG falsifiers | T-KG-01…14 | one per known gap, expected to *expose* the gap, not pass |

---

## 5. Mechanisms deliberately not chosen

| Not chosen | Why | Would be justified by |
|---|---|---|
| Filesystem watcher | order §12 forbids in requirements; polling at evaluation is enough for participating workers | an observed failure where UNATTRIBUTED_CHANGE arrived too late to matter |
| TTL / lease / auto-expiry | order §10 wants UNKNOWN, not silent expiry; KG-05 stays an experiment target | measured stale-claim burden that operator release cannot absorb |
| Authentication / signatures | §9 boundary; tokens are possession, not identity; order §5 | a demonstrated token-laundering attack that changed a real decision |
| Process start time (pid-reuse guard) | no stdlib portable source; revision 1 stays stdlib | T-M08-b showing pid reuse in practice |
| Daemon / MCP / HTTP | one machine, CLI + module suffice; a daemon is a second runtime | a participant that cannot run a CLI |
| Git as identity or revision | workspace need not be a repo; content hash is enough for revision; fileid for identity | multi-branch work in scope |
| Profile selection at runtime | §24: baseline by definition | a second deployment profile with an owner |
| YELLOW | order §11 | KG-10 measurement |
| Cross-store discovery | KG-09 | evidence that workers cannot agree on one store |

---

## 6. Visible limits (must appear in every basis)

- Discovery domain = participating claims in **this store**; non-participating writers are never observed as workers (KG-07, order §12).
- Instance = token possession, not identity (KG-01, KG-14).
- Liveness probe is host-local and pid-based (KG-05).
- Class before first observation rests on declared intent (KG-02).
- Pre-creation identity rests on path (KG-12).
- Enforcement is off unless the labeled flag is set (§1).

---

## 7. Position statements (mine, for Grok to attack)

1. Hard links and junctions to one file are **one artifact**. Two claims on them conflict. I think this is right for coordination and wrong for nothing in scope.
2. Two windows of one human are **two working instances**. They can clobber each other; PSP should say so.
3. The pid probe is cheap and imperfect, and imperfect-but-honest (UNKNOWN with an annotation) beats unfalsifiable LIVE.
4. Operator release is a role flag, not authentication. In a three-worker experiment on one machine that is the correct amount of trust; it is also the first thing to revisit if the scope grows.
5. Evaluations as log events is the single design choice that makes §2 and B25 mechanical instead of aspirational.

STOP. Design only. No code. Frozen v0.1 untouched. Baseline and known gaps untouched by this document.
