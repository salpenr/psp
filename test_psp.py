"""PSP v0.1 tests.  stdlib unittest only.  Run:  python -m unittest -v test_psp"""
import io
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout

import psp as P


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.db = os.path.join(self.root, "psp.db")
        self.target = "MAP.md"
        self.write("version 1\n")
        self.p = P.PSP(self.db)

    def tearDown(self):
        self.p.con.close()
        self.tmp.cleanup()

    def write(self, text):
        with open(os.path.join(self.root, self.target), "w", encoding="utf-8") as f:
            f.write(text)

    def claim(self, actor, mode, op="review", **kw):
        return self.p.claim("proj", actor, op, self.target, mode, root=self.root, **kw)


class ReadOnlyCompatibility(Base):
    def test_two_read_only_claims_do_not_conflict(self):
        c1, code1 = self.claim("claude", "READ_ONLY")
        c2, code2 = self.claim("grok", "READ_ONLY")
        self.assertEqual((code1, code2), (P.EXIT_OK, P.EXIT_OK))
        self.assertEqual(c1["target_hash"], c2["target_hash"])
        st = self.p.status("proj")
        self.assertTrue(st["clean"])
        self.assertEqual(len(st["active_claims"]), 2)
        for c in st["active_claims"]:
            self.assertEqual(c["flags"], [])


class WriteConflicts(Base):
    def test_write_after_read_only_is_visible_on_both_sides(self):
        r, _ = self.claim("grok", "READ_ONLY")
        w, code = self.claim("claude", "WRITE", op="revise")
        self.assertEqual(code, P.EXIT_VISIBLE_CONFLICT)
        self.assertIn("CONFLICT_AT_CLAIM", w["note"])
        self.assertIn(r["claim_id"], w["note"])
        st = self.p.status("proj")
        self.assertFalse(st["clean"])
        by = {c["claim_id"]: c for c in st["active_claims"]}
        self.assertIn("CONFLICT", by[w["claim_id"]]["flags"])
        self.assertIn("CONFLICT", by[r["claim_id"]]["flags"])  # the reviewer sees it too
        self.assertEqual(by[r["claim_id"]]["live_conflicts"][0]["actor"], "claude")

    def test_two_writers_both_recorded_second_flagged(self):
        w1, code1 = self.claim("claude", "WRITE")
        w2, code2 = self.claim("grok", "WRITE")
        self.assertEqual(code1, P.EXIT_OK)
        self.assertEqual(code2, P.EXIT_VISIBLE_CONFLICT)
        self.assertEqual(len(self.p.claims("proj")), 2)  # nothing refused, nothing hidden
        self.assertIn(w1["claim_id"], w2["conflicts_at_claim"])
        st = self.p.status("proj")
        self.assertEqual(st["visible_issues"], ["CONFLICT"])

    def test_same_actor_twice_is_not_a_conflict_with_itself(self):
        self.claim("claude", "WRITE")
        _, code = self.claim("claude", "WRITE", op="second-pass")
        self.assertEqual(code, P.EXIT_OK)

    def test_collision_stays_in_history_after_release(self):
        r, _ = self.claim("grok", "READ_ONLY")
        w, _ = self.claim("claude", "WRITE")
        self.p.release(w["claim_id"], "claude", "done")
        st = self.p.status("proj")
        self.assertTrue(st["clean"])  # live state is clean now
        h = self.p.history(claim_id=w["claim_id"])
        self.assertIn("CONFLICT_AT_CLAIM", h[0]["note"])  # but the record says what happened


class Drift(Base):
    def test_target_changed_after_claim_shows_drift(self):
        c, _ = self.claim("grok", "READ_ONLY")
        self.write("version 2\n")
        st = self.p.status("proj")
        self.assertIn("DRIFT", st["active_claims"][0]["flags"])
        self.assertNotEqual(st["active_claims"][0]["current_hash"], c["target_hash"])
        self.assertFalse(st["clean"])

    def test_check_command_exit_codes(self):
        c, _ = self.claim("grok", "READ_ONLY")
        argv = ["--db", self.db, "check", "--root", self.root, "--target", self.target, "--hash", c["target_hash"]]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(P.main(argv), P.EXIT_OK)
            self.write("version 2\n")
            self.assertEqual(P.main(argv), P.EXIT_VISIBLE_CONFLICT)

    def test_missing_target_is_visible_not_an_error(self):
        c, code = self.p.claim("proj", "claude", "write-new", "NEW.md", "WRITE", root=self.root)
        self.assertEqual(code, P.EXIT_OK)
        self.assertIn("TARGET_MISSING_AT_CLAIM", c["note"])
        self.assertIn("TARGET_MISSING", c["flags"])


