"""PSP v0.2 first-success experiment (Ruben's implementation order, FIRST SUCCESS TEST / CONTROL / UNCERTAINTY).

Two participating workers are real separate OS processes that stay alive while PSP evaluates (module-API callers, so the
liveness probe is active).  A third run repeats the success case through the CLI, where pids are transient (IN-01), to
record that limitation as evidence.  Everything is written under ./experiment/<timestamp>/ : the shared store, every basis
as JSON, and a RESULTS.md.  Nothing is repaired here; failures are recorded as failures.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import psp2 as P  # noqa: E402

PY = sys.executable
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT = HERE / "experiment" / STAMP
OUT.mkdir(parents=True, exist_ok=True)
WS = OUT / "workspace"; WS.mkdir()
DB = str(OUT / "psp-v0.2.db")
(WS / "X.md").write_text("artifact X, revision 1\n", encoding="utf-8")
RESULTS: list[dict] = []


def worker(actor: str, op: str, target: str, hold_seconds: int = 30, instance: str | None = None) -> tuple[subprocess.Popen, dict]:
    """Spawn a long-lived worker process that claims and then holds (simulating a worker doing the work)."""
    script = ("import sys,json,time; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); "
              "c=p.claim('experiment',%r,%r,%r,root=%r,instance_id=%r); print(json.dumps(c),flush=True); p.close(); time.sleep(%d)"
              % (str(HERE), DB, actor, op, target, str(WS), instance, hold_seconds))
    proc = subprocess.Popen([PY, "-c", script], stdout=subprocess.PIPE, text=True)
    claim = json.loads(proc.stdout.readline())
    return proc, claim


def record(name: str, basis: dict, expected: str, note: str = "") -> None:
    ok = basis["signal"] == expected
    path = OUT / f"{name}.basis.json"
    path.write_text(json.dumps(basis, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    RESULTS.append({"case": name, "expected": expected, "produced": basis["signal"], "pass": ok, "row": basis["answer_key_row"],
                    "unresolved": [u["proposition"] for u in basis["unresolved"]], "annotations": basis["annotations"],
                    "conflicts_with": [f"{c['actor']}/{c['op_class']}/{c['claim_id']}" for c in basis["conflicts"]],
                    "evaluation_id": basis.get("evaluation_id"), "basis_file": path.name, "note": note})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected {expected}, produced {basis['signal']}  {P.summary_line(basis)}")


def main() -> None:
    p = P.PSP2(DB)
    procs: list[subprocess.Popen] = []
    try:
        # ---- FIRST SUCCESS TEST: Claude LIVE WRITE X; Grok approaches WRITE X (and aliases) -> CONFLICT with WHY
        pa, ca = worker("claude", "WRITE", "X.md"); procs.append(pa)
        for i, ref in enumerate(["X.md", "./X.md", "foo/../X.md"]):
            pb, cb = worker("grok", "WRITE", ref); procs.append(pb)
            b = p.evaluate(cb["claim_id"])
            record(f"01-success-write-write-{i}-{ref.replace('/', '_').replace('.', '_')}", b, "CONFLICT",
                   f"grok reference {ref!r}; both workers are live separate processes")
            # WHY must identify: working instances, operations, artifact relationship, lifecycle evidence, baseline row, evaluation time
            why_ok = all([b["conflicts"] and b["conflicts"][0]["instance_id"] != b["subject"]["instance_id"],
                          b["conflicts"][0]["op_class"] == "WRITE" and b["subject"]["op_class"] == "WRITE",
                          b["observations_admitted"][0]["identity"]["relation"] == "SAME",
                          b["conflicts"][0]["lifecycle"]["rule"].startswith("accepted CLAIMED"),
                          b["answer_key_row"] == "WRITE/WRITE", bool(b["evaluation_time"])])
            RESULTS[-1]["why_complete"] = why_ok
            # grok releases so the next alias run is a fresh pair
            p.release(cb["claim_id"], cb["instance_id"]); pb.kill(); pb.wait()
        p.release(ca["claim_id"], ca["instance_id"]); pa.kill(); pa.wait()

        # ---- CONTROL: Claude READ X; Grok READ X -> CLEAR with basis
        pa, ca = worker("claude", "READ", "X.md"); procs.append(pa)
        pb, cb = worker("grok", "READ", "./X.md"); procs.append(pb)
        record("02-control-read-read", p.evaluate(cb["claim_id"]), "CLEAR", "HISTORICAL_CONFLICT expected in annotations (B23)")
        p.release(ca["claim_id"], ca["instance_id"]); p.release(cb["claim_id"], cb["instance_id"]); pa.kill(); pb.kill()

        # ---- UNCERTAINTY: identity cannot be established (one reference resolves, the other does not) -> UNKNOWN naming the proposition
        pa, ca = worker("claude", "WRITE", "X.md"); procs.append(pa)
        pb, cb = worker("grok", "WRITE", "not-yet-created.md"); procs.append(pb)
        record("03-uncertainty-identity", p.evaluate(cb["claim_id"]), "UNKNOWN", "SAME/DISTINCT unresolved: exactly one reference exists")
        p.release(ca["claim_id"], ca["instance_id"]); p.release(cb["claim_id"], cb["instance_id"]); pa.kill(); pb.kill()

        # ---- UNCERTAINTY 2: dead claimant (process exited without RELEASE) -> UNKNOWN naming LIVE(claim)
        script = ("import sys,json; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); print(json.dumps(p.claim('experiment','claude','WRITE','X.md',root=%r)))"
                  % (str(HERE), DB, str(WS)))
        dead = json.loads(subprocess.run([PY, "-c", script], capture_output=True, text=True, check=True).stdout)
        pb, cb = worker("grok", "WRITE", "X.md"); procs.append(pb)
        record("04-uncertainty-dead-claimant", p.evaluate(cb["claim_id"]), "UNKNOWN", "claude's claiming process exited; KG-05 exposure")
        p.release(dead["claim_id"], operator="ruben", note="experiment: closing dead claim")
        record("05-after-operator-release", p.evaluate(cb["claim_id"]), "CLEAR", "operator release (KG-04) closed the dead claim; HISTORICAL_CONFLICT expected")
        p.release(cb["claim_id"], cb["instance_id"]); pb.kill()

        # ---- REVIEW/WRITE under the owner's §23 sentence, then supersession (§26)
        pr, cr = worker("grok", "REVIEW", "X.md"); procs.append(pr)
        pw, cw = worker("claude", "WRITE", "./X.md"); procs.append(pw)
        record("06-review-then-write-owner-s23", p.evaluate(cw["claim_id"]), "CONFLICT", "review bound to current revision; T-B6")
        (WS / "X.md").write_text("artifact X, revision 2 by claude\n", encoding="utf-8")
        p.ready(cw["claim_id"], cw["instance_id"], note="published revision 2"); p.release(cw["claim_id"], cw["instance_id"]); pw.kill()
        record("07-superseded-review", p.evaluate(cr["claim_id"]), "CLEAR", "B24: CLEAR + SUPERSEDED_REVIEW; no live writer")
        p.release(cr["claim_id"], cr["instance_id"]); pr.kill()

        # ---- CLI path (IN-01): same success case through the command line; pids transient -> PROBE_UNAVAILABLE annotation
        base = [PY, str(HERE / "psp2.py"), "--db", DB, "--json"]
        r1 = subprocess.run(base + ["claim", "--project", "experiment", "--as", "claude", "--op", "WRITE", "--target", "X.md", "--root", str(WS)],
                            capture_output=True, text=True)
        c1 = json.loads(r1.stdout.split("\n", 1)[0])
        r2 = subprocess.run(base + ["claim", "--project", "experiment", "--as", "grok", "--op", "WRITE", "--target", "./X.md", "--root", str(WS)],
                            capture_output=True, text=True)
        b2 = json.loads(r2.stdout.split("\n", 1)[1])
        record("08-cli-transient-pids", b2, "CONFLICT", "IN-01: CLI pids are transient, probe unavailable, LIVE by rule; exit code %d (observational)" % r2.returncode)
        RESULTS[-1]["cli_exit_code"] = r2.returncode
        # (claims left LIVE on purpose: shows what an abandoned CLI claim looks like in `status`)
        status = p.status()
        (OUT / "09-status-after.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        metrics = p.metrics()
        (OUT / "10-metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        verify = p.verify()
    finally:
        for pr_ in procs:
            try:
                pr_.kill(); pr_.wait(timeout=5)
            except Exception:
                pass
        p.close()

    env = {"python": sys.version.split()[0], "platform": sys.platform, "psp2_version": P.VERSION, "profile": P.PROFILE,
           "store": DB, "workspace": str(WS), "run": STAMP}
    passes = sum(1 for r in RESULTS if r["pass"]); total = len(RESULTS)
    lines = [f"# PSP v0.2 first-success experiment — {STAMP}", "", f"**Result:** {passes}/{total} cases produced the expected signal. "
             f"Chain verify: `{verify}`.", "", "| case | expected | produced | pass | row | unresolved | annotations | conflicts_with | why complete | note |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in RESULTS:
        lines.append(f"| {r['case']} | {r['expected']} | {r['produced']} | {'PASS' if r['pass'] else 'FAIL'} | {r['row'] or '-'} | "
                     f"{'; '.join(r['unresolved']) or '-'} | {','.join(r['annotations']) or '-'} | {', '.join(r['conflicts_with']) or '-'} | "
                     f"{r.get('why_complete', '-')} | {r['note']} |")
    lines += ["", "## Metrics after the run", "", "```json", json.dumps(metrics, indent=2), "```", "", "## Environment", "", "```json",
              json.dumps(env, indent=2), "```", "", "Bases: one `*.basis.json` per case beside this file. Store: `psp-v0.2.db` (append-only, hash-chained)."]
    (OUT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "results.json").write_text(json.dumps({"env": env, "results": RESULTS, "verify": verify}, indent=2, default=str), encoding="utf-8")
    print(f"\n{passes}/{total} -> {OUT / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
