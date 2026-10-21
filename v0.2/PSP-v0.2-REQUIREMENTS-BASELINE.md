# PSP v0.2 — REQUIREMENTS BASELINE (FROZEN)

**This file is Draft 5 plus exactly one normative sentence in §23.** Nothing else was changed. Draft 6 was not created.

## Correction record

| Field | Value |
|---|---|
| Source | `<home>\psp\PSP-v0.2-REQUIREMENTS-DRAFT5-2026-09-15.md` |
| Source Draft-5 SHA-256 | `d4ca86cae7243960ad27f76e6cfeb3a93353277f9558e84d750f1a3f60b4fda1` |
| Correction | One sentence appended to §23 after "The baseline cannot choose among several revision rules per evaluation." (shown in place, marked **Owner correction**) |
| Reason | §23's phrase "the artifact state/revision relationship that the REVIEW is established as reviewing" admitted two readings; under the revision-as-fixed-object reading a conforming implementation emits CLEAR for a live writer over a live reviewer of the current revision and answer-key rows B5/B6/B7/B24 become uninterpretable. The sentence fixes reading (i) for the experimental baseline. |
| Claude blocker finding | `<home>\<private-notes>/psp-v0.2-requirements\CLAUDE-REVIEW-DRAFT5-2026-09-15.md`, finding F1 (BLOCKER), letter `<id>` |
| Authorized by | Ruben, "PSP v0.2 — OWNER AUTHORIZATION AND EXPERIMENTAL DESIGN ORDER", 2026-09-15, §2 |
| New baseline SHA-256 | recorded in `FREEZE-v0.2-DESIGN.md` beside this file (a file cannot carry its own hash) |
| Date | 2026-09-15 |
| Environment | Python 3.11.9, Windows-10-10.0.26200-SP0; produced by `make_baseline.py` (scratchpad), deterministic text edit, no other transformation |

---

# PROJECT SIGNAL PROTOCOL — PSP v0.2
## Requirements Draft 5 — Baseline Evidence Protocol
### 2026-09-15

**Status:** DRAFT — ADVERSARIAL REVIEW TARGET  
**Implementation:** NOT AUTHORIZED  
**PSP v0.1:** FROZEN / UNCHANGED  
**Drafts 1–4:** DEFEATED / PRESERVED AS EVIDENCE  
**example-project:** HOLD  
**Owner:** Ruben  
**Prepared by:** GPT / Archivist

---

# 0. Purpose

Draft 5 defines the minimum evidence protocol required before PSP may issue:

```text
🟢 CLEAR
🔴 CONFLICT
⚫ UNKNOWN
```

The protocol is:

```text
CLAIM DOMAIN
      ↓
DISCOVERY CONTRACT
      ↓
EVIDENCE LINEAGE
      ↓
ENTITY + RELATIONSHIP ESTABLISHMENT
      ↓
CURRENCY / LIFECYCLE
      ↓
GOVERNING BASELINE
      ↓
ANSWER KEY
      ↓
SIGNAL + BASIS
```

The central rule is:

> **PSP may not claim more coordination knowledge than its evidence process justifies.**

---

# 1. Core Boundary

PSP determines coordination state.

It does not determine:

- authority,
- permission,
- correctness,
- safety,
- ownership,
- priority,
- truth of an artifact,
- who must stop.

Therefore:

```text
CLAIMED ≠ AUTHORIZED
CLEAR ≠ PERMITTED
CONFLICT ≠ DENIED
UNKNOWN ≠ FORBIDDEN
```

A consumer may separately act on a PSP result.

That action is not part of PSP signal semantics.

---

# 2. Claim Domain

Every evaluation has an explicit **claim domain**.

The claim domain defines what the resulting signal claims to describe.

A CLEAR result is valid only for its stated claim domain.

A narrow CLEAR cannot be presented as a broader CLEAR.

A later narrow evaluation cannot erase an earlier broader CONFLICT.

---

# 3. Discovery Contract

Every baseline evaluation must use a declared discovery contract.

The discovery contract defines:

1. the domain PSP attempts to observe;
2. the classes of activity that may affect the answer;
3. the evidence classes capable of supporting a proposition;
4. the evidence classes capable of defeating that proposition.

For CLEAR:

```text
CLEAR CLAIM DOMAIN
        ⊆
DISCOVERY DOMAIN
```

must be established.

Otherwise:

```text
⚫ UNKNOWN
```

---

# 4. Anti-Gerrymandering Rule

A discovery boundary must not be defined solely by a representation whose equivalence, distinctness, classification, or binding is itself necessary to determine the signal.

Example:

```text
A = MAP.md
B = foo/../MAP.md
```

If determining whether A and B identify the same artifact participates in the answer key, exact target-string equality alone cannot define a discovery boundary that prevents A and B from becoming candidates for comparison.

This rule generalizes beyond paths to any representation used as a discovery boundary.

Examples include:

- target strings,
- project labels,
- actor labels,
- revision labels,
- operation labels,
- session labels,
- namespaces.

A representation cannot establish its own isolation merely by defining the boundary within which PSP looks.

---

# 5. Discovery Falsifiability

For every proposition P that can change a signal, the discovery contract must identify:

```text
SUPPORTING EVIDENCE CLASS(P)
DEFEATING EVIDENCE CLASS(P)
```

where such defeating evidence can exist.

A discovery contract is non-conforming if it can structurally observe evidence defined to establish P while excluding the evidence class defined to reject P.

Example:

```text
LIVE support:
CLAIM

LIVE defeat:
RELEASE
```

A discovery rule that admits CLAIM but structurally excludes RELEASE cannot establish LIVE for a CLEAR or CONFLICT determination.

---

# 6. No Omission After Discovery

Once an observation satisfies the discovery contract for an evaluation, it cannot be excluded merely because including it changes the result.

Evidence may be rejected only under an explicit evidence-admissibility rule.

The rejection and its basis must remain visible.

---

# 7. Evidence Lineage

Every decisive item of evidence must preserve lineage sufficient to answer:

```text
SOURCE
  ↓
OBSERVATION
  ↓
TRANSFORMATION(S)
  ↓
PROPOSITION / RELATIONSHIP
```

Recording an assertion in PSP does not change its original source.

Transforming an assertion does not automatically make it independent.

Copying an assertion does not create corroboration.

---

# 8. Evidence Independence

Independence is a property of evidence lineage, not:

- record count,
- actor-name count,
- message count,
- database-row count,
- agreement count.

Therefore:

```text
A asserts X
B repeats A's X
```

does not automatically provide two independent evidentiary sources for X.

Likewise:

```text
A asserts X
PSP records X
PSP derives Y from X
```

does not automatically turn X and Y into independent evidence.

A conforming evidence rule that requires independence must define what lineage properties establish that independence.

---

# 9. Self-State Versus Relational Propositions

Draft 5 distinguishes two categories.

## 9.1 Self-state proposition

A proposition about an activity the participant itself initiates or terminates through the protocol.

Examples:

```text
working instance A starts claim A
working instance A releases claim A
working instance A reports operation intent
```

A participant's protocol action may contribute decisive evidence for its own self-state when the baseline acceptance rule explicitly permits it.

This does not make every statement by that participant true.

## 9.2 Relational proposition

A proposition whose truth determines a relationship between entities.

Examples:

```text
SAME(A,B)
DISTINCT(A,B)

worker A distinct from worker B

operation A targets same artifact as operation B

operation A compatible with operation B

profile P governs evaluation E
```

An interested participant's bare assertion cannot by itself establish a relational proposition that changes its coordination relationship with another participant.

---

# 10. No Corroboration Laundering

Two or more interested parties agreeing on a relational proposition do not automatically establish independence.

Example:

```text
A: "A and B are distinct."
B: "Yes, A and B are distinct."
```

does not by itself establish:

```text
DISTINCT(A,B) = TRUE
```

If an acceptance rule requires independent evidence, independence must be established through lineage.

---

# 11. Artifact Identity

For artifact references A and B:

```text
SAME(A,B)
DISTINCT(A,B)
```

are separate propositions.

Each has:

```text
acceptance rule
rejection rule
evidence classes
```

Failure to establish SAME does not establish DISTINCT.

Failure to establish DISTINCT does not establish SAME.

If neither can be established and artifact identity can change the answer:

```text
⚫ UNKNOWN
```

---

# 12. Representation Rule

Textual or representational equality alone does not establish SAME when that representation can refer to distinct artifacts within the claim domain.

Textual or representational inequality alone does not establish DISTINCT when multiple representations can refer to the same artifact within the claim domain.

Therefore neither:

```text
A.text == B.text
```

nor:

```text
A.text != B.text
```

is universally sufficient identity evidence.

Concrete alias and false-collision cases belong in the conformance suite; the normative rule is general.

---

# 13. Identity Regression Family

A candidate must be attacked with at least:

```text
MAP.md
./MAP.md
foo/../MAP.md
absolute vs relative reference
case variant where underlying environment aliases case
alternate linked reference where applicable
same textual reference under established different roots/contexts
same basename on established different artifacts
```

The test environment must document which cases it can instantiate.

Expected semantic behavior is determined by established SAME/DISTINCT evidence, not by the spelling of the reference.

Unsupported identity determination that can change the answer produces:

```text
⚫ UNKNOWN
```

not fabricated CLEAR or CONFLICT.

---

# 14. Working-Instance Identity

Actor label is not working-instance identity.

A working-instance relation used in a conflict determination must have its own evidence rule.

A process restart does not automatically prove:

```text
same working instance
```

or:

```text
different working instance
```

If continuity matters to the answer and cannot be established:

```text
⚫ UNKNOWN
```

---

# 15. Operation Class Is a Proposition

Operation class is not trusted merely because a participant labels it.

The baseline operation classes are:

```text
READ
WRITE
REVIEW
```

Each class must have an evidence rule defining what establishes the classification used by the answer key.

A participant may declare intent.

Intent is not automatically equivalent to observed operation class.

Therefore:

```text
actual WRITE
declared READ
```

must not become READ solely because the participant supplied that label.

---

# 16. Operation Bindings

A baseline determination may require:

```text
working instance → performs → operation

operation → targets → artifact

operation → binds-to → revision

REVIEW → reviews → revision
```

Endpoint existence does not establish the relationship.

Example:

```text
WRITE exists
artifact X exists
revision B exists
```

does not establish:

```text
WRITE targets X at B
```

without binding evidence.

---

# 17. Currency and Lifecycle

The baseline lifecycle has:

```text
LIVE
INACTIVE
UNRESOLVED
```

A self-state protocol event may contribute evidence to lifecycle state.

The baseline must define both:

```text
LIVE acceptance/rejection
INACTIVE acceptance/rejection
```

and discovery must include evidence classes capable of supporting and defeating those states.

---

# 18. Baseline Lifecycle Rule

For baseline conformance:

```text
accepted CLAIM/START evidence
```

may establish the beginning of a LIVE interval for that working instance/claim relationship.

```text
accepted RELEASE evidence
```

terminates that LIVE interval for subsequent baseline coordination determinations unless a later accepted event establishes a new LIVE relationship.

RELEASE is not merely absence of CLAIM.

It is defeating lifecycle evidence.

An INACTIVE claim cannot create a new LIVE coordination consequence.

Historical information remains preserved.

---

# 19. No Unfalsifiable LIVE Rule

The following rule is insufficient by itself:

```text
no RELEASE observed → LIVE forever
```

unless the discovery contract establishes that evidence capable of defeating LIVE was within the evaluation's required discovery domain.

A lifecycle rule cannot obtain permanent LIVE by making its own falsifier undiscoverable.

---

# 20. Temporal Basis

Every signal identifies:

```text
observation time
evaluation time
lifecycle evidence used
```

Reading an old record now does not make its state newly current.

A cached signal is not present-state evidence merely because it was returned now.

---

# 21. Governing Baseline

Draft 5 defines one baseline coordination protocol.

A different named deployment profile may exist.

It cannot silently replace the Draft-5 baseline during baseline conformance testing.

The baseline includes:

- discovery obligations,
- evidence-lineage obligations,
- artifact-identity obligations,
- working-instance obligations,
- operation-class obligations,
- operation/revision bindings,
- lifecycle obligations,
- compatibility rules,
- answer-key precedence.

Thus the baseline is a protocol, not merely a compatibility table.

---

# 22. Baseline Compatibility

For:

```text
same established artifact
distinct established LIVE working instances
required bindings established
required lifecycle state established
```

the baseline relationships are:

| Operation A | Operation B | Result |
|---|---|---|
| READ | READ | NON-CONFLICT |
| READ | REVIEW | NON-CONFLICT |
| REVIEW | READ | NON-CONFLICT |
| REVIEW | REVIEW | NON-CONFLICT when review bindings do not establish incompatible target state |
| READ | WRITE | CONFLICT |
| WRITE | READ | CONFLICT |
| REVIEW | WRITE | CONFLICT when WRITE can alter the artifact/revision relationship being reviewed |
| WRITE | REVIEW | CONFLICT when WRITE can alter the artifact/revision relationship being reviewed |
| WRITE | WRITE | CONFLICT |

