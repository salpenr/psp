#!/usr/bin/env python3
"""PSP v0.2 -- Project Signal Protocol, experimental implementation of frozen design r1.

Implements, and only implements, the twelve mechanisms in PSP-v0.2-DESIGN-MAPPING.md against the frozen
requirements baseline (Draft 5 + owner's §23 sentence).  Three signals: CLEAR / CONFLICT / UNKNOWN.
Observational only: nothing here blocks, expires, terminates, or authorizes anything.

  M-01 store = discovery domain (enumerate every claim in the store before any identity question)
  M-02 working instance = PSP-minted token presented on later self-state actions
  M-03 artifact identity = resolved canonical path + file identity, SAME/DISTINCT with accept+reject rules
  M-04 revision = content hash at claim / READY / evaluation; transitions = READY records
  M-05 operation class = declared intent (provisional) then observed WRITE via own READY
  M-06 discovery table: supporter and defeater evidence per proposition, all in one store + two host probes
  M-07 lifecycle LIVE / INACTIVE / UNRESOLVED with three defeaters; no auto-expiry
  M-08 host-local process-existence probe (sends no signal)
  M-09 evaluation: baseline rows, precedence, annotations; every evaluation appended as an event
  M-10 full basis JSON + one summary line; exit 0 always; --enforce-exit is opt-in and labeled
  M-11 relation tag -> INTENDED_OVERLAP on non-conflict rows only
  M-12 metrics from the log + operator verdicts

Storage: one SQLite file (default %LOCALAPPDATA%/psp/psp-v0.2.db or $PSP2_DB), one append-only hash-chained
event table.  Claims, instances, and evaluations are views over events.  Nothing is updated or deleted.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import socket
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

VERSION = "0.2-r2"
HASH_DOMAIN = "psp/0.2-r1"  # pinned: r2 must still verify stores written by r1 (evidence); do not bump with VERSION
PROFILE = "psp-v0.2-baseline"
GENESIS = "0" * 64
CLASSES = ("READ", "WRITE", "REVIEW")
RELATIONS = ("independent-attack", "independent-reproduction", "dependent-review", "complementary", "unspecified")
KINDS = ("CLAIMED", "READY", "RELEASED", "OPERATOR_RELEASE", "ATTEMPTED_RELEASE_OTHER", "ATTEMPT_ON_INACTIVE",
         "NOTE", "RECLASSIFIED", "EVALUATED", "VERDICT", "INTERVENTION")

# ---------------------------------------------------------------- M-06 discovery table (shipped constant)
DISCOVERY_TABLE = {
    "LIVE":        {"support": ["CLAIMED (own instance token)"],
                    "defeat":  ["RELEASED (own token)", "OPERATOR_RELEASE (operator class)", "instance process gone (host probe) -> UNRESOLVED"]},
    "INACTIVE":    {"support": ["RELEASED (own token)", "OPERATOR_RELEASE"], "defeat": ["absence of both -> not INACTIVE"]},
    "SAME":        {"support": ["file identity equal (stat)", "resolved path equal when neither exists (path-only)"],
                    "defeat":  ["file identity differs"]},
    "DISTINCT":    {"support": ["file identity differs (both exist)", "resolved path differs when neither exists (path-only)"],
                    "defeat":  ["file identity equal"]},
    "CLASS":       {"support": ["declared intent (self-state, provisional)", "own READY with changed hash -> WRITE (observed)"],
                    "defeat":  ["observed WRITE over declared READ/REVIEW"]},
    "REVISION":    {"support": ["sha256 at claim", "sha256 at READY", "sha256 at evaluation"],
                    "defeat":  ["current hash differs from bound hash"]},
    "INSTANCE":    {"support": ["distinct PSP-minted tokens"], "defeat": ["same token used concurrently from two live pids -> TOKEN_SHARED"]},
}
EVENT_KINDS_WITH_ROWS = {"CLAIMED": "LIVE", "READY": "REVISION", "RELEASED": "INACTIVE", "OPERATOR_RELEASE": "INACTIVE",
                         "RECLASSIFIED": "CLASS", "ATTEMPTED_RELEASE_OTHER": "LIVE", "ATTEMPT_ON_INACTIVE": "INACTIVE",
                         "NOTE": "LIVE", "EVALUATED": "REVISION", "VERDICT": "LIVE", "INTERVENTION": "LIVE"}

# ---------------------------------------------------------------- helpers

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_db() -> str:
    if os.environ.get("PSP2_DB"):
        return os.environ["PSP2_DB"]
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "psp", "psp-v0.2.db")


def sha256_file(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


# ---------------------------------------------------------------- M-03 artifact identity

def resolve_ref(root: str, target: str) -> str:
    p = target if os.path.isabs(target) else os.path.join(root, target)
    try:
        return os.path.normcase(os.path.realpath(p))
    except OSError:
        return os.path.normcase(os.path.abspath(p))


def file_identity(resolved: str) -> str | None:
    """'dev:ino' when the filesystem supplies a file identity; None when the file is absent or identity unavailable."""
    try:
        st = os.stat(resolved)
    except OSError:
        return None
    if st.st_ino == 0:
        return None
    return f"{st.st_dev}:{st.st_ino}"


def identity_relation(a_resolved: str, a_fid: str | None, b_resolved: str, b_fid: str | None) -> dict:
    """SAME / DISTINCT / UNRESOLVED with the rule that fired.  Strings never decide (baseline §12)."""
    a_exists, b_exists = a_fid is not None, b_fid is not None
    if a_exists and b_exists:
        if a_fid == b_fid:
            return {"relation": "SAME", "evidence_class": "protocol-observation", "rule": "file identity equal"}
        return {"relation": "DISTINCT", "evidence_class": "protocol-observation", "rule": "file identity differs"}
    if not a_exists and not b_exists:
        if a_resolved == b_resolved:
            return {"relation": "SAME", "evidence_class": "path-only", "rule": "neither exists; resolved paths equal (KG-12)"}
        return {"relation": "DISTINCT", "evidence_class": "path-only", "rule": "neither exists; resolved paths differ (KG-12)"}
    return {"relation": "UNRESOLVED", "evidence_class": None, "rule": "exactly one reference resolves to an existing file"}


# ---------------------------------------------------------------- M-08 process probe (no signal sent)

def process_state(host: str, pid: int) -> str:
    """'alive' | 'gone' | 'unavailable'.  Host-local; never terminates anything."""
    if host != socket.gethostname():
        return "unavailable"
    if pid is None:
        return "unavailable"
    if sys.platform == "win32":
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            err = ctypes.get_last_error() or k32.GetLastError()
            return "alive" if err == 5 else "gone"  # 5 = access denied: exists; 87 = invalid parameter: no such pid
        try:
            code = ctypes.c_ulong()
            if k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return "alive" if code.value == 259 else "gone"  # 259 = STILL_ACTIVE
            return "unavailable"
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return "alive"
    except ProcessLookupError:
        return "gone"
    except PermissionError:
        return "alive"
    except OSError:
        return "unavailable"


# ---------------------------------------------------------------- storage (append-only, hash-chained)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, kind TEXT NOT NULL,
  claim_id TEXT, instance_id TEXT, actor TEXT, recorded_by TEXT, host TEXT, pid INTEGER,
  project TEXT, target TEXT, root TEXT, resolved TEXT, fileid TEXT, revision TEXT,
  op_class TEXT, class_evidence TEXT, relation TEXT, relates_to TEXT, note TEXT, ref_claim TEXT,
  pid_kind TEXT, data TEXT, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_claim ON events(claim_id);
CREATE INDEX IF NOT EXISTS ix_kind ON events(kind);
CREATE TRIGGER IF NOT EXISTS no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'events is append-only'); END;
PRAGMA user_version = 2;
"""
ROW_FIELDS = ("ts", "kind", "claim_id", "instance_id", "actor", "recorded_by", "host", "pid", "project", "target", "root",
              "resolved", "fileid", "revision", "op_class", "class_evidence", "relation", "relates_to", "note", "ref_claim", "pid_kind", "data")


