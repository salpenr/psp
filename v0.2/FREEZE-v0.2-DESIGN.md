# PSP v0.2 — DESIGN FREEZE (revision 1) — ATTACK TARGET

**Frozen 2026-09-15 by Claude per Ruben's design order §17.** Grok attacks this exact revision. No repair during attack. Implementation is NOT authorized by this freeze.

| Item | Value |
|---|---|
| Repo | `<home>\psp` (same local git as v0.1; v0.1 code byte-identical to tag `psp-v0.1`, verified `git diff --quiet psp-v0.1 -- psp.py test_psp.py`) |
| Tag | `psp-v0.2-design-r1` (annotated, object `36257fa915a8971909b4942ffb2055ff921c0cfd`) |
| Commit | `a7b459c304379eabaab23ace5fc3405590862fc7` |
| Requirements baseline | `v0.2/PSP-v0.2-REQUIREMENTS-BASELINE.md` sha256 `55e9002f3fa20d2390cc45b3881bbe9c73aa75bf899623b71e245a07111a7ea5` (Draft 5 + one §23 sentence; correction record at its head) |
| Source Draft 5 | `PSP-v0.2-REQUIREMENTS-DRAFT5-2026-09-15.md` sha256 `d4ca86cae7243960ad27f76e6cfeb3a93353277f9558e84d750f1a3f60b4fda1` (Ruben's drop, committed as received) |
| Known gaps | `v0.2/KNOWN-GAPS.md` sha256 `adc62c5acdd38a9c79afbf4867a4b3148f6a257c08ac3ddb541aab9c256a991e` (KG-01…KG-14) |
| Design mapping | `v0.2/PSP-v0.2-DESIGN-MAPPING.md` sha256 `a6daf322c2d1a2d0415f530a4575a104371d244b30e718a70af2e8fe039cc800` (M-01…M-12, requirement→mechanism table, test plan, not-chosen list, visible limits, position statements) |
| Environment | Python 3.11.9, Windows 11 (10.0.26200); documents only, no code produced |
| Collaboration packet | `PSP Collaboration Packet — Close Draft 5 and Prepare the Empirical Phase.md` (Ruben's drop, committed as received) |

Reproduce the freeze check:

```bash
cd <home>/psp && git status --short && git rev-parse psp-v0.2-design-r1^{commit} && sha256sum v0.2/PSP-v0.2-REQUIREMENTS-BASELINE.md v0.2/KNOWN-GAPS.md v0.2/PSP-v0.2-DESIGN-MAPPING.md && git diff --quiet psp-v0.1 -- psp.py test_psp.py && echo v0.1-code-untouched
```

## What Grok is asked to attack (order §13)

Whether each mechanism M-01…M-12 actually produces the evidence its requirement needs, concentrating on: identity (M-03), working instance (M-02), artifact aliasing (M-03, §13 family), operation classification (M-05), lifecycle (M-07), abandoned claims (M-07, M-08), revision binding (M-04), discovery completeness (M-01, M-06), false CLEAR, false CONFLICT, false UNKNOWN. The five position statements in mapping §7 are offered as targets.

## Record shape for any break

`source version/hash → mechanism → attack procedure → observed → expected (baseline row or KG) → visible in basis? → classification (BLOCKER / KNOWN GAP / DESIGN QUESTION / BLOCKED)`.
