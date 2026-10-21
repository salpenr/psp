#!/usr/bin/env python3
"""PSP -- Project Signal Protocol v0.1

Coordination / observability for several actors working on one project.
Answers exactly one question:  who is doing what, to which artifact / revision, and since when?

It is NOT an authority system.  CLAIMED means "this actor reports it is working on this target".
It never means "this actor may".  PSP never blocks a write, never grants, never decides policy.
When it sees a collision it records it and makes it visible; what to do about it is the owner's call.

Storage: one SQLite file (default %LOCALAPPDATA%/psp/psp.db, override with --db or PSP_DB).
The only table is an append-only, hash-chained event log.  Claims are a *view* over events.
Nothing is ever deleted or updated.  A stale claim is released by an explicit RELEASED event that
names who released it and on whose behalf; the history keeps both.

Event vocabulary (v0.1):  CLAIMED  READY  REVIEWING  BREAK_FOUND  SUPERSEDED  RELEASED
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone

VERSION = "0.1"
KINDS = ("CLAIMED", "READY", "REVIEWING", "BREAK_FOUND", "SUPERSEDED", "RELEASED")
MODES = ("READ_ONLY", "WRITE")
GENESIS = "0" * 64

# Exit codes.  2 and 3 are "recorded, but look": the claim exists either way.
EXIT_OK, EXIT_ERROR, EXIT_VISIBLE_CONFLICT, EXIT_HASH_MISMATCH = 0, 1, 2, 3


def default_db() -> str:
    if os.environ.get("PSP_DB"):
        return os.environ["PSP_DB"]
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "psp", "psp.db")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def resolve_target(root: str, target: str) -> str:
    return os.path.normpath(os.path.join(root, target)) if not os.path.isabs(target) else os.path.normpath(target)


# ---------------------------------------------------------------- storage

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  seq         INTEGER PRIMARY KEY AUTOINCREMENT,
  ts          TEXT NOT NULL,
  project     TEXT NOT NULL,
  claim_id    TEXT NOT NULL,
  kind        TEXT NOT NULL,
  actor       TEXT NOT NULL,        -- subject of the event
  recorded_by TEXT NOT NULL,        -- who wrote the event (differs from actor => on-behalf)
  host        TEXT NOT NULL,
  pid         INTEGER NOT NULL,
  operation   TEXT,
  target      TEXT,                 -- as given (relative to root)
  root        TEXT,
  target_hash TEXT,                 -- hash the actor says it is working against
  mode        TEXT,
  note        TEXT,
  ref_claim   TEXT,                 -- another claim this event refers to (conflict / supersession)
  cause_seq   INTEGER,              -- event that caused this one (SUPERSEDED <- READY)
  prev_hash   TEXT NOT NULL,
  hash        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_claim ON events(claim_id);
CREATE INDEX IF NOT EXISTS ix_project_target ON events(project, target);
-- append-only: refuse UPDATE and DELETE at the engine
CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
"""

ROW_FIELDS = ("ts", "project", "claim_id", "kind", "actor", "recorded_by", "host", "pid", "operation",
              "target", "root", "target_hash", "mode", "note", "ref_claim", "cause_seq")