Where a required revision/binding proposition for a conditional row is UNRESOLVED:

```text
⚫ UNKNOWN
```

---

# 23. One Baseline Revision Rule

The Draft-5 baseline uses this rule:

> **A LIVE WRITE conflicts with a LIVE REVIEW when the WRITE can alter the artifact state/revision relationship that the REVIEW is established as reviewing.**

Therefore:

```text
REVIEW → revision A
WRITE → can alter reviewed A relationship
```

yields:

```text
🔴 CONFLICT
```

If the WRITE is established not to affect the review's bound artifact/revision relationship:

```text
NON-CONFLICT
```

If that relationship cannot be established:

```text
⚫ UNKNOWN
```

The baseline cannot choose among several revision rules per evaluation.

**Owner correction (2026-09-15, Ruben; from Claude Draft-5 finding F1, BLOCKER). Normative:**

> **For the Draft-5 experimental baseline, when a LIVE REVIEW is bound to revision A as the current reviewed state of artifact X, any distinct LIVE WRITE targeting artifact X is considered capable of altering that reviewed state relationship and therefore conflicts while both operations remain LIVE.**

---

# 24. Profile Binding

For non-baseline deployments, provenance of a profile and binding of that profile to an evaluation remain separate propositions.

Two legitimate profiles do not allow the implementation to select whichever produces a desired result.

During Draft-5 baseline conformance testing:

```text
governing profile = Draft-5 baseline
```

by definition of the test.

No runtime profile-selection mechanism is specified here.

---

# 25. Answer-Key Precedence

## 25.1 CONFLICT

Emit:

```text
🔴 CONFLICT
```

when all propositions required by a baseline conflict row are established TRUE.

Uncertainty that does not participate in that conflict row cannot downgrade CONFLICT.

## 25.2 CLEAR

Emit:

```text
🟢 CLEAR
```

only when:

1. the claim domain is explicit;
2. required discovery coverage is established;
3. discovery falsifiability requirements are satisfied;
4. decisive evidence passes admissibility/lineage requirements;
5. required identities are established;
6. required operation classes are established;
7. required bindings are established;
8. required lifecycle/currency propositions are established;
9. no baseline conflict row is TRUE;
10. no proposition capable of changing CLEAR to CONFLICT is UNRESOLVED.

## 25.3 UNKNOWN

Emit:

```text
⚫ UNKNOWN
```

when CONFLICT is not already established and a proposition necessary to distinguish remaining outcomes is UNRESOLVED.

UNKNOWN identifies the unresolved proposition.

---

# 26. Superseded Review Test

Draft 5 deliberately includes the case that challenged the three-state kernel.

Scenario:

```text
reviewer = LIVE
review explicitly bound to revision A

writer = INACTIVE

artifact state = revision B

A → B transition = established

no LIVE WRITE remains

review target A is established as superseded
```

Draft 5 does **not** pre-label this CONFLICT merely because the artifact changed.

The reviewer is not in a LIVE concurrency conflict with the inactive writer.

The baseline asks instead:

```text
Does CLEAR mean:
"No active coordination conflict"

or:

"Work remains validly bound to its intended coordination target"?
```

For Draft-5 adversarial review, this case has provisional result:

```text
🟢 CLEAR
with mandatory semantic annotation:
SUPERSEDED_REVIEW
```

The annotation is not a fourth signal.

Reviewers must attack this choice.

If a serious wrong-result case proves that CLEAR + annotation cannot faithfully represent the state, the three-state kernel is reopened.

No YELLOW is restored merely for visual symmetry.

---

# 27. Semantic Annotations

Annotations may describe established conditions that do not change the core answer key.

Examples may include:

```text
HISTORICAL_CONFLICT
SUPERSEDED_REVIEW
PRIOR_REVISION
```

An annotation cannot hide:

```text
🔴 CONFLICT
```

or replace:

```text
⚫ UNKNOWN
```

when the core answer key requires either.

An annotation is descriptive evidence attached to a semantic result.

It is not a policy instruction.

---

# 28. Conformance Answer Key