class HashMismatch(Base):
    def test_actor_believes_hash_a_file_is_hash_b(self):
        c, code = self.claim("grok", "READ_ONLY", expected_hash="a" * 64)
        self.assertEqual(code, P.EXIT_HASH_MISMATCH)
        self.assertIn("HASH_MISMATCH", c["note"])
        self.assertEqual(c["target_hash"], "a" * 64)  # what the actor said, kept verbatim
        self.assertIn(c["current_hash"], c["note"])  # what the disk said, kept beside it
        self.assertIn("DRIFT", c["flags"])  # and it stays visible in status


class Supersession(Base):
    def test_ready_marks_reviewers_of_old_revision_superseded(self):
        w, _ = self.claim("claude", "WRITE", op="revise")
        r, _ = self.claim("grok", "READ_ONLY", op="attack")
        self.write("version 2\n")
        seq, sup = self.p.ready(w["claim_id"], "claude", "v2 published")
        self.assertEqual([s["claim_id"] for s in sup], [r["claim_id"]])
        h = self.p.history(claim_id=r["claim_id"])
        self.assertEqual([e["kind"] for e in h], ["CLAIMED", "SUPERSEDED"])
        self.assertEqual(h[1]["cause_seq"], seq)
        self.assertEqual(h[1]["ref_claim"], w["claim_id"])
        self.assertEqual(h[1]["recorded_by"], "claude")  # the writer caused it; the reviewer is the subject
        self.assertEqual(h[1]["actor"], "grok")
        st = {c["claim_id"]: c for c in self.p.status("proj")["active_claims"]}
        self.assertIn("SUPERSEDED", st[r["claim_id"]]["flags"])
        self.assertIn("DRIFT", st[r["claim_id"]]["flags"])
        self.assertIsNone(st[r["claim_id"]]["released"])  # still open: reviewer decides what to do

    def test_ready_does_not_supersede_claims_already_on_new_hash(self):
        w, _ = self.claim("claude", "WRITE")
        self.write("version 2\n")
        r, _ = self.claim("grok", "READ_ONLY")  # claimed after the change, hash == new
        _, sup = self.p.ready(w["claim_id"], "claude")
        self.assertEqual(sup, [])

    def test_ready_on_read_only_refused(self):
        r, _ = self.claim("grok", "READ_ONLY")
        with self.assertRaises(ValueError):
            self.p.ready(r["claim_id"], "grok")


class ReleaseAndStale(Base):
    def test_release_on_behalf_is_recorded_as_such(self):
        c, _ = self.claim("claude", "WRITE")
        seq = self.p.release(c["claim_id"], "grok", "claude's window crashed 18:01")
        h = self.p.history(claim_id=c["claim_id"])[-1]
        self.assertEqual((h["kind"], h["actor"], h["recorded_by"]), ("RELEASED", "claude", "grok"))
        self.assertTrue(h["note"].startswith("ON_BEHALF_OF claude by grok"))
        self.assertEqual(self.p.claims("proj"), [])
        self.assertIn("ON_BEHALF", self.p.annotate(self.p.get(c["claim_id"]))["flags"])

    def test_double_release_refused_history_unchanged(self):
        c, _ = self.claim("claude", "WRITE")
        self.p.release(c["claim_id"], "claude")
        n = len(self.p.history())
        with self.assertRaises(ValueError):
            self.p.release(c["claim_id"], "claude")
        self.assertEqual(len(self.p.history()), n)

    def test_stale_claim_never_expires_by_itself_and_shows_age(self):
        c, _ = self.claim("claude", "WRITE")
        time.sleep(0.05)
        st = self.p.status("proj")
        self.assertEqual(len(st["active_claims"]), 1)
        self.assertGreater(st["active_claims"][0]["age_seconds"], 0)

    def test_claim_recorded_by_someone_else_is_flagged(self):
        c, _ = self.claim("claude", "READ_ONLY", recorded_by="ruben")
        self.assertIn("ON_BEHALF", c["flags"])
        self.assertEqual(self.p.history()[0]["recorded_by"], "ruben")