def event_hash(prev_hash: str, seq: int, row: dict) -> str:
    payload = json.dumps({k: row.get(k) for k in ROW_FIELDS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"psp/{VERSION}|{prev_hash}|{seq}|{payload}".encode("utf-8")).hexdigest()


class PSP:
    def __init__(self, db: str | None = None):
        self.path = db or default_db()
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30, isolation_level=None)  # manual transactions
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.host = socket.gethostname()
        self.pid = os.getpid()

    def close(self) -> None:
        self.con.close()

    # -- low level ---------------------------------------------------------
    def _append(self, row: dict) -> int:
        """Must be called inside BEGIN IMMEDIATE."""
        last = self.con.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = last["hash"] if last else GENESIS
        seq = (last["seq"] + 1) if last else 1
        row = dict(row)
        row.setdefault("ts", now_iso())
        row.setdefault("host", self.host)
        row.setdefault("pid", self.pid)
        h = event_hash(prev_hash, seq, row)
        cols = ("seq",) + ROW_FIELDS + ("prev_hash", "hash")
        vals = (seq,) + tuple(row.get(k) for k in ROW_FIELDS) + (prev_hash, h)
        self.con.execute(f"INSERT INTO events ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        return seq

    def _events(self, where: str = "1=1", params: tuple = ()) -> list[sqlite3.Row]:
        return self.con.execute(f"SELECT * FROM events WHERE {where} ORDER BY seq", params).fetchall()

    # -- derived state -----------------------------------------------------
    def claims(self, project: str | None = None, target: str | None = None, active_only: bool = True) -> list[dict]:
        """Claims are derived from events; a claim is active until a RELEASED event names it."""
        rows = self._events()
        by_id: dict[str, dict] = {}
        for r in rows:
            cid = r["claim_id"]
            if r["kind"] == "CLAIMED":
                by_id[cid] = {"claim_id": cid, "seq": r["seq"], "since": r["ts"], "project": r["project"], "actor": r["actor"],
                              "recorded_by": r["recorded_by"], "operation": r["operation"], "target": r["target"], "root": r["root"],
                              "target_hash": r["target_hash"], "mode": r["mode"], "note": r["note"], "last_kind": "CLAIMED",
                              "last_ts": r["ts"], "released": None, "superseded_by": [], "conflicts_at_claim": [], "on_behalf_events": []}
                if r["ref_claim"]:
                    by_id[cid]["conflicts_at_claim"] = r["ref_claim"].split(",")
            elif cid in by_id:
                c = by_id[cid]
                c["last_kind"], c["last_ts"] = r["kind"], r["ts"]
                if r["kind"] == "RELEASED":
                    c["released"] = {"seq": r["seq"], "ts": r["ts"], "by": r["recorded_by"], "note": r["note"]}
                if r["kind"] == "SUPERSEDED":
                    c["superseded_by"].append({"seq": r["seq"], "claim": r["ref_claim"], "new_hash": r["target_hash"], "by": r["recorded_by"]})
                if r["kind"] == "READY":
                    c["ready_hash"] = r["target_hash"]
            if cid in by_id and r["recorded_by"] != r["actor"]:
                by_id[cid]["on_behalf_events"].append({"seq": r["seq"], "kind": r["kind"], "by": r["recorded_by"]})
        out = list(by_id.values())
        if project:
            out = [c for c in out if c["project"] == project]
        if target:
            out = [c for c in out if c["target"] == target]
        if active_only:
            out = [c for c in out if not c["released"]]
        return out

    def annotate(self, claim: dict, others: list[dict] | None = None) -> dict:
        """Attach the things a reader must see: drift, supersession, live conflicts, age, on-behalf."""
        c = dict(claim)
        path = resolve_target(c["root"] or "", c["target"])
        cur = sha256_file(path)
        c["current_hash"] = cur
        flags = []
        if cur is None:
            flags.append("TARGET_MISSING")
        elif c["target_hash"] and cur != c["target_hash"]:
            flags.append("DRIFT")  # the file is no longer what the actor said it was working against
        if c["superseded_by"]:
            flags.append("SUPERSEDED")
        if c["on_behalf_events"]:
            flags.append("ON_BEHALF")
        live = []
        for o in (others if others is not None else self.claims(project=c["project"], target=c["target"])):
            if o["claim_id"] == c["claim_id"] or o["actor"] == c["actor"]:
                continue
            if c["mode"] == "WRITE" or o["mode"] == "WRITE":
                live.append({"claim": o["claim_id"], "actor": o["actor"], "mode": o["mode"]})
        if live:
            flags.append("CONFLICT")
        c["live_conflicts"] = live
        try:
            since = datetime.fromisoformat(c["since"])
            c["age_seconds"] = round((datetime.now(timezone.utc) - since).total_seconds(), 1)
        except ValueError:
            c["age_seconds"] = None
        c["flags"] = flags
        return c

    # -- commands ----------------------------------------------------------
    def claim(self, project: str, actor: str, operation: str, target: str, mode: str, root: str = ".",
              expected_hash: str | None = None, note: str | None = None, recorded_by: str | None = None) -> tuple[dict, int]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        recorded_by = recorded_by or actor
        root = os.path.abspath(root)
        path = resolve_target(root, target)
        actual = sha256_file(path)
        code = EXIT_OK
        notes = [note] if note else []
        target_hash = expected_hash or actual
        if expected_hash and actual and expected_hash != actual:
            # The actor says it is working against X; the file on disk is Y.  Record both, do not pick.
            notes.append(f"HASH_MISMATCH expected={expected_hash} actual={actual}")
            code = EXIT_HASH_MISMATCH
        if actual is None:
            notes.append("TARGET_MISSING_AT_CLAIM")
        claim_id = uuid.uuid4().hex[:12]
        self.con.execute("BEGIN IMMEDIATE")
        try:
            others = [o for o in self.claims(project=project, target=target) if o["actor"] != actor]
            conflicts = [o for o in others if mode == "WRITE" or o["mode"] == "WRITE"]
            if conflicts:
                notes.append("CONFLICT_AT_CLAIM " + ",".join(f"{o['claim_id']}:{o['actor']}:{o['mode']}" for o in conflicts))
                if code == EXIT_OK:
                    code = EXIT_VISIBLE_CONFLICT
            seq = self._append({"project": project, "claim_id": claim_id, "kind": "CLAIMED", "actor": actor, "recorded_by": recorded_by,
                                "operation": operation, "target": target, "root": root, "target_hash": target_hash, "mode": mode,
                                "note": "; ".join(notes) or None, "ref_claim": ",".join(o["claim_id"] for o in conflicts) or None})
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        c = self.annotate(self.get(claim_id))
        c["seq"] = seq
        return c, code

    def get(self, claim_id: str) -> dict:
        for c in self.claims(active_only=False):
            if c["claim_id"] == claim_id:
                return c
        raise KeyError(f"no claim {claim_id}")

    def event(self, claim_id: str, kind: str, recorded_by: str, note: str | None = None, target_hash: str | None = None) -> int:
        """REVIEWING / BREAK_FOUND on an existing claim.  READY and RELEASED have their own methods."""
        if kind not in ("REVIEWING", "BREAK_FOUND"):
            raise ValueError("use ready() / release() for READY / RELEASED; SUPERSEDED is derived")
        c = self.get(claim_id)
        self.con.execute("BEGIN IMMEDIATE")
        try:
            seq = self._append({"project": c["project"], "claim_id": claim_id, "kind": kind, "actor": c["actor"], "recorded_by": recorded_by,
                                "operation": c["operation"], "target": c["target"], "root": c["root"],
                                "target_hash": target_hash or c["target_hash"], "mode": c["mode"], "note": note})
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        return seq

    def ready(self, claim_id: str, recorded_by: str, note: str | None = None) -> tuple[int, list[dict]]:
        """A WRITE claim publishes a new revision.  Every other active claim on the same target whose
        hash is not the new one gets a SUPERSEDED event, caused by this READY.  Their claims stay open:
        a reviewer may knowingly keep working on the old revision, but it is flagged until released."""
        c = self.get(claim_id)
        if c["mode"] != "WRITE":
            raise ValueError("READY is for WRITE claims; a READ_ONLY claim has nothing to publish")
        new_hash = sha256_file(resolve_target(c["root"], c["target"]))
        self.con.execute("BEGIN IMMEDIATE")
        try:
            seq = self._append({"project": c["project"], "claim_id": claim_id, "kind": "READY", "actor": c["actor"], "recorded_by": recorded_by,
                                "operation": c["operation"], "target": c["target"], "root": c["root"], "target_hash": new_hash,
                                "mode": c["mode"], "note": note})
            superseded = []
            for o in self.claims(project=c["project"], target=c["target"]):
                if o["claim_id"] == claim_id or o["target_hash"] == new_hash:
                    continue
                self._append({"project": o["project"], "claim_id": o["claim_id"], "kind": "SUPERSEDED", "actor": o["actor"], "recorded_by": recorded_by,
                              "operation": o["operation"], "target": o["target"], "root": o["root"], "target_hash": new_hash, "mode": o["mode"],
                              "note": f"revision {o['target_hash']} superseded by {new_hash} (READY seq {seq} by {c['actor']})",
                              "ref_claim": claim_id, "cause_seq": seq})
                superseded.append(o)
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        return seq, superseded

    def release(self, claim_id: str, recorded_by: str, note: str | None = None) -> int:
        c = self.get(claim_id)
        if c["released"]:
            raise ValueError(f"claim {claim_id} already released at seq {c['released']['seq']}")
        if recorded_by != c["actor"]:
            note = f"ON_BEHALF_OF {c['actor']} by {recorded_by}" + (f": {note}" if note else "")
        self.con.execute("BEGIN IMMEDIATE")
        try:
            seq = self._append({"project": c["project"], "claim_id": claim_id, "kind": "RELEASED", "actor": c["actor"], "recorded_by": recorded_by,
                                "operation": c["operation"], "target": c["target"], "root": c["root"], "target_hash": c["target_hash"],
                                "mode": c["mode"], "note": note})
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        return seq

    def status(self, project: str | None = None, target: str | None = None) -> dict:
        active = self.claims(project=project, target=target)
        ann = []
        for c in active:
            ann.append(self.annotate(c, [o for o in active if o["target"] == c["target"] and o["project"] == c["project"]]))
        collisions = sorted({f for c in ann for f in c["flags"] if f in ("CONFLICT", "DRIFT", "SUPERSEDED", "TARGET_MISSING")})
        return {"psp_version": VERSION, "db": self.path, "checked_at": now_iso(), "active_claims": ann,
                "clean": not collisions, "visible_issues": collisions}

    def history(self, claim_id: str | None = None, target: str | None = None, project: str | None = None) -> list[dict]:
        where, params = [], []
        if claim_id:
            where.append("claim_id=?"); params.append(claim_id)
        if target:
            where.append("target=?"); params.append(target)
        if project:
            where.append("project=?"); params.append(project)
        rows = self._events(" AND ".join(where) or "1=1", tuple(params))
        return [dict(r) for r in rows]

    def verify(self) -> dict:
        """Recompute the chain.  Any edited, removed, or reordered row breaks it at that seq."""
        prev, expected_seq = GENESIS, 1
        for r in self._events():
            if r["seq"] != expected_seq:
                return {"ok": False, "at_seq": r["seq"], "reason": f"gap: expected seq {expected_seq}"}
            if r["prev_hash"] != prev:
                return {"ok": False, "at_seq": r["seq"], "reason": "prev_hash does not match previous row"}
            if event_hash(prev, r["seq"], dict(r)) != r["hash"]:
                return {"ok": False, "at_seq": r["seq"], "reason": "row hash does not match row content"}
            prev, expected_seq = r["hash"], r["seq"] + 1
        return {"ok": True, "events": expected_seq - 1, "head": prev}

    def who(self, project: str | None = None) -> dict:
        out: dict[str, list] = {}
        for c in self.status(project)["active_claims"]:
            out.setdefault(c["actor"], []).append({k: c[k] for k in ("claim_id", "operation", "target", "mode", "since", "last_kind", "flags")})
        return out


# ---------------------------------------------------------------- CLI

def _print(obj, as_json: bool):
    if as_json:
        print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))
        return
    if isinstance(obj, dict) and "active_claims" in obj:
        print(f"PSP {obj['psp_version']}  db={obj['db']}  clean={obj['clean']}  issues={obj['visible_issues']}")
        for c in obj["active_claims"]:
            ch = (c["target_hash"] or "-")[:12]
            cur = (c["current_hash"] or "MISSING")[:12]
            fl = ",".join(c["flags"]) or "-"
            print(f"  {c['claim_id']}  {c['actor']:<10} {c['mode']:<9} {c['operation']:<22} {c['project']}/{c['target']}  "
                  f"claimed={ch} now={cur}  age={c['age_seconds']}s  last={c['last_kind']}  flags={fl}")
            for lc in c["live_conflicts"]:
                print(f"      conflict: {lc['claim']} {lc['actor']} {lc['mode']}")
            for s in c["superseded_by"]:
                print(f"      superseded: by claim {s['claim']} -> {str(s['new_hash'])[:12]} (seq {s['seq']}, recorded by {s['by']})")
        return
    if isinstance(obj, list):
        for r in obj:
            if "kind" in r:
                ob = "" if r["recorded_by"] == r["actor"] else f"  [recorded_by={r['recorded_by']}]"
                print(f"{r['seq']:>5} {r['ts']}  {r['kind']:<11} {r['claim_id']}  {r['actor']:<10} {r['mode'] or '-':<9} "
                      f"{r['project']}/{r['target']}  {str(r['target_hash'] or '-')[:12]}{ob}  {r['note'] or ''}")
            else:
                print(r)
        return
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="psp", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None, help="sqlite path (default %%LOCALAPPDATA%%/psp/psp.db or $PSP_DB)")
    ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("claim", help="report that ACTOR is working on TARGET")
    p.add_argument("--project", required=True); p.add_argument("--as", dest="actor", required=True)
    p.add_argument("--op", required=True, help="operation / activity, free text"); p.add_argument("--target", required=True)
    p.add_argument("--mode", choices=MODES, required=True); p.add_argument("--root", default=".")
    p.add_argument("--hash", default=None, help="revision the actor believes it is working against (else hashed from disk)")
    p.add_argument("--note", default=None); p.add_argument("--recorded-by", default=None, help="who is writing this event, if not the actor")

    p = sub.add_parser("event", help="REVIEWING or BREAK_FOUND on a claim")
    p.add_argument("--claim", required=True); p.add_argument("--kind", choices=("REVIEWING", "BREAK_FOUND"), required=True)
    p.add_argument("--as", dest="actor", required=True); p.add_argument("--note", default=None); p.add_argument("--hash", default=None)

    p = sub.add_parser("ready", help="WRITE claim publishes the current file revision; others on the old revision get SUPERSEDED")
    p.add_argument("--claim", required=True); p.add_argument("--as", dest="actor", required=True); p.add_argument("--note", default=None)

    p = sub.add_parser("release", help="close a claim (on behalf of another actor is allowed and recorded as such)")
    p.add_argument("--claim", required=True); p.add_argument("--as", dest="actor", required=True); p.add_argument("--note", default=None)

    p = sub.add_parser("status", help="active claims with DRIFT / SUPERSEDED / CONFLICT / age")
    p.add_argument("--project", default=None); p.add_argument("--target", default=None)

    p = sub.add_parser("who", help="active claims grouped by actor"); p.add_argument("--project", default=None)

    p = sub.add_parser("history", help="raw events"); p.add_argument("--claim", default=None); p.add_argument("--target", default=None); p.add_argument("--project", default=None)

    sub.add_parser("verify", help="recompute the hash chain")

    p = sub.add_parser("check", help="exit 0 if TARGET on disk still has HASH, else 2")
    p.add_argument("--target", required=True); p.add_argument("--hash", required=True); p.add_argument("--root", default=".")

    a = ap.parse_args(argv)
    psp = PSP(a.db)
    try:
        return _dispatch(psp, a)
    finally:
        psp.close()