| ID | Scenario | Expected |
|---|---|---|
| B1 | Same artifact, distinct LIVE READ/READ | 🟢 CLEAR |
| B2 | Same artifact, distinct LIVE READ/WRITE | 🔴 CONFLICT |
| B3 | Same artifact, distinct LIVE WRITE/READ | 🔴 CONFLICT |
| B4 | Same artifact, distinct LIVE WRITE/WRITE | 🔴 CONFLICT |
| B5 | Same artifact, LIVE REVIEW/WRITE affecting reviewed relationship | 🔴 CONFLICT |
| B6 | Same artifact, LIVE WRITE/REVIEW affecting reviewed relationship | 🔴 CONFLICT |
| B7 | REVIEW/WRITE revision relationship unresolved | ⚫ UNKNOWN |
| B8 | SAME/DISTINCT required but unresolved | ⚫ UNKNOWN |
| B9 | DISTINCT positively established, all other CLEAR requirements true | 🟢 CLEAR |
| B10 | Working-instance continuity required but unresolved | ⚫ UNKNOWN |
| B11 | Operation class required but unresolved | ⚫ UNKNOWN |
| B12 | Declared READ but evidence establishes WRITE | classify using established WRITE |
| B13 | Discovery can see CLAIM but structurally excludes RELEASE | ⚫ UNKNOWN for LIVE-dependent determination |
| B14 | CLAIM then discovered RELEASE | subsequent state INACTIVE |
| B15 | Cached GREEN without present evaluation evidence | ⚫ UNKNOWN if present state required |
| B16 | Broad CLEAR domain but discovery is gerrymandered by unresolved target representation | ⚫ UNKNOWN |
| B17 | Participant declares DISTINCT without admissible relational evidence | ⚫ UNKNOWN if identity affects result |
| B18 | Two interested parties mutually assert DISTINCT without established independence | ⚫ UNKNOWN if identity affects result |
| B19 | Basename equality alone on established different artifacts | must not create false CONFLICT |
| B20 | Representation inequality alone where aliases may exist | must not create false CLEAR |
| B21 | Established CONFLICT + unrelated authentication uncertainty | 🔴 CONFLICT |
| B22 | Inactive claim attempts new LIVE effect | invalid live consequence |
| B23 | Historical conflict inactive + present CLEAR predicates established | 🟢 CLEAR + history preserved |
| B24 | Superseded-review scenario §26 | 🟢 CLEAR + SUPERSEDED_REVIEW |
| B25 | Narrow CLEAR following broader RED | both retained with different claim domains |
| B26 | Evidence copied through PSP from one source | copy does not create independence |

---

# 29. Wrong-Result Criterion

Draft 5 is defeated if a conforming candidate can obey the written rules and still:

- produce dual broad CLEAR by gerrymandering discovery;
- manufacture SAME or DISTINCT from representation alone;
- manufacture independence from multiple dependent records;
- turn participant assertions into independent protocol evidence merely by recording them;
- hide RELEASE through its discovery contract;
- keep a dead claim LIVE indefinitely through an unfalsifiable rule;
- classify WRITE as READ solely from participant labeling;
- omit REVIEW from baseline operation handling;
- discard required revision binding;
- choose a favorable governing profile during baseline testing;
- produce false CONFLICT from coarse identity;
- produce false CLEAR from aliasing;
- use UNKNOWN to erase established CONFLICT;
- present a narrow CLEAR as answering a broader conflict question;
- use an annotation to conceal CONFLICT or UNKNOWN;
- satisfy the baseline table while violating the baseline evidence protocol.

---

# 30. Required Signal Basis

Every determination must expose or reference:

```text
evaluation identifier
evaluation time
claim domain
discovery domain
discovery rule
supporting evidence classes
defeating evidence classes
observations admitted
observations rejected and why
source lineage for decisive evidence
independence relationship where used
artifact identity propositions
working-instance propositions
operation classification
operation/artifact/revision bindings
lifecycle state and evidence
governing baseline/profile
answer-key row
unresolved propositions
annotations
signal
```

Storage format is a design decision.

---

# 31. Normative Language

A normative rule must not depend on an undefined qualifier such as:

```text
known
relevant
material
appropriate
reasonable
supported
sufficient
unexpected
unexplained
```

If such ordinary wording appears in explanatory prose, it adds no protocol condition.

A normative decision must reduce to:

