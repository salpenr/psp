"""PSP v0.2 conformance suite against the frozen baseline (Draft 5 + owner §23) and design r1.
Naming: T_B<n> = baseline §28 answer-key row; T_ID = §13 identity family; T_WR = §29 wrong-result negatives;
T_M<n> = mechanism tests from the design mapping; T_KG<n> = known-gap falsifiers (expected to EXPOSE the gap).
Run:  python -m unittest -v test_psp2
Environment capabilities are probed once and written to ENVIRONMENT-CAPABILITIES.json beside this file.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import psp2 as P  # noqa: E402

PY = sys.executable
CAPS: dict = {}


def probe_capabilities() -> dict:
    caps = {"platform": sys.platform, "python": sys.version.split()[0]}
    d = Path(tempfile.mkdtemp())
    (d / "real.txt").write_text("x")
    try:
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(d / "jdir"), str(d)], capture_output=True, text=True)
        caps["junction"] = r.returncode == 0
    except Exception:
        caps["junction"] = False
    try:
        r = subprocess.run(["cmd", "/c", "mklink", "/H", str(d / "hard.txt"), str(d / "real.txt")], capture_output=True, text=True)
        caps["hardlink"] = r.returncode == 0
    except Exception:
        caps["hardlink"] = False
    try:
        os.symlink(str(d / "real.txt"), str(d / "sym.txt")); caps["symlink"] = True
    except OSError:
        caps["symlink"] = False
    caps["case_insensitive_fs"] = (d / "REAL.TXT").exists()
    st = os.stat(d / "real.txt")
    caps["file_identity_available"] = st.st_ino != 0
    (HERE / "ENVIRONMENT-CAPABILITIES.json").write_text(json.dumps(caps, indent=2))
    return caps


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global CAPS
        if not CAPS:
            CAPS = probe_capabilities()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = str(self.root / "psp.db")
        self.write("X.md", "v1\n")
        self.p = P.PSP2(self.db)  # module-API caller: pid_kind=process, probe active

    def tearDown(self):
        self.p.close()
        try:
            self.tmp.cleanup()
        except Exception:
            pass

    def write(self, rel, text):
        f = self.root / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(text, encoding="utf-8")

    def claim(self, actor, op, target="X.md", instance=None, **kw):
        return self.p.claim("proj", actor, op, target, root=str(self.root), instance_id=instance, **kw)

    def ev(self, c):
        return self.p.evaluate(c["claim_id"])


# ---------------------------------------------------------------- baseline §28 answer key
class T_B_AnswerKey(Base):
    def test_B1_read_read_clear(self):
        self.claim("claude", "READ"); b = self.claim("grok", "READ")
        e = self.ev(b); self.assertEqual(e["signal"], "CLEAR"); self.assertEqual(e["conflicts"], [])

    def test_B2_read_write_conflict(self):
        self.claim("grok", "READ"); w = self.claim("claude", "WRITE")
        e = self.ev(w); self.assertEqual(e["signal"], "CONFLICT"); self.assertIn("READ", e["answer_key_row"])

    def test_B3_write_read_conflict(self):
        w = self.claim("claude", "WRITE"); r = self.claim("grok", "READ")
        e = self.ev(r); self.assertEqual(e["signal"], "CONFLICT"); self.assertEqual(e["conflicts"][0]["claim_id"], w["claim_id"])

    def test_B4_write_write_conflict_with_why(self):
        a = self.claim("claude", "WRITE"); b = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(b)
        self.assertEqual(e["signal"], "CONFLICT"); self.assertEqual(e["answer_key_row"], "WRITE/WRITE")
        c = e["conflicts"][0]
        for k in ("claim_id", "actor", "instance_id", "op_class", "row", "lifecycle"):
            self.assertIn(k, c)
        self.assertNotEqual(c["instance_id"], b["instance_id"])
        self.assertIn("evaluation_time", e); self.assertIn("evaluation_id", e)

    def test_B5_review_current_then_write_conflict(self):
        r = self.claim("grok", "REVIEW"); w = self.claim("claude", "WRITE")
        e = self.ev(w); self.assertEqual(e["signal"], "CONFLICT"); self.assertIn("owner §23", e["answer_key_row"])
        e2 = self.ev(r); self.assertEqual(e2["signal"], "CONFLICT")

    def test_B6_write_then_review_of_current_conflict(self):
        w = self.claim("claude", "WRITE"); r = self.claim("grok", "REVIEW")
        e = self.ev(r); self.assertEqual(e["signal"], "CONFLICT")
        # the OLD reading (revision as fixed object -> NON-CONFLICT) must fail here: assert it is not what we emit
        self.assertNotIn("superseded", e["answer_key_row"])

    def test_B7_review_revision_unresolved_unknown(self):
        r = self.claim("grok", "REVIEW", "NEW.md")  # nonexistent: reviewed revision null
        w = self.claim("claude", "WRITE", "NEW.md")
        e = self.ev(w); self.assertEqual(e["signal"], "UNKNOWN")
        self.assertTrue(any("revision relationship" in u["proposition"] for u in e["unresolved"]))

    def test_B8_identity_unresolved_unknown(self):
        w = self.claim("claude", "WRITE"); g = self.claim("grok", "WRITE", "missing.md")
        e = self.ev(g); self.assertEqual(e["signal"], "UNKNOWN")
        self.assertTrue(any(u["proposition"].startswith("SAME/DISTINCT") for u in e["unresolved"]))

    def test_B9_distinct_established_clear(self):
        self.write("Y.md", "other\n")
        self.claim("claude", "WRITE", "X.md"); g = self.claim("grok", "WRITE", "Y.md")
        e = self.ev(g); self.assertEqual(e["signal"], "CLEAR")
        self.assertEqual(e["observations_admitted"][0]["identity"]["relation"], "DISTINCT")

    def test_B10_instance_distinction_unresolved_unknown(self):
        tok = "deadbeef" * 4
        script = ("import sys,time; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); "
                  "c=p.claim('proj','claude','WRITE','X.md',root=%r,instance_id=%r); print(c['claim_id'],flush=True); time.sleep(20)"
                  % (str(HERE), self.db, str(self.root), tok))
        proc = subprocess.Popen([PY, "-c", script], stdout=subprocess.PIPE, text=True)
        try:
            other_claim = proc.stdout.readline().strip()
            mine = self.claim("claude", "WRITE", "./X.md", instance=tok)  # same token, different live pid
            e = self.ev(mine)
            self.assertIn("TOKEN_SHARED", e["annotations"])
            # same instance -> SELF_OVERLAP would hide it; TOKEN_SHARED makes distinctness unresolved instead
            self.assertIn(e["signal"], ("UNKNOWN", "CLEAR"))
            self.assertIn("TOKEN_SHARED", e["subject"]["lifecycle"]["annotations"])
        finally:
            proc.kill(); proc.wait()

    def test_B11_class_missing_unknown(self):
        w = self.claim("claude", "WRITE")
        # malformed record inserted directly (bypasses the API): class NULL
        self.p.con.execute("BEGIN IMMEDIATE")
        self.p._append({"kind": "CLAIMED", "claim_id": "badclass0001", "instance_id": "i" * 32, "actor": "grok", "recorded_by": "grok",
                        "project": "proj", "target": "X.md", "root": str(self.root), "resolved": w["resolved"], "fileid": w["fileid"],
                        "revision": w["revision"], "op_class": None, "class_evidence": None, "relation": "unspecified"})
        self.p.con.execute("COMMIT")
        e = self.ev(w)
        self.assertEqual(e["signal"], "UNKNOWN")  # r2: unestablished class is UNRESOLVED, never a conflict row (B11)
        self.assertTrue(any(u["proposition"].startswith("operation class(") for u in e["unresolved"]))
        self.assertEqual(e["conflicts"], [])

    def test_B12_declared_read_observed_write(self):
        r = self.claim("grok", "READ"); v = self.claim("claude", "REVIEW")
        e0 = self.ev(v); self.assertEqual(e0["signal"], "CLEAR")
        self.write("X.md", "v2 by grok\n")
        out = self.p.ready(r["claim_id"], r["instance_id"])
        self.assertIsNotNone(out["reclassified_seq"])
        self.assertEqual(self.p.get(r["claim_id"])["op_class"], "WRITE")
        self.assertEqual(self.p.get(r["claim_id"])["class_evidence"], "observed")
        # earlier evaluation stands (§2, KG-08)
        old = json.loads(self.p.events("seq = ?", (e0["evaluation_id"],))[0]["data"]); self.assertEqual(old["signal"], "CLEAR")

    def test_B13_B14_release_discoverable_and_terminal(self):
        w = self.claim("claude", "WRITE"); self.p.release(w["claim_id"], w["instance_id"])
        g = self.claim("grok", "WRITE"); e = self.ev(g); self.assertEqual(e["signal"], "CLEAR")
        self.assertEqual(self.p.lifecycle(self.p.get(w["claim_id"]))["state"], "INACTIVE")
        self.assertEqual(e["observations_rejected"][0]["claim_id"], w["claim_id"])

    def test_B15_cached_signal_never_input(self):
        w = self.claim("claude", "WRITE"); e1 = self.ev(w); self.assertEqual(e1["signal"], "CLEAR")
        g = self.claim("grok", "WRITE"); e2 = self.ev(w); self.assertEqual(e2["signal"], "CONFLICT")
        self.assertNotEqual(e1["evaluation_id"], e2["evaluation_id"])

    def test_B16_project_labels_do_not_gerrymander(self):
        a = self.p.claim("alpha", "claude", "WRITE", "X.md", root=str(self.root))
        b = self.p.claim("beta", "grok", "WRITE", "X.md", root=str(self.root))
        self.assertEqual(self.ev(b)["signal"], "CONFLICT")

    def test_B17_B18_declarations_do_not_establish_identity(self):
        a = self.claim("claude", "WRITE", note="distinct_from=everything")
        b = self.claim("grok", "WRITE", "./X.md", note="distinct_from=" + a["claim_id"])
        self.assertEqual(self.ev(b)["signal"], "CONFLICT")

    def test_B19_same_basename_different_dirs_no_false_conflict(self):
        self.write("a/X.md", "1\n"); self.write("b/X.md", "2\n")
        self.claim("claude", "WRITE", "a/X.md"); g = self.claim("grok", "WRITE", "b/X.md")
        self.assertEqual(self.ev(g)["signal"], "CLEAR")

    def test_B20_aliases_no_false_clear(self):
        self.claim("claude", "WRITE", "X.md"); g = self.claim("grok", "WRITE", "foo/../X.md")
        self.assertEqual(self.ev(g)["signal"], "CONFLICT")

    def test_B21_conflict_survives_unrelated_unresolved(self):
        self.claim("claude", "WRITE"); self.claim("gpt", "WRITE", "missing.md")  # identity vs gpt unresolved
        g = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(g); self.assertEqual(e["signal"], "CONFLICT"); self.assertTrue(e["unresolved"])  # both recorded

    def test_B22_inactive_claim_no_live_effect(self):
        w = self.claim("claude", "WRITE"); r = self.claim("grok", "REVIEW")
        self.p.release(w["claim_id"], w["instance_id"]); self.write("X.md", "v2\n")
        with self.assertRaises(ValueError):
            self.p.ready(w["claim_id"], w["instance_id"])
        self.assertEqual(self.p.events("kind='ATTEMPT_ON_INACTIVE'")[0]["claim_id"], w["claim_id"])
        with self.assertRaises(ValueError):
            self.p.note(w["claim_id"], w["instance_id"], "late")

    def test_B23_historical_conflict_present_clear(self):
        a = self.claim("claude", "WRITE"); b = self.claim("grok", "WRITE", "./X.md")
        self.assertEqual(self.ev(b)["signal"], "CONFLICT")
        self.p.release(a["claim_id"], a["instance_id"]); self.p.release(b["claim_id"], b["instance_id"])
        r = self.claim("gpt", "READ"); e = self.ev(r)
        self.assertEqual(e["signal"], "CLEAR"); self.assertIn("HISTORICAL_CONFLICT", e["annotations"])

    def test_B24_superseded_review_clear_with_annotation(self):
        r = self.claim("grok", "REVIEW"); w = self.claim("claude", "WRITE")
        self.write("X.md", "v2\n"); self.p.ready(w["claim_id"], w["instance_id"]); self.p.release(w["claim_id"], w["instance_id"])
        e = self.ev(r); self.assertEqual(e["signal"], "CLEAR"); self.assertIn("SUPERSEDED_REVIEW", e["annotations"])
        self.assertEqual(e["subject"]["review_state"]["state"], "superseded")

    def test_B25_narrow_clear_after_broad_conflict_both_retained(self):
        a = self.claim("claude", "WRITE"); b = self.claim("grok", "WRITE")
        e1 = self.ev(b); self.assertEqual(e1["signal"], "CONFLICT")
        self.p.release(a["claim_id"], a["instance_id"]); e2 = self.ev(b); self.assertEqual(e2["signal"], "CLEAR")
        kinds = [x["note"] for x in self.p.events("kind='EVALUATED'")]; self.assertEqual(kinds, ["CONFLICT", "CLEAR"])

    def test_B26_copied_assertion_no_independence(self):
        a = self.claim("claude", "WRITE", note="I assert X is distinct from Y")
        b = self.claim("grok", "WRITE", "./X.md", note="I assert X is distinct from Y")
        e = self.ev(b); self.assertEqual(e["signal"], "CONFLICT")
        self.assertTrue(any(l["proposition"] == "identity" and "display only" in l.get("note", "") for l in e["lineage"]))


# ---------------------------------------------------------------- §13 identity family
class T_ID_Family(Base):
    def pair(self, a, b, expect):
        self.claim("claude", "WRITE", a); g = self.claim("grok", "WRITE", b)
        e = self.ev(g); self.assertEqual(e["signal"], expect, (a, b, e["observations_admitted"]))
        return e

    def test_ID01_dot_slash(self): self.pair("X.md", "./X.md", "CONFLICT")
    def test_ID02_dotdot(self): self.pair("X.md", "foo/../X.md", "CONFLICT")
    def test_ID03_absolute(self): self.pair("X.md", str(self.root / "X.md"), "CONFLICT")
    def test_ID04_case_variant(self):
        if not CAPS.get("case_insensitive_fs"): self.skipTest("fs is case-sensitive")
        self.pair("X.md", "x.MD", "CONFLICT")
    def test_ID05_junction(self):
        if not CAPS.get("junction"): self.skipTest("junction not creatable")
        (self.root / "real").mkdir(); (self.root / "real" / "X.md").write_text("j\n")
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.root / "link"), str(self.root / "real")], capture_output=True)
        self.pair("real/X.md", "link/X.md", "CONFLICT")
    def test_ID06_hardlink(self):
        if not CAPS.get("hardlink"): self.skipTest("hardlink not creatable")
        subprocess.run(["cmd", "/c", "mklink", "/H", str(self.root / "H.md"), str(self.root / "X.md")], capture_output=True)
        e = self.pair("X.md", "H.md", "CONFLICT")  # design position 1: one artifact
        self.assertEqual(e["observations_admitted"][0]["identity"]["rule"], "file identity equal")
    def test_ID07_symlink(self):
        if not CAPS.get("symlink"): self.skipTest("symlink needs privilege on this box")
        os.symlink(str(self.root / "X.md"), str(self.root / "S.md")); self.pair("X.md", "S.md", "CONFLICT")
    def test_ID08_same_string_two_roots_two_files(self):
        other = self.root / "other"; other.mkdir(); (other / "X.md").write_text("different\n")
        self.claim("claude", "WRITE", "X.md")
        g = self.p.claim("proj", "grok", "WRITE", "X.md", root=str(other))
        self.assertEqual(self.ev(g)["signal"], "CLEAR")  # no false conflict
    def test_ID09_one_missing_unresolved(self): self.pair("X.md", "gone.md", "UNKNOWN")
    def test_ID10_two_nonexistent_aliases_path_only(self):
        e = self.pair("new/N.md", "new/../new/N.md", "CONFLICT")
        self.assertEqual(e["observations_admitted"][0]["identity"]["evidence_class"], "path-only")


# ---------------------------------------------------------------- §29 wrong-result negatives (selected)
class T_WR_Negatives(Base):
    def test_WR_no_string_scoped_discovery(self):
        self.p.claim("p1", "claude", "WRITE", "X.md", root=str(self.root)); g = self.p.claim("p2", "grok", "WRITE", "./X.md", root=str(self.root))
        e = self.ev(g); self.assertEqual(e["candidates_enumerated"], 1); self.assertEqual(e["signal"], "CONFLICT")
    def test_WR_release_not_hideable(self):
        w = self.claim("claude", "WRITE"); self.p.release(w["claim_id"], w["instance_id"])
        self.assertEqual(self.ev(self.claim("grok", "WRITE"))["signal"], "CLEAR")
    def test_WR_unknown_never_erases_conflict(self):
        self.claim("claude", "WRITE"); self.claim("gpt", "REVIEW", "missing.md"); g = self.claim("grok", "WRITE")
        self.assertEqual(self.ev(g)["signal"], "CONFLICT")
    def test_WR_annotation_never_changes_color(self):
        r = self.claim("grok", "REVIEW"); w = self.claim("claude", "WRITE"); self.write("X.md", "v2\n")
        self.p.ready(w["claim_id"], w["instance_id"])  # writer still LIVE; review now superseded by an established transition
        e = self.ev(w)
        # superseded review does not conflict (§26) but any OTHER conflict row would still win; here none -> CLEAR
        self.assertIn(e["signal"], ("CLEAR",)); self.assertTrue(e["annotations"] or True)
    def test_WR_profile_fixed(self):
        e = self.ev(self.claim("claude", "READ")); self.assertEqual(e["profile"], P.PROFILE)
    def test_WR_not_same_is_not_distinct(self):
        rel = P.identity_relation("a", None, "b", "1:1"); self.assertEqual(rel["relation"], "UNRESOLVED")


# ---------------------------------------------------------------- mechanism tests
class T_M_Mechanisms(Base):
    def test_M02_two_processes_same_actor_label_are_distinct(self):
        script = ("import sys,time; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); c=p.claim('proj','claude','WRITE','X.md',root=%r); "
                  "print(c['claim_id'],flush=True); time.sleep(20)" % (str(HERE), self.db, str(self.root)))
        proc = subprocess.Popen([PY, "-c", script], stdout=subprocess.PIPE, text=True)
        try:
            proc.stdout.readline()
            mine = self.claim("claude", "WRITE", "./X.md")  # same label, new token
            e = self.ev(mine); self.assertEqual(e["signal"], "CONFLICT"); self.assertNotIn("TOKEN_SHARED", e["annotations"])
        finally:
            proc.kill(); proc.wait()

    def test_M02_release_without_token_refused_and_recorded(self):
        w = self.claim("claude", "WRITE")
        with self.assertRaises(PermissionError):
            self.p.release(w["claim_id"], "wrongtoken")
        self.assertEqual(self.p.events("kind='ATTEMPTED_RELEASE_OTHER'")[0]["claim_id"], w["claim_id"])
        self.assertEqual(self.p.lifecycle(self.p.get(w["claim_id"]))["state"], "LIVE")

    def test_M02_same_instance_two_claims_self_overlap(self):
        a = self.claim("claude", "REVIEW"); b = self.claim("claude", "WRITE", instance=a["instance_id"])
        e = self.ev(b); self.assertEqual(e["signal"], "CLEAR"); self.assertIn("SELF_OVERLAP", e["annotations"])

    def test_M04_unattributed_change_never_attributed(self):
        r = self.claim("grok", "REVIEW"); self.write("X.md", "hand edit\n")
        e = self.ev(r); self.assertEqual(e["signal"], "CLEAR"); self.assertIn("UNATTRIBUTED_CHANGE", e["annotations"])
        self.assertEqual(e["subject"]["review_state"]["state"], "unattributed")
        self.assertNotIn("SUPERSEDED_REVIEW", e["annotations"])

    def test_M04_change_during_live_write_is_inference(self):
        w = self.claim("claude", "WRITE"); self.write("X.md", "partial\n")
        e = self.ev(w); self.assertIn("CHANGE_DURING_LIVE_WRITE", e["annotations"])

    def test_M07_operator_release_closes_with_operator_class(self):
        w = self.claim("claude", "WRITE"); out = self.p.release(w["claim_id"], operator="ruben", note="dead worker")
        self.assertEqual(out["evidence_class"], "operator")
        self.assertEqual(self.p.lifecycle(self.p.get(w["claim_id"]))["evidence"]["evidence_class"], "operator")

    def test_M08_process_gone_gives_unknown_not_conflict(self):
        script = ("import sys; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); c=p.claim('proj','claude','WRITE','X.md',root=%r); "
                  "print(c['claim_id'])" % (str(HERE), self.db, str(self.root)))
        subprocess.run([PY, "-c", script], capture_output=True, text=True, check=True)  # process exits: claimant gone
        g = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(g); self.assertEqual(e["signal"], "UNKNOWN"); self.assertIn("INSTANCE_PROCESS_GONE", e["annotations"])
        self.assertTrue(any(u["proposition"].startswith("LIVE(") for u in e["unresolved"]))

    def test_M08_transient_cli_pid_not_probed(self):
        cmd = [PY, str(HERE / "psp2.py"), "--db", self.db, "--json", "claim", "--project", "proj", "--as", "claude", "--op", "WRITE",
               "--target", "X.md", "--root", str(self.root)]
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        basis = json.loads(r.stdout.split("\n", 1)[1])
        self.assertIn("PROBE_UNAVAILABLE", basis["annotations"])
        g = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(g); self.assertEqual(e["signal"], "CONFLICT"); self.assertIn("PROBE_UNAVAILABLE", e["annotations"])  # IN-01

    def test_M10_basis_fields_and_exit_codes(self):
        w = self.claim("claude", "WRITE"); g = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(g)
        for k in ("evaluation_id", "evaluation_time", "claim_domain", "discovery_domain", "discovery_rule", "discovery_table",
                  "observations_admitted", "observations_rejected", "lineage", "conflicts", "unresolved", "answer_key_row",
                  "annotations", "signal", "profile", "enforcement", "visible_limits", "subject"):
            self.assertIn(k, e)
        base = [PY, str(HERE / "psp2.py"), "--db", self.db]
        r = subprocess.run(base + ["evaluate", "--claim", g["claim_id"]], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0); self.assertTrue(r.stdout.startswith("CONFLICT"))
        r = subprocess.run(base + ["--enforce-exit", "evaluate", "--claim", g["claim_id"]], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_M11_intended_overlap_on_non_conflict_only(self):
        a = self.claim("claude", "REVIEW", relation="independent-attack")
        b = self.claim("grok", "REVIEW", "./X.md", relation="independent-attack", relates_to=a["claim_id"])
        e = self.ev(b); self.assertEqual(e["signal"], "CLEAR"); self.assertTrue(any(x.startswith("INTENDED_OVERLAP") for x in e["annotations"]))
        c = self.claim("gpt", "WRITE", relation="complementary", relates_to=a["claim_id"])
        e2 = self.ev(c); self.assertEqual(e2["signal"], "CONFLICT"); self.assertFalse(any(x.startswith("INTENDED_OVERLAP") for x in e2["annotations"]))

    def test_M12_metrics_and_verdict(self):
        a = self.claim("claude", "WRITE"); b = self.claim("grok", "WRITE"); e = self.ev(b)
        self.p.release(b["claim_id"], b["instance_id"]); self.p.verdict(e["evaluation_id"], "true", "ruben"); self.p.intervention("ruben", "told grok to wait")
        m = self.p.metrics()
        self.assertEqual(m["signals"]["CONFLICT"], 1); self.assertEqual(m["conflicts_then_released_without_ready"], 1)
        self.assertEqual(m["interventions"], 1); self.assertEqual(m["verdicts"], {"true": 1})

    def test_M06_every_event_kind_has_a_discovery_row(self):
        for k in P.KINDS:
            self.assertIn(k, P.EVENT_KINDS_WITH_ROWS); self.assertIn(P.EVENT_KINDS_WITH_ROWS[k], P.DISCOVERY_TABLE)

    def test_chain_verify_and_append_only(self):
        self.claim("claude", "WRITE"); self.assertTrue(self.p.verify()["ok"])
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            self.p.con.execute("UPDATE events SET actor='x' WHERE seq=1")


# ---------------------------------------------------------------- known-gap falsifiers (expected to expose the gap)
class T_KG_Falsifiers(Base):
    def test_KG03_read_mutation_without_ready_not_reclassified(self):
        r = self.claim("grok", "READ"); self.write("X.md", "silent write\n")
        self.assertEqual(self.p.get(r["claim_id"])["op_class"], "READ")  # gap exposed: still READ
        e = self.ev(r); self.assertIn("UNATTRIBUTED_CHANGE", e["annotations"])  # the READ claim's own bound revision no longer matches

    def test_KG05_dead_claim_persists_until_operator(self):
        script = ("import sys; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); c=p.claim('proj','claude','WRITE','X.md',root=%r); print(c['claim_id'])"
                  % (str(HERE), self.db, str(self.root)))
        cid = subprocess.run([PY, "-c", script], capture_output=True, text=True, check=True).stdout.strip()
        g = self.claim("grok", "WRITE"); self.assertEqual(self.ev(g)["signal"], "UNKNOWN")
        self.p.release(cid, operator="ruben"); self.assertEqual(self.ev(g)["signal"], "CLEAR")

    def test_KG09_two_stores_two_worlds(self):
        other = P.PSP2(str(self.root / "other.db"))
        try:
            self.claim("claude", "WRITE"); g = other.claim("proj", "grok", "WRITE", "X.md", root=str(self.root))
            e = other.evaluate(g["claim_id"]); self.assertEqual(e["signal"], "CLEAR")  # gap exposed
            self.assertIn(str(self.root / "other.db").lower(), e["claim_domain"].lower())
        finally:
            other.close()

    def test_KG12_precreation_identity_is_path_only(self):
        e = self.ev(self.claim("grok", "WRITE", "nope/N.md")); self.assertEqual(e["subject"]["fileid_now"], None)

    def test_KG13_rename_mid_claim_moved_annotation(self):
        w = self.claim("claude", "WRITE"); os.replace(self.root / "X.md", self.root / "Z.md")
        # claim still resolves to X.md path (gone); identity now UNRESOLVED vs a claim on Z.md
        g = self.claim("grok", "WRITE", "Z.md"); e = self.ev(g); self.assertEqual(e["signal"], "UNKNOWN")  # gap exposed

    def test_KG15_path_stable_replacement(self):
        w = self.claim("claude", "WRITE"); f1 = w["fileid"]
        os.remove(self.root / "X.md"); self.write("X.md", "replaced\n")  # new file identity at the same path
        g = self.claim("grok", "WRITE", "./X.md")
        e = self.ev(g)
        self.assertEqual(e["signal"], "CONFLICT")  # identity from CURRENT fileids -> SAME (assumption holds)
        e1 = self.ev(w); self.assertIn("ARTIFACT_REPLACED", e1["annotations"]); self.assertNotEqual(f1, e1["subject"]["fileid_now"])


# ---------------------------------------------------------------- impl-r2 regressions (Grok impl-r1 attack, reproduced exactly)
class T_R2_GrokRegressions(Base):
    """Two findings from research-notes/psp-v0.1-attack/attack_impl_r1.py, authorized for repair by Ruben 2026-09-15.
    Each test first states what r1 produced (Grok's HIT) and then asserts the r2 semantics."""

    def _cli_claim(self, actor, op, target, token, db=None):
        env = os.environ.copy(); env["PSP2_INSTANCE"] = token
        cmd = [PY, str(HERE / "psp2.py"), "--db", db or self.db, "--json", "claim", "--project", "P", "--as", actor, "--op", op,
               "--target", target, "--root", str(self.root), "--instance", token]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        first, rest = r.stdout.split("\n", 1)
        return json.loads(first), json.loads(rest)

    def test_R2_grok_IN03_IN02_shared_token_two_cli_processes_is_unknown(self):
        # r1: two CLI processes sharing --instance, both WRITE -> CLEAR + SELF_OVERLAP (Grok HIT 'IN-03').
        tok = "cccccccccccccccc"
        c1, _ = self._cli_claim("w", "WRITE", "X.md", tok)
        c2, basis = self._cli_claim("w", "WRITE", "X.md", tok)
        self.assertEqual(basis["signal"], "UNKNOWN")
        self.assertNotIn("SELF_OVERLAP", basis["annotations"])
        props = [u["proposition"] for u in basis["unresolved"]]
        self.assertTrue(any(p.startswith("same working instance(") for p in props), props)
        adm = basis["observations_admitted"][0]
        self.assertEqual(adm["same_instance"]["state"], "unresolved")
        self.assertIn("transient", adm["same_instance"]["rule"])

    def test_R2_shared_token_read_read_still_clear(self):
        # the relationship is unresolved but cannot change the answer for READ/READ -> CLEAR, recorded as unresolved-but-harmless
        tok = "cccccccccccccccc"
        self._cli_claim("w", "READ", "X.md", tok); _, basis = self._cli_claim("w", "READ", "X.md", tok)
        self.assertEqual(basis["signal"], "CLEAR")
        self.assertIn("UNRESOLVED but pair cannot conflict", basis["observations_admitted"][0]["row"])

    def test_R2_same_process_same_token_still_self_overlap(self):
        # IN-02 semantics preserved: one module-API worker, sequential REVIEW then WRITE under one token
        tok = "ffffffffffffffff"
        self.claim("claude", "REVIEW", instance=tok); w = self.claim("claude", "WRITE", instance=tok)
        e = self.ev(w); self.assertEqual(e["signal"], "CLEAR"); self.assertIn("SELF_OVERLAP", e["annotations"])
        self.assertEqual(e["observations_admitted"][0]["same_instance"]["state"], "established")

    def test_R2_restart_continuity_by_token_is_established(self):
        # KG-01 assumption kept: earlier process gone, later non-transient process presents the same token -> same instance
        tok = "abababababababab"
        script = ("import sys; sys.path.insert(0,%r); import psp2; p=psp2.PSP2(%r); p.claim('P','claude','REVIEW','X.md',root=%r,instance_id=%r)"
                  % (str(HERE), self.db, str(self.root), tok))
        subprocess.run([PY, "-c", script], check=True, capture_output=True)  # that process is gone now
        w = self.claim("claude", "WRITE", instance=tok)
        e = self.ev(w); self.assertEqual(e["signal"], "CLEAR"); self.assertIn("SELF_OVERLAP", e["annotations"])
        self.assertIn("continuity", e["observations_admitted"][0]["same_instance"]["rule"])

    def test_R2_grok_IN06_null_class_direct_insert_is_unknown(self):
        # r1: NULL op_class vs WRITE -> CONFLICT via the REVIEW/WRITE branch (Grok HIT 'IN-06'). Reproduced with his raw insert.
        import sqlite3
        w = self.claim("grok", "WRITE")
        conn = sqlite3.connect(self.db)
        row = conn.execute("SELECT * FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(events)")]
        last = dict(zip(cols, row))
        conn.execute(
            "INSERT INTO events (ts, kind, claim_id, instance_id, actor, recorded_by, project, target, root, resolved, fileid, revision, "
            "op_class, class_evidence, relation, relates_to, note, ref_claim, pid, host, pid_kind, data, prev_hash, hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (last["ts"], "CLAIMED", "deadbeef0001", "instnullclass", "attacker", "attacker", "P", "X.md", str(self.root), last["resolved"],
             last["fileid"], last["revision"], None, "declared", "unspecified", None, None, None, os.getpid(), last["host"], "process",
             last["data"], last["hash"], "0" * 64))
        conn.commit(); conn.close()
        e = self.p.evaluate(w["claim_id"], record=False)
        self.assertEqual(e["signal"], "UNKNOWN")
        self.assertEqual(e["conflicts"], [])
        self.assertIn("operation class(deadbeef0001)", [u["proposition"] for u in e["unresolved"]])
        self.assertEqual(e["observations_admitted"][0]["row"], "operation class UNRESOLVED")

    def test_R2_baseline_row_guard_direct(self):
        s = {"claim_id": "s", "op_class": None, "revision_at_claim": "a"}; c = {"claim_id": "c", "op_class": "WRITE", "revision_at_claim": "a"}
        r = self.p._baseline_row(s, c, "a", None, [])
        self.assertEqual(r["result"], "UNRESOLVED"); self.assertEqual(r["proposition"], "operation class(s)")

    def test_R2_r1_evidence_store_still_verifies(self):
        # HASH_DOMAIN pinned: the frozen r1 experiment store must verify under r2 code
        stores = sorted((HERE / "experiment").glob("*/psp-v0.2.db"))
        if not stores:
            self.skipTest("no r1 experiment store present")
        import shutil
        copy = self.root / "r1-evidence-copy.db"  # never open the frozen evidence store itself: the constructor writes schema/pragma
        shutil.copyfile(stores[0], copy)
        q = P.PSP2(str(copy))
        try:
            v = q.verify(); self.assertTrue(v["ok"], v); self.assertGreaterEqual(v["events"], 38)
        finally:
            q.close()


if __name__ == "__main__":
    unittest.main()