def _dispatch(psp: "PSP", a) -> int:
    try:
        if a.cmd == "claim":
            c, code = psp.claim(a.project, a.actor, a.op, a.target, a.mode, root=a.root, expected_hash=a.hash, note=a.note, recorded_by=a.recorded_by)
            _print(c if a.json else {"claim_id": c["claim_id"], "seq": c["seq"], "target_hash": c["target_hash"], "flags": c["flags"],
                                     "live_conflicts": c["live_conflicts"], "note": c["note"], "exit": code}, a.json or True)
            return code
        if a.cmd == "event":
            seq = psp.event(a.claim, a.kind, a.actor, note=a.note, target_hash=a.hash); print(json.dumps({"seq": seq})); return EXIT_OK
        if a.cmd == "ready":
            seq, sup = psp.ready(a.claim, a.actor, note=a.note)
            print(json.dumps({"seq": seq, "superseded": [{"claim": s["claim_id"], "actor": s["actor"], "old_hash": s["target_hash"]} for s in sup]}, indent=2))
            return EXIT_VISIBLE_CONFLICT if sup else EXIT_OK
        if a.cmd == "release":
            seq = psp.release(a.claim, a.actor, note=a.note); print(json.dumps({"seq": seq})); return EXIT_OK
        if a.cmd == "status":
            st = psp.status(a.project, a.target); _print(st, a.json); return EXIT_OK if st["clean"] else EXIT_VISIBLE_CONFLICT
        if a.cmd == "who":
            _print(psp.who(a.project), True); return EXIT_OK
        if a.cmd == "history":
            _print(psp.history(a.claim, a.target, a.project), a.json); return EXIT_OK
        if a.cmd == "verify":
            v = psp.verify(); _print(v, True); return EXIT_OK if v["ok"] else EXIT_ERROR
        if a.cmd == "check":
            cur = sha256_file(resolve_target(os.path.abspath(a.root), a.target))
            print(json.dumps({"target": a.target, "expected": a.hash, "actual": cur, "same": cur == a.hash}))
            return EXIT_OK if cur == a.hash else EXIT_VISIBLE_CONFLICT
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