class Chain(Base):
    def test_verify_ok_and_ordering(self):
        a, _ = self.claim("claude", "READ_ONLY")
        b, _ = self.claim("grok", "READ_ONLY")
        self.p.event(a["claim_id"], "REVIEWING", "claude")
        self.p.event(b["claim_id"], "BREAK_FOUND", "grok", "R6 excludes B")
        self.p.release(a["claim_id"], "claude")
        v = self.p.verify()
        self.assertTrue(v["ok"], v)
        seqs = [e["seq"] for e in self.p.history()]
        self.assertEqual(seqs, list(range(1, 6)))
        self.assertEqual([e["kind"] for e in self.p.history()], ["CLAIMED", "CLAIMED", "REVIEWING", "BREAK_FOUND", "RELEASED"])

    def test_engine_refuses_update_and_delete(self):
        self.claim("claude", "READ_ONLY")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p.con.execute("UPDATE events SET note='x' WHERE seq=1")
        with self.assertRaises(sqlite3.IntegrityError):
            self.p.con.execute("DELETE FROM events WHERE seq=1")

    def test_tamper_after_dropping_triggers_is_caught(self):
        self.claim("claude", "READ_ONLY")
        self.claim("grok", "WRITE")
        self.claim("gpt", "READ_ONLY")
        raw = sqlite3.connect(self.db)
        raw.executescript("DROP TRIGGER no_update; DROP TRIGGER no_delete;")
        raw.execute("UPDATE events SET actor='claude' WHERE seq=2")  # make grok's WRITE look like claude's
        raw.commit(); raw.close()
        v = self.p.verify()
        self.assertFalse(v["ok"]); self.assertEqual(v["at_seq"], 2)

    def test_deleted_row_leaves_a_gap(self):
        self.claim("claude", "READ_ONLY"); self.claim("grok", "WRITE"); self.claim("gpt", "READ_ONLY")
        raw = sqlite3.connect(self.db)
        raw.executescript("DROP TRIGGER no_update; DROP TRIGGER no_delete; DELETE FROM events WHERE seq=2;")
        raw.commit(); raw.close()
        v = self.p.verify()
        self.assertFalse(v["ok"]); self.assertEqual(v["at_seq"], 3)


class Concurrency(Base):
    def test_simultaneous_writers_all_recorded_one_unflagged(self):
        results, errors = [], []

        def worker(i):
            try:
                q = P.PSP(self.db)
                c, code = q.claim("proj", f"actor{i}", "edit", self.target, "WRITE", root=self.root)
                results.append((c["claim_id"], code, c["conflicts_at_claim"]))
                q.con.close()
            except Exception as e:  # pragma: no cover
                errors.append(repr(e))

        ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)
        self.assertEqual(sum(1 for _, code, _ in results if code == P.EXIT_OK), 1)  # exactly one saw an empty field
        self.assertEqual(len(self.p.claims("proj")), 8)
        self.assertTrue(self.p.verify()["ok"])


class NotAuthority(Base):
    def test_no_authority_vocabulary_in_data_model(self):
        for k in P.KINDS + P.ROW_FIELDS:
            self.assertNotIn("authoriz", k.lower())
            self.assertNotIn("owner", k.lower())
            self.assertNotIn("permit", k.lower())
        c, _ = self.claim("claude", "WRITE")
        self.write("version 2\n")
        st = self.p.status("proj")
        for key in st["active_claims"][0].keys():
            self.assertNotIn("authoriz", key.lower())

    def test_write_is_never_blocked_only_seen(self):
        self.claim("grok", "READ_ONLY")
        w, code = self.claim("claude", "WRITE")
        self.assertEqual(code, P.EXIT_VISIBLE_CONFLICT)
        self.assertIsNotNone(self.p.get(w["claim_id"]))  # recorded despite the conflict
        self.write("version 2\n")  # nothing in PSP prevented this write; PSP only shows it happened
        self.assertIn("DRIFT", self.p.status("proj")["active_claims"][0]["flags"])


class CLI(Base):
    def test_cli_roundtrip(self):
        base = ["--db", self.db]
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(P.main(base + ["claim", "--project", "proj", "--as", "grok", "--op", "attack", "--target", self.target,
                                            "--mode", "READ_ONLY", "--root", self.root]), P.EXIT_OK)
            self.assertEqual(P.main(base + ["claim", "--project", "proj", "--as", "claude", "--op", "revise", "--target", self.target,
                                            "--mode", "WRITE", "--root", self.root]), P.EXIT_VISIBLE_CONFLICT)
            self.assertEqual(P.main(base + ["status", "--project", "proj"]), P.EXIT_VISIBLE_CONFLICT)
            self.assertEqual(P.main(base + ["verify"]), P.EXIT_OK)
            self.assertEqual(P.main(base + ["history"]), P.EXIT_OK)
            self.assertEqual(P.main(base + ["who"]), P.EXIT_OK)
        text = out.getvalue()
        self.assertIn("CONFLICT", text)
        self.assertIn('"ok": true', text)


if __name__ == "__main__":
    unittest.main()