def event_hash(prev_hash: str, seq: int, row: dict) -> str:
    payload = json.dumps({k: row.get(k) for k in ROW_FIELDS}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(f"{HASH_DOMAIN}|{prev_hash}|{seq}|{payload}".encode("utf-8")).hexdigest()


class PSP2:
    def __init__(self, db: str | None = None, pid: int | None = None, pid_kind: str = "process"):
        """pid_kind: 'process' = this process is the worker (probe active); 'transient' = a short-lived CLI wrote on the
        worker's behalf (probe reports unavailable, IN-01); 'declared' = the worker supplied its own long-lived pid."""
        self.path = os.path.abspath(db or default_db())
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.host = socket.gethostname()
        self.pid = int(pid) if pid else os.getpid()
        self.pid_kind = pid_kind

    def close(self) -> None:
        self.con.close()

    # -- log ------------------------------------------------------------------------------------
    def _append(self, row: dict) -> int:
        last = self.con.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last["hash"] if last else GENESIS
        seq = (last["seq"] + 1) if last else 1
        row = dict(row); row.setdefault("ts", now_iso()); row.setdefault("host", self.host); row.setdefault("pid", self.pid)
        row.setdefault("pid_kind", self.pid_kind)
        if isinstance(row.get("data"), (dict, list)):
            row["data"] = json.dumps(row["data"], ensure_ascii=False, sort_keys=True, default=str)
        h = event_hash(prev, seq, row)
        cols = ("seq",) + ROW_FIELDS + ("prev_hash", "hash")
        vals = (seq,) + tuple(row.get(k) for k in ROW_FIELDS) + (prev, h)
        self.con.execute(f"INSERT INTO events ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        return seq

    def _tx(self, fn):
        self.con.execute("BEGIN IMMEDIATE")
        try:
            out = fn(); self.con.execute("COMMIT"); return out
        except Exception:
            self.con.execute("ROLLBACK"); raise

    def events(self, where: str = "1=1", params: tuple = ()) -> list[dict]:
        return [dict(r) for r in self.con.execute(f"SELECT * FROM events WHERE {where} ORDER BY seq", params)]

    def verify(self) -> dict:
        prev, expect = GENESIS, 1
        for r in self.events():
            if r["seq"] != expect:
                return {"ok": False, "at_seq": r["seq"], "reason": "gap"}
            if r["prev_hash"] != prev or event_hash(prev, r["seq"], r) != r["hash"]:
                return {"ok": False, "at_seq": r["seq"], "reason": "chain mismatch"}
            prev, expect = r["hash"], r["seq"] + 1
        return {"ok": True, "events": expect - 1, "head": prev}

    # -- views ----------------------------------------------------------------------------------
    def claims(self) -> dict[str, dict]:
        """Every claim derived from events (M-09: views, never mutable rows)."""
        out: dict[str, dict] = {}
        for r in self.events("claim_id IS NOT NULL"):
            cid = r["claim_id"]
            if r["kind"] == "CLAIMED":
                out[cid] = {"claim_id": cid, "seq": r["seq"], "since": r["ts"], "instance_id": r["instance_id"], "actor": r["actor"],
                            "recorded_by": r["recorded_by"], "project": r["project"], "target": r["target"], "root": r["root"],
                            "resolved": r["resolved"], "fileid_at_claim": r["fileid"], "revision_at_claim": r["revision"],
                            "op_class": r["op_class"], "class_evidence": r["class_evidence"], "relation": r["relation"],
                            "relates_to": r["relates_to"], "released": None, "ready": [], "pids": {(r["host"], r["pid"], r["pid_kind"] or "process")},
                            "last_event": r["kind"], "notes": []}
                continue
            c = out.get(cid)
            if not c:
                continue
            if r["kind"] in ("READY", "NOTE", "RELEASED", "RECLASSIFIED") and r["instance_id"] == c["instance_id"]:
                c["pids"].add((r["host"], r["pid"], r["pid_kind"] or "process"))
            if r["kind"] == "RELEASED":
                c["released"] = {"seq": r["seq"], "ts": r["ts"], "evidence_class": "self-state", "by": r["recorded_by"]}
            elif r["kind"] == "OPERATOR_RELEASE":
                c["released"] = {"seq": r["seq"], "ts": r["ts"], "evidence_class": "operator", "by": r["recorded_by"]}
            elif r["kind"] == "READY":
                c["ready"].append({"seq": r["seq"], "ts": r["ts"], "revision": r["revision"]})
            elif r["kind"] == "RECLASSIFIED":
                c["op_class"], c["class_evidence"] = r["op_class"], r["class_evidence"]
            elif r["kind"] == "NOTE":
                c["notes"].append({"seq": r["seq"], "note": r["note"]})
            c["last_event"] = r["kind"]
        return out

    def get(self, claim_id: str) -> dict:
        c = self.claims().get(claim_id)
        if not c:
            raise KeyError(f"no claim {claim_id}")
        return c

    def instance_pids(self, instance_id: str) -> list[tuple[str, int, str]]:
        pids = []
        for r in self.events("instance_id = ? AND kind IN ('CLAIMED','READY','NOTE','RELEASED','RECLASSIFIED')", (instance_id,)):
            key = (r["host"], r["pid"], r["pid_kind"] or "process")
            if key not in pids:
                pids.append(key)
        return pids

    # -- M-07 lifecycle -------------------------------------------------------------------------
    def lifecycle(self, c: dict) -> dict:
        if c["released"]:
            return {"state": "INACTIVE", "evidence": c["released"], "annotations": []}
        pids = self.instance_pids(c["instance_id"])
        host, pid, kind = pids[-1]  # latest pid that presented the token
        st = "unavailable" if kind == "transient" else process_state(host, pid)  # IN-01: transient CLI pids are not probed
        ann = []
        if st == "gone":
            ann.append("INSTANCE_PROCESS_GONE")
            return {"state": "UNRESOLVED", "evidence": {"rule": "CLAIMED, no RELEASE, instance process gone", "host": host, "pid": pid,
                                                        "pid_kind": kind, "age_seconds": self._age(c["since"])}, "annotations": ann}
        if st == "unavailable":
            ann.append("PROBE_UNAVAILABLE")
        # TOKEN_SHARED: same token used from two different non-transient pids that are both alive now
        alive = {(p[0], p[1]) for p in pids if p[2] != "transient" and process_state(p[0], p[1]) == "alive"}
        if len(alive) > 1:
            ann.append("TOKEN_SHARED")
        return {"state": "LIVE", "evidence": {"rule": "accepted CLAIMED, no RELEASE, no OPERATOR_RELEASE, probe " + st,
                                             "host": host, "pid": pid, "pid_kind": kind, "age_seconds": self._age(c["since"])}, "annotations": ann}

    @staticmethod
    def _age(ts: str) -> float:
        try:
            return round((datetime.now(timezone.utc) - datetime.fromisoformat(ts)).total_seconds(), 1)
        except ValueError:
            return -1.0

    # -- r2: same-working-instance is a relational proposition; a matching token string alone does not establish it
    def same_instance(self, s: dict, c: dict) -> dict:
        """'distinct' | 'established' | 'unresolved'.  Baseline §9.2 / §14: SELF_OVERLAP needs evidence that the two claims
        were made by the same working instance, not merely the same instance string.  Evidence classes (design M-02, KG-01):
        the same non-transient process presented the token for both claims; or the earlier process is gone and a later
        non-transient process presents the token (continuity by possession, KG-01).  A transient (CLI) pid cannot tie
        possession to a process (IN-01), so shared tokens through the CLI are UNRESOLVED (Grok impl-r1 finding IN-03+IN-02)."""
        if s["instance_id"] != c["instance_id"]:
            return {"state": "distinct", "rule": "instance tokens differ"}
        sp, cp = s["pids"], c["pids"]
        if any(p[2] == "transient" for p in sp | cp):
            return {"state": "unresolved", "rule": "same token, but a transient (CLI) pid cannot tie possession to a process (IN-01)"}
        shared = {(p[0], p[1]) for p in sp} & {(p[0], p[1]) for p in cp}
        if shared:
            return {"state": "established", "rule": "same token presented by the same process for both claims"}
        s_alive = [p for p in sp if process_state(p[0], p[1]) == "alive"]
        c_alive = [p for p in cp if process_state(p[0], p[1]) == "alive"]
        if s_alive and c_alive:
            return {"state": "unresolved", "rule": "same token in use by two live processes (TOKEN_SHARED)"}
        if (s_alive and not c_alive) or (c_alive and not s_alive):
            return {"state": "established", "rule": "same token; earlier process gone, later process presents it (continuity by possession, KG-01)"}
        return {"state": "unresolved", "rule": "same token; process states unavailable or both gone"}

    # -- M-04 revisions -------------------------------------------------------------------------
    def established_transitions(self, resolved: str) -> list[dict]:
        """READY records on claims that resolve to this artifact: from-revision -> produced revision."""
        out = []
        cl = self.claims()
        for r in self.events("kind = 'READY'"):
            c = cl.get(r["claim_id"])
            if c and c["resolved"] == resolved:
                out.append({"claim_id": c["claim_id"], "instance_id": c["instance_id"], "from": c["revision_at_claim"],
                            "to": r["revision"], "seq": r["seq"], "ts": r["ts"]})
        return out

    # -- commands: self-state --------------------------------------------------------------------
    def claim(self, project: str, actor: str, op_class: str, target: str, root: str = ".", instance_id: str | None = None,
              relation: str = "unspecified", relates_to: str | None = None, recorded_by: str | None = None, note: str | None = None) -> dict:
        if op_class not in CLASSES:
            raise ValueError(f"op class must be one of {CLASSES}")
        if relation not in RELATIONS:
            raise ValueError(f"relation must be one of {RELATIONS}")
        root = os.path.abspath(root)
        resolved = resolve_ref(root, target)
        fid = file_identity(resolved)
        rev = sha256_file(resolved)
        cid = uuid.uuid4().hex[:12]
        inst = instance_id or uuid.uuid4().hex  # M-02: minted here unless the worker presents its existing token
        recorded_by = recorded_by or actor

        def go():
            return self._append({"kind": "CLAIMED", "claim_id": cid, "instance_id": inst, "actor": actor, "recorded_by": recorded_by,
                                 "project": project, "target": target, "root": root, "resolved": resolved, "fileid": fid, "revision": rev,
                                 "op_class": op_class, "class_evidence": "declared", "relation": relation, "relates_to": relates_to, "note": note,
                                 "data": {"evidence_class": "self-state" if recorded_by == actor else "relay-assertion"}})
        seq = self._tx(go)
        return {"claim_id": cid, "instance_id": inst, "seq": seq, "resolved": resolved, "fileid": fid, "revision": rev}

    def _require_token(self, c: dict, instance_id: str | None, action: str) -> None:
        if not instance_id or instance_id != c["instance_id"]:
            raise PermissionError(f"{action}: instance token does not match claim {c['claim_id']} (self-state requires the minted token)")

    def ready(self, claim_id: str, instance_id: str, note: str | None = None) -> dict:
        c = self.get(claim_id)
        self._require_token(c, instance_id, "ready")
        if c["released"]:
            self._tx(lambda: self._append({"kind": "ATTEMPT_ON_INACTIVE", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"],
                                           "recorded_by": c["actor"], "note": "READY refused: claim INACTIVE (baseline §18, B22)"}))
            raise ValueError("claim is INACTIVE; READY refused and recorded")
        rev = sha256_file(c["resolved"])

        def go():
            seq = self._append({"kind": "READY", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"], "recorded_by": c["actor"],
                                "resolved": c["resolved"], "fileid": file_identity(c["resolved"]), "revision": rev, "note": note})
            recl = None
            if c["op_class"] != "WRITE" and rev != c["revision_at_claim"]:
                recl = self._append({"kind": "RECLASSIFIED", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"], "recorded_by": c["actor"],
                                     "op_class": "WRITE", "class_evidence": "observed",
                                     "note": f"declared {c['op_class']}, own READY changed revision {str(c['revision_at_claim'])[:8]} -> {str(rev)[:8]} (B12)"})
            return {"seq": seq, "revision": rev, "reclassified_seq": recl}
        return self._tx(go)

    def note(self, claim_id: str, instance_id: str, text: str) -> int:
        c = self.get(claim_id)
        self._require_token(c, instance_id, "note")
        if c["released"]:
            self._tx(lambda: self._append({"kind": "ATTEMPT_ON_INACTIVE", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"],
                                           "recorded_by": c["actor"], "note": "NOTE refused: claim INACTIVE"}))
            raise ValueError("claim is INACTIVE; note refused and recorded")
        return self._tx(lambda: self._append({"kind": "NOTE", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"],
                                              "recorded_by": c["actor"], "note": text}))

    def release(self, claim_id: str, instance_id: str | None = None, operator: str | None = None, note: str | None = None) -> dict:
        c = self.get(claim_id)
        if c["released"]:
            raise ValueError(f"claim already INACTIVE since seq {c['released']['seq']}")
        if operator:
            seq = self._tx(lambda: self._append({"kind": "OPERATOR_RELEASE", "claim_id": claim_id, "instance_id": c["instance_id"], "actor": c["actor"],
                                                 "recorded_by": operator, "note": note, "data": {"evidence_class": "operator"}}))
            return {"seq": seq, "evidence_class": "operator"}
        if instance_id != c["instance_id"]:
            self._tx(lambda: self._append({"kind": "ATTEMPTED_RELEASE_OTHER", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"],
                                           "recorded_by": instance_id or "unknown", "note": note or "release attempted without the claim's token"}))
            raise PermissionError("release by another party establishes nothing (baseline §9.2); attempt recorded")
        seq = self._tx(lambda: self._append({"kind": "RELEASED", "claim_id": claim_id, "instance_id": instance_id, "actor": c["actor"],
                                             "recorded_by": c["actor"], "note": note, "data": {"evidence_class": "self-state"}}))
        return {"seq": seq, "evidence_class": "self-state"}

    # -- M-09 evaluation -------------------------------------------------------------------------
    def evaluate(self, claim_id: str, record: bool = True) -> dict:
        t_eval = now_iso()
        cl = self.claims()
        s = cl.get(claim_id)
        if not s:
            raise KeyError(f"no claim {claim_id}")
        s_life = self.lifecycle(s)
        s_fid_now = file_identity(s["resolved"])
        s_rev_now = sha256_file(s["resolved"])
        transitions = self.established_transitions(s["resolved"])
        annotations: list[str] = []
        unresolved: list[dict] = []
        conflicts: list[dict] = []
        considered: list[dict] = []
        rejected: list[dict] = []
        lineage: list[dict] = []
        if s_life["state"] == "INACTIVE":
            annotations.append("SUBJECT_INACTIVE")
        annotations += s_life["annotations"]
        if s["fileid_at_claim"] and s_fid_now and s["fileid_at_claim"] != s_fid_now:
            annotations.append("ARTIFACT_REPLACED")  # KG-15
        if s["fileid_at_claim"] and s_fid_now == s["fileid_at_claim"] and resolve_ref(s["root"], s["target"]) != s["resolved"]:
            annotations.append("ARTIFACT_MOVED")  # KG-13
        lineage.append({"proposition": "subject revision now", "source": "filesystem", "observation": "sha256 at evaluation", "value": s_rev_now})

        # revision relationship of the subject if it is a REVIEW (M-04 / corrected §23 / §26)
        s_review_state = None
        if s["op_class"] == "REVIEW":
            s_review_state = self._review_state(s, s_rev_now, transitions)
            if s_review_state["state"] == "superseded":
                annotations.append("SUPERSEDED_REVIEW")
            elif s_review_state["state"] == "unattributed":
                annotations.append("UNATTRIBUTED_CHANGE")
        elif s_rev_now != s["revision_at_claim"] and not any(t["to"] == s_rev_now for t in transitions):
            if s["op_class"] == "WRITE" and s_life["state"] == "LIVE":
                annotations.append("CHANGE_DURING_LIVE_WRITE")
            else:
                annotations.append("UNATTRIBUTED_CHANGE")

        # M-01: every other claim in the store is a candidate; no representation filter
        for cid, c in cl.items():
            if cid == claim_id:
                continue
            life = self.lifecycle(c)
            c_fid_now = file_identity(c["resolved"])
            ident = identity_relation(s["resolved"], s_fid_now, c["resolved"], c_fid_now)
            pair = (s["op_class"], c["op_class"])
            classes_ok = s["op_class"] in CLASSES and c["op_class"] in CLASSES
            could_conflict = (not classes_ok) or ("WRITE" in pair)  # an unestablished class cannot be assumed compatible (baseline §15; r2 IN-06 repair)
            same_inst = self.same_instance(s, c)
            entry = {"claim_id": cid, "actor": c["actor"], "instance_id": c["instance_id"], "op_class": c["op_class"], "class_evidence": c["class_evidence"],
                     "lifecycle": life["state"], "identity": ident, "same_instance": same_inst, "row": None}
            if life["state"] == "INACTIVE":
                rejected.append({"claim_id": cid, "reason": "INACTIVE (baseline §18): cannot create live consequence", "identity": ident["relation"]})
                if ident["relation"] == "SAME" and could_conflict and c["instance_id"] != s["instance_id"]:
                    annotations.append("HISTORICAL_CONFLICT")
                continue
            considered.append(entry)
            annotations += [a for a in life["annotations"] if a not in annotations]
            if ident["relation"] == "DISTINCT":
                entry["row"] = "DISTINCT: no baseline row"
                continue
            if ident["relation"] == "UNRESOLVED":
                if could_conflict:
                    unresolved.append({"proposition": f"SAME/DISTINCT({claim_id},{cid})", "reason": ident["rule"]})
                    entry["row"] = "identity UNRESOLVED and could change the answer"
                else:
                    entry["row"] = "identity UNRESOLVED but pair cannot conflict"
                continue
            # SAME artifact from here
            if not classes_ok:  # r2 IN-06 repair: operation class is a proposition; unresolved class -> UNKNOWN, never a row
                bad = [x for x, k in ((claim_id, s["op_class"]), (cid, c["op_class"])) if k not in CLASSES]
                unresolved.append({"proposition": f"operation class({','.join(bad)})", "reason": "class not established (baseline §15, B11)"})
                entry["row"] = "operation class UNRESOLVED"
                continue
            if same_inst["state"] == "established":
                entry["row"] = "same working instance: no coordination relationship"
                if "SELF_OVERLAP" not in annotations:
                    annotations.append("SELF_OVERLAP")
                continue
            if same_inst["state"] == "unresolved":  # r2 IN-03+IN-02 repair: matching token string is not evidence of one instance
                if could_conflict:
                    unresolved.append({"proposition": f"same working instance({claim_id},{cid})", "reason": same_inst["rule"]})
                    entry["row"] = "same-instance relationship UNRESOLVED and pair could conflict"
                else:
                    entry["row"] = "same-instance relationship UNRESOLVED but pair cannot conflict"
                continue
            if "TOKEN_SHARED" in life["annotations"] or "TOKEN_SHARED" in s_life["annotations"]:
                if could_conflict:
                    unresolved.append({"proposition": f"instance distinctness({claim_id},{cid})", "reason": "TOKEN_SHARED"})
                    entry["row"] = "instance distinctness UNRESOLVED"
                    continue
            if life["state"] == "UNRESOLVED":
                if could_conflict:
                    unresolved.append({"proposition": f"LIVE({cid})", "reason": "instance process gone, no RELEASE (KG-05)"})
                    entry["row"] = "lifecycle UNRESOLVED and pair could conflict"
                else:
                    entry["row"] = "lifecycle UNRESOLVED but pair cannot conflict"
                continue
            row = self._baseline_row(s, c, s_rev_now, s_review_state, transitions)
            entry["row"] = row["row"]
            if row["result"] == "CONFLICT":
                conflicts.append({"claim_id": cid, "actor": c["actor"], "instance_id": c["instance_id"], "op_class": c["op_class"], "row": row["row"],
                                  "lifecycle": life["evidence"]})
            elif row["result"] == "UNRESOLVED":
                unresolved.append({"proposition": row["proposition"], "reason": row["reason"]})
            elif row["result"] == "NON-CONFLICT":
                if s["relation"] != "unspecified" and c["relation"] != "unspecified" and (s["relates_to"] == cid or c["relates_to"] == claim_id):
                    annotations.append(f"INTENDED_OVERLAP({s['relation']}/{c['relation']})")
                if pair == ("REVIEW", "REVIEW") and c["revision_at_claim"] != s["revision_at_claim"]:
                    annotations.append("REVIEW_REVISIONS_DIFFER")

        # precedence (baseline §25)
        if conflicts:
            signal, row = "CONFLICT", conflicts[0]["row"]
        elif unresolved:
            signal, row = "UNKNOWN", None
        else:
            signal, row = "CLEAR", "no baseline conflict row TRUE; CLEAR conditions 1-10 satisfied"
        basis = {
            "psp_version": VERSION, "profile": PROFILE, "evaluation_time": t_eval, "subject_claim": claim_id,
            "claim_domain": f"store={self.path}; operation={claim_id}; scope=all participating claims at T={t_eval}",
            "discovery_domain": f"all claims in store {self.path}, every state, every project/target/actor string",
            "discovery_rule": "enumerate every CLAIMED row; identity evaluated per candidate by M-03; no representation filter (baseline §4)",
            "discovery_table": DISCOVERY_TABLE, "candidates_enumerated": len(cl) - 1,
            "subject": {"actor": s["actor"], "instance_id": s["instance_id"], "op_class": s["op_class"], "class_evidence": s["class_evidence"],
                        "target": s["target"], "resolved": s["resolved"], "fileid_at_claim": s["fileid_at_claim"], "fileid_now": s_fid_now,
                        "revision_at_claim": s["revision_at_claim"], "revision_now": s_rev_now, "lifecycle": s_life,
                        "review_state": s_review_state, "relation": s["relation"], "relates_to": s["relates_to"]},
            "observations_admitted": considered, "observations_rejected": rejected, "established_transitions": transitions,
            "lineage": lineage + [{"proposition": "identity", "source": "filesystem", "observation": "realpath+normcase and stat file identity",
                                   "transformation": "identity_relation()", "note": "reference strings recorded for display only"},
                                  {"proposition": "instance", "source": "PSP-minted token", "observation": "token presented on events", "transformation": "none"},
                                  {"proposition": "class", "source": "participant declaration then own READY", "observation": s["class_evidence"]},
                                  {"proposition": "lifecycle", "source": "store events + host process probe", "observation": s_life["evidence"]}],
            "conflicts": conflicts, "unresolved": unresolved, "answer_key_row": row, "annotations": sorted(set(annotations)),
            "signal": signal, "enforcement": "none (observational); --enforce-exit not set",
            "visible_limits": ["discovery = participating claims in this store only; non-participating writers never observed as workers (KG-07)",
                               "instance = token possession, not identity (KG-01, KG-14)", "liveness probe is host-local and pid-based (KG-05)",
                               "class before first observation rests on declared intent (KG-02)", "pre-creation identity rests on path (KG-12)"],
        }
        if record:
            eid = self._tx(lambda: self._append({"kind": "EVALUATED", "claim_id": claim_id, "instance_id": s["instance_id"], "actor": s["actor"],
                                                 "recorded_by": "psp", "resolved": s["resolved"], "revision": s_rev_now, "note": signal, "data": basis}))
            basis["evaluation_id"] = eid
        return basis

    def _review_state(self, s: dict, rev_now: str | None, transitions: list[dict]) -> dict:
        bound = s["revision_at_claim"]
        if bound is None or rev_now is None:
            return {"state": "unresolved", "bound": bound, "now": rev_now, "reason": "reviewed revision or current revision unavailable"}
        if bound == rev_now:
            return {"state": "current", "bound": bound, "now": rev_now}
        chain = [t for t in transitions if t["to"] == rev_now]
        if chain:
            return {"state": "superseded", "bound": bound, "now": rev_now, "by": chain[-1]}
        return {"state": "unattributed", "bound": bound, "now": rev_now, "reason": "current revision differs and no READY explains it"}

    def _baseline_row(self, s: dict, c: dict, s_rev_now: str | None, s_review_state: dict | None, transitions: list[dict]) -> dict:
        a, b = s["op_class"], c["op_class"]
        pair = f"{a}/{b}"
        if a not in CLASSES or b not in CLASSES:  # r2 IN-06: never let an unestablished class fall into a conflict branch
            return {"result": "UNRESOLVED", "row": pair, "proposition": f"operation class({s['claim_id'] if a not in CLASSES else c['claim_id']})",
                    "reason": "class not established (baseline §15, B11)"}
        if {a, b} <= {"READ", "REVIEW"}:
            return {"result": "NON-CONFLICT", "row": pair}
        if a == "WRITE" and b == "WRITE":
            return {"result": "CONFLICT", "row": "WRITE/WRITE"}
        if {a, b} == {"READ", "WRITE"}:
            return {"result": "CONFLICT", "row": pair}
        # REVIEW vs WRITE: owner's §23 sentence.  The review's bound revision must be the artifact's current reviewed state.
        review = s if a == "REVIEW" else c
        rstate = s_review_state if review is s else self._review_state(c, s_rev_now, transitions)
        if rstate["state"] == "current":
            return {"result": "CONFLICT", "row": pair + " (owner §23: LIVE WRITE on same artifact alters the current reviewed state)"}
        if rstate["state"] == "superseded":
            return {"result": "NON-CONFLICT", "row": pair + " (review target superseded by established transition; §26)"}
        return {"result": "UNRESOLVED", "row": pair, "proposition": f"revision relationship of REVIEW {review['claim_id']}", "reason": rstate.get("reason")}

    # -- M-12 metrics and verdicts ----------------------------------------------------------------
    def verdict(self, evaluation_seq: int, truth: str, operator: str, note: str | None = None) -> int:
        if truth not in ("true", "false-conflict", "false-clear", "false-unknown"):
            raise ValueError("truth must be true | false-conflict | false-clear | false-unknown")
        return self._tx(lambda: self._append({"kind": "VERDICT", "recorded_by": operator, "ref_claim": str(evaluation_seq), "note": note,
                                              "data": {"truth": truth, "evidence_class": "operator"}}))

    def intervention(self, operator: str, text: str) -> int:
        return self._tx(lambda: self._append({"kind": "INTERVENTION", "recorded_by": operator, "note": text, "data": {"evidence_class": "operator"}}))

    def metrics(self) -> dict:
        ev = self.events()
        evals = [e for e in ev if e["kind"] == "EVALUATED"]
        sig = {"CLEAR": 0, "CONFLICT": 0, "UNKNOWN": 0}
        unresolved_hist: dict[str, int] = {}
        ann_hist: dict[str, int] = {}
        for e in evals:
            d = json.loads(e["data"]) if e["data"] else {}
            sig[d.get("signal", "UNKNOWN")] = sig.get(d.get("signal", "UNKNOWN"), 0) + 1
            for u in d.get("unresolved", []):
                k = u["proposition"].split("(")[0]; unresolved_hist[k] = unresolved_hist.get(k, 0) + 1
            for a in d.get("annotations", []):
                k = a.split("(")[0]; ann_hist[k] = ann_hist.get(k, 0) + 1
        verdicts = [json.loads(e["data"])["truth"] for e in ev if e["kind"] == "VERDICT"]
        cl = self.claims()
        conflict_then_released_without_ready = 0
        for e in evals:
            d = json.loads(e["data"]) if e["data"] else {}
            c = cl.get(e["claim_id"])
            if d.get("signal") == "CONFLICT" and c and c["released"] and not c["ready"]:
                conflict_then_released_without_ready += 1
        return {"claims": len(cl), "evaluations": len(evals), "signals": sig, "unresolved_propositions": unresolved_hist, "annotations": ann_hist,
                "conflicts_then_released_without_ready": conflict_then_released_without_ready,
                "operator_releases": sum(1 for e in ev if e["kind"] == "OPERATOR_RELEASE"),
                "interventions": sum(1 for e in ev if e["kind"] == "INTERVENTION"),
                "attempted_release_other": sum(1 for e in ev if e["kind"] == "ATTEMPTED_RELEASE_OTHER"),
                "reclassified": sum(1 for e in ev if e["kind"] == "RECLASSIFIED"),
                "verdicts": {t: verdicts.count(t) for t in set(verdicts)}, "stale_instances": ann_hist.get("INSTANCE_PROCESS_GONE", 0)}

    def status(self) -> list[dict]:
        out = []
        for cid, c in self.claims().items():
            life = self.lifecycle(c)
            if life["state"] == "INACTIVE":
                continue
            out.append({"claim_id": cid, "actor": c["actor"], "op_class": c["op_class"], "target": c["target"], "lifecycle": life["state"],
                        "age_seconds": self._age(c["since"]), "annotations": life["annotations"]})
        return out


# ---------------------------------------------------------------- M-10 presentation and CLI

def summary_line(b: dict) -> str:
    others = ", ".join(f"{x['claim_id']}:{x['actor']}:{x['op_class']}" for x in b["conflicts"]) or "-"
    unres = "; ".join(u["proposition"] for u in b["unresolved"]) or "-"
    ann = ",".join(b["annotations"]) or "-"
    return (f"{b['signal']}  subject={b['subject_claim']} {b['subject']['actor']}/{b['subject']['op_class']}  row={b['answer_key_row'] or '-'}  "
            f"conflicts_with={others}  unresolved={unres}  annotations={ann}  eval={b.get('evaluation_id', '-')}@{b['evaluation_time']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="psp2", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=None); ap.add_argument("--json", action="store_true")
    ap.add_argument("--enforce-exit", action="store_true", help="ENFORCEMENT (labeled, opt-in): exit 2 on CONFLICT, 3 on UNKNOWN")
    ap.add_argument("--worker-pid", type=int, default=None,
                    help="IN-01: the worker's own long-lived pid; without it the CLI's pid is recorded as transient and never probed")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("claim"); p.add_argument("--project", required=True); p.add_argument("--as", dest="actor", required=True)
    p.add_argument("--op", choices=CLASSES, required=True); p.add_argument("--target", required=True); p.add_argument("--root", default=".")
    p.add_argument("--instance", default=os.environ.get("PSP2_INSTANCE")); p.add_argument("--relation", choices=RELATIONS, default="unspecified")
    p.add_argument("--relates-to", default=None); p.add_argument("--recorded-by", default=None); p.add_argument("--note", default=None)
    p.add_argument("--no-eval", action="store_true")
    p = sub.add_parser("evaluate"); p.add_argument("--claim", required=True)
    p = sub.add_parser("ready"); p.add_argument("--claim", required=True); p.add_argument("--instance", default=os.environ.get("PSP2_INSTANCE")); p.add_argument("--note", default=None)
    p = sub.add_parser("note"); p.add_argument("--claim", required=True); p.add_argument("--instance", default=os.environ.get("PSP2_INSTANCE")); p.add_argument("--text", required=True)
    p = sub.add_parser("release"); p.add_argument("--claim", required=True); p.add_argument("--instance", default=os.environ.get("PSP2_INSTANCE"))
    p.add_argument("--as-operator", dest="operator", default=None); p.add_argument("--note", default=None)
    sub.add_parser("status"); sub.add_parser("verify"); sub.add_parser("metrics")
    p = sub.add_parser("why"); p.add_argument("--eval", required=True, type=int)
    p = sub.add_parser("history"); p.add_argument("--claim", default=None)
    p = sub.add_parser("verdict"); p.add_argument("--eval", required=True, type=int); p.add_argument("--truth", required=True); p.add_argument("--as-operator", dest="operator", required=True); p.add_argument("--note", default=None)
    p = sub.add_parser("intervention"); p.add_argument("--as-operator", dest="operator", required=True); p.add_argument("--text", required=True)
    a = ap.parse_args(argv)
    psp = PSP2(a.db, pid=a.worker_pid, pid_kind="declared" if a.worker_pid else "transient")
    try:
        return _dispatch(psp, a)
    finally:
        psp.close()


def _emit_signal(basis: dict, a) -> int:
    if a.json:
        print(json.dumps(basis, indent=2, ensure_ascii=False, default=str))
    else:
        print(summary_line(basis))
    if a.enforce_exit:
        basis_note = {"CLEAR": 0, "CONFLICT": 2, "UNKNOWN": 3}[basis["signal"]]
        return basis_note
    return 0


def _dispatch(psp: PSP2, a) -> int:
    try:
        if a.cmd == "claim":
            c = psp.claim(a.project, a.actor, a.op, a.target, root=a.root, instance_id=a.instance, relation=a.relation, relates_to=a.relates_to,
                          recorded_by=a.recorded_by, note=a.note)
            print(json.dumps({"claim_id": c["claim_id"], "instance_id": c["instance_id"], "resolved": c["resolved"], "fileid": c["fileid"], "revision": c["revision"]}))
            if a.no_eval:
                return 0
            basis = psp.evaluate(c["claim_id"])
            if a.enforce_exit:
                basis["enforcement"] = "exit-code (labeled, opt-in)"
            return _emit_signal(basis, a)
        if a.cmd == "evaluate":
            basis = psp.evaluate(a.claim)
            if a.enforce_exit:
                basis["enforcement"] = "exit-code (labeled, opt-in)"
            return _emit_signal(basis, a)
        if a.cmd == "ready":
            print(json.dumps(psp.ready(a.claim, a.instance, a.note))); return 0
        if a.cmd == "note":
            print(json.dumps({"seq": psp.note(a.claim, a.instance, a.text)})); return 0
        if a.cmd == "release":
            print(json.dumps(psp.release(a.claim, a.instance, a.operator, a.note))); return 0
        if a.cmd == "status":
            print(json.dumps(psp.status(), indent=2)); return 0
        if a.cmd == "verify":
            v = psp.verify(); print(json.dumps(v)); return 0 if v["ok"] else 1
        if a.cmd == "metrics":
            print(json.dumps(psp.metrics(), indent=2)); return 0
        if a.cmd == "why":
            rows = psp.events("seq = ? AND kind = 'EVALUATED'", (a.eval,))
            if not rows:
                print("no such evaluation", file=sys.stderr); return 1
            print(json.dumps(json.loads(rows[0]["data"]), indent=2, ensure_ascii=False)); return 0
        if a.cmd == "history":
            for r in (psp.events("claim_id = ?", (a.claim,)) if a.claim else psp.events()):
                print(f"{r['seq']:>5} {r['ts']} {r['kind']:<24} {r['claim_id'] or '-':<12} {r['actor'] or '-':<10} {r['op_class'] or '-':<6} "
                      f"{(r['revision'] or '-')[:8]} {r['note'] or ''}")
            return 0
        if a.cmd == "verdict":
            print(json.dumps({"seq": psp.verdict(a.eval, a.truth, a.operator, a.note)})); return 0
        if a.cmd == "intervention":
            print(json.dumps({"seq": psp.intervention(a.operator, a.text)})); return 0
    except (KeyError, ValueError, PermissionError) as e:
        print(f"error: {e}", file=sys.stderr); return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