- a defined proposition,
- an evidence rule,
- a relationship,
- a discovery obligation,
- a lifecycle rule,
- a baseline answer-key row,
- or an explicitly identified unresolved proposition.

---

# 32. No Mechanism Selected

Draft 5 defines required evidence properties.

It does not choose how they are implemented.

A future design may propose concrete mechanisms.

Each proposed mechanism must answer:

```text
Which Draft-5 requirement does this satisfy?

What evidence does it produce?

What can falsify that evidence?

What new failure mode does the mechanism introduce?
```

Mechanisms are subordinate to requirements.

Requirements are not rewritten merely to make a preferred mechanism pass.

---

# 33. Claude Attack Assignment

Attack Draft 5 verbatim.

Do not repair it.

Concentrate on:

1. baseline discovery completeness;
2. anti-gerrymandering;
3. falsifiability of discovery;
4. evidence lineage;
5. independence;
6. self-state versus relational evidence;
7. identity;
8. working-instance continuity;
9. operation classification;
10. currency/lifecycle;
11. REVIEW/WRITE revision rule;
12. superseded-review CLEAR + annotation.

Try to produce a wrong answer while obeying every written rule.

Return:

```text
REQUIREMENT
→ ATTACK
→ EVIDENCE LINEAGE
→ REQUIREMENTS OBEYED
→ PRODUCED RESULT
→ EXPECTED REAL-WORLD RESULT
→ WHY THEY DIFFER
→ CLASSIFICATION
```

Also list serious attacks blocked by a specific written rule.

STOP.

No design.

No mechanism.

No code.

---

# 34. Grok Attack Assignment

Attack Draft 5 independently.

Do not repair it.

Try:

```text
discovery gerrymandering
falsifier exclusion
source laundering
independence laundering
sockpuppet corroboration
self-state laundering
identity laundering
operation laundering
revision laundering
currency laundering
restart laundering
profile laundering
annotation laundering
false CLEAR
false CONFLICT
false UNKNOWN
```

For each surviving attack:

```text
SCENARIO
→ CLAIM DOMAIN
→ DISCOVERY CONTRACT
→ SOURCE LINEAGE
→ PROPOSITIONS
→ BINDINGS
→ LIFECYCLE
→ BASELINE ROW
→ PRODUCED SIGNAL
→ CORRECT SIGNAL
→ WHY DRAFT 5 ALLOWS THE ERROR
```

Also list attacks that fail because Draft 5 explicitly blocks them.

STOP.

No implementation.

No repair.

---

# 35. Exit Criterion

Draft 5 becomes a candidate for design only if independent adversarial review fails to construct a serious wrong-signal counterexample without violating a written requirement.

In particular:

1. discovery cannot define away competing work;
2. supporting and defeating evidence remain discoverable under the same claim;
3. evidence retains source lineage;
4. copying does not manufacture independence;
5. self-state evidence is distinguished from relational evidence;
6. participants cannot manufacture two-party relationships;
7. representation spelling cannot manufacture artifact identity;
8. operation labels cannot manufacture operation class;
9. lifecycle is falsifiable;
10. dead claims cannot remain live by construction;
11. REVIEW participates in the baseline;
12. revision bindings affect the answer where defined;
13. broad CLEAR requires broad-enough evidence coverage;
14. CONFLICT survives unrelated uncertainty;
15. annotations cannot hide a core state;
16. the superseded-review case has a defensible answer.

Passing review does not authorize implementation.

Ruben decides whether PSP proceeds to design.

---

# 36. Governing Principles

> **PSP cannot claim a road is clear if its observation boundary was constructed so the other traffic could never appear.**

> **Discovery must be capable of finding evidence that defeats its own working state.**

> **Recording an assertion does not make it independent evidence.**

> **Agreement count is not evidence independence.**

> **Self-state and relational state are different evidentiary problems.**

> **Representation is not automatically identity.**

> **Operation intent is not automatically operation fact.**

> **A lifecycle claim that cannot be falsified is not a trustworthy lifecycle claim.**

> **The baseline is an evidence protocol, not merely a compatibility table.**

> **Facts need lineage; relationships need evidence; state needs currency.**

> **CLEAR means positively justified CLEAR.**

> **CONFLICT means positively established coordination conflict.**

> **UNKNOWN means PSP knows exactly which required proposition it cannot establish.**

END — PSP v0.2 REQUIREMENTS DRAFT 5
