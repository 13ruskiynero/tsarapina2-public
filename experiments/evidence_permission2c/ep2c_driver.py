# -*- coding: utf-8 -*-
"""EP-2C driver (FROZEN 10.09.2026; measurement-only; v0.6.x не меняется).

Дизайн: EVIDENCE_PERMISSION2C_DESIGN.md (FROZEN);
протокол: evidence_permission2c/PROTOCOL.md.

Клетка: --cell "U1|POOL|R|r1"  (UNIT|SEM|RIGHT|rep)
  UNIT: U1,U2,U3,U4,U5a,U5b,U6a,U6b, NEG-E6N, NEG-E6N-V3, NEG-E6S
  SEM: POOL | TEMP; RIGHT: R | S.
Механики: POOL-фильтр (обёртка чтения кандидатов, multi-exclusion);
Explore-эпизод (EP-1-стиль): S3-детекция при пустом eligible pool
ПОСЛЕ exclusion → следующий эпизод = forced fix-aq (mode="explore"),
события s3_detected/explore; U5b: после exclusion(K2) — стресс-
событие exclusion(K1) (boundary). TEMP — как EP-2B (slot; SOL
только success ЧЛЕНА L и mode="S2").
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"

W1 = ("w1", None)
W2 = ("w2", None)
W1N = ("w1", "n")

# unit -> (learn_steps, phase_steps); phase step = (envver, world, noise)
HISTORIES = {
    "U1": ([("w1", "1")],
           [("1", "w2", None), ("1", "w2", None),
            ("1", "w2", None), ("1", "w2", None)]),
    "U2": ([("w1", "1")],
           [("1", "w2", None)] * 3 + [("1", "w2", None)] * 3),
    "U3": ([("w1", "1"), ("w1", "2")],
           [("3", "w2", None), ("3", "w2", None),
            ("3", "w2", None), ("3", "w2", None)]),
    "U4": ([("w1", "1"), ("w1", "2")],
           [("3", "w1", "n"), ("3", "w1", None),
            ("3", "w1", None), ("3", "w1", None)]),
    "U5a": ([("w1", "1"), ("w1", "2")],
            [("1", "w1", "n"), ("1", "w1", None),
             ("1", "w1", None)]),
    "U5b": ([("w1", "1"), ("w1", "2")],
            [("1", "w1", "n"), ("1", "w1", None),
             ("1", "w1", None), ("1", "w1", None)]),
    "U6a": ([("w1", "1"), ("w1", "2")],
            [("3", "w2", None), ("3", "w2", None),
             ("3", "w2", None), ("3", "w2", None)]),
    "U6b": ([("w1", "1"), ("w1", "2")],
            [("3", "w1", "n"), ("3", "w1", None),
             ("3", "w1", None), ("3", "w1", None)]),
    "NEG-E6N": ([("w1", "1"), ("w1", "2")],
                [("1", "w1", "n"), ("1", "w1", None),
                 ("1", "w1", None)]),
    "NEG-E6N-V3": ([("w1", "1"), ("w1", "2")],
                   [("3", "w1", "n"), ("1", "w1", None),
                    ("1", "w1", None)]),
    "NEG-E6S": ([("w1", "1"), ("w1", "2")],
                [("1", "w2", None), ("1", "w2", None),
                 ("1", "w2", None)]),
}
TRIGGERS = {"U1": "C1", "U2": "C3", "U3": "C5", "U4": "C5",
            "U5a": "C5", "U5b": "C5", "U6a": "C5", "U6b": "C5",
            "NEG-E6N": "C5", "NEG-E6N-V3": "C5", "NEG-E6S": "C5"}
ROLES = {"U1": "core", "U2": "core", "U3": "core", "U4": "core",
         "U5a": "core+negative", "U5b": "core", "U6a": "core",
         "U6b": "core", "NEG-E6N": "negative",
         "NEG-E6N-V3": "negative", "NEG-E6S": "negative"}
STEMP = ("U6a", "U6b")

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

_OUTCOME_RE = re.compile(r"outcome=(\w+)")
_ORIG_PRIOR_LINEAGE = update._prior_lineage


class FilteredStore(object):
    """POOL: набор исключённых kid'ов невидим для чтения кандидатов."""

    def __init__(self, store, exclude_kids):
        self._store = store
        self._ex = set(exclude_kids or [])

    def read_knowledge_versions_all(self):
        return [v for v in self._store.read_knowledge_versions_all()
                if v["knowledge_id"] not in self._ex]

    def __getattr__(self, name):
        return getattr(self._store, name)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def hash_layers():
    out = {}
    for rel in LAYER_FILES:
        p = os.path.join(BASE, rel)
        if os.path.exists(p):
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()[:16]
    return out


def load_strategy():
    spec = importlib.util.spec_from_file_location(
        "strategy_aa_mod", os.path.join(DIR, "..",
                                        "applicability_addressing1",
                                        "strategy_aa.py"))
    st = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(st)
    return st


def env_set(world, noise, envver):
    flags = ["a"]
    if world == "w2":
        flags.append("q")
    if noise == "n":
        flags.append("n")
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(envver)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(cell):
    d = os.path.join(DIR, "data_ep2c_%s" % cell)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def outcome_of_row(r):
    m = _OUTCOME_RE.search(r.get("context") or "")
    return m.group(1) if m else None


def obs_kinds(r):
    kinds = []
    for o in r.get("applicability_observations") or []:
        if o.get("source") == "verified failure":
            kinds.append("a" if o.get("signal") else "b")
        else:
            kinds.append("s")
    return kinds


def v_vals_of(r):
    vals = set()
    aw = r.get("applicable_when") or {}
    if "V" in aw:
        vals.add(str(aw["V"]))
    for o in r.get("applicability_observations") or []:
        if o.get("signal") == "V":
            vals.update(str(x) for x in (o.get("values_seen") or []))
    return vals


def row_of(store, kid):
    for v in store.read_knowledge_versions_all():
        if v["knowledge_id"] == kid:
            return v
    return None


def line_members(store, st, cmd="fix-a"):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    members = []
    for v in latest.values():
        if v.get("status") not in ("active", "conflicted"):
            continue
        try:
            a = st._addr_cmd_of(store, v)
        except Exception:
            a = None
        if not a:
            continue
        syms = sorted(a[0]) if hasattr(a[0], "__iter__") else [a[0]]
        if "a" in syms and a[1] == "absent" and a[2] == cmd:
            members.append({
                "kid": v["knowledge_id"], "created_at": v.get("created_at"),
                "outcome": outcome_of_row(v), "aw": v.get("applicable_when"),
                "kinds": obs_kinds(v), "v_vals": sorted(v_vals_of(v)),
            })
    members.sort(key=lambda m: (m["created_at"], m["kid"]))
    return members


def fresh_failures(members):
    last_succ = -1
    for i, m in enumerate(members):
        if m["outcome"] == "success":
            last_succ = i
    return members[last_succ + 1:]


def conflict_present(members):
    vals = set()
    for m in members:
        if m["outcome"] == "success":
            vals.update(m.get("v_vals") or [])
    return len(vals) >= 2


def recovery_present(members):
    first_fail = None
    for i, m in enumerate(members):
        if m["outcome"] != "success":
            first_fail = i
            break
    if first_fail is None:
        return False
    for m in members[first_fail + 1:]:
        if m["outcome"] == "success":
            return True
    return False


def trigger_check(conf, members):
    fresh = fresh_failures(members)
    if not fresh or fresh[-1]["outcome"] == "success":
        return False
    if conf == "C1":
        return len(fresh) == 1
    if conf == "C3":
        return len(fresh) == 3
    if conf == "C5":
        return conflict_present(members)
    if conf == "C6":
        return recovery_present(members)
    if conf == "C2":
        return len(fresh) == 2
    return False


def _install_retract(kids):
    orig = _ORIG_PRIOR_LINEAGE

    def wrapper(store, sym, e_val, cmd):
        return [r for r in orig(store, sym, e_val, cmd)
                if r.get("knowledge_id") not in kids]
    update._prior_lineage = wrapper


def _do_action(store, cmd, ep, kind):
    facts = observer.collect(store)
    act = {"schema_version": "0.1",
           "action_id": "act_ep2c_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "EP2C-%s" % kind}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="ep2c")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"step": ep, "mode": kind, "action": cmd, "outcome": outcome,
            "ok": ok, "strategy_id": None,
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def learn_episode(store, world, envver, cmd, ep):
    env_set(world, None, envver)
    return _do_action(store, cmd, ep, "learn")


def check_episode(store, st, world, noise, envver, ep, excl_kids):
    env_set(world, noise, envver)
    src = FilteredStore(store, excl_kids) if excl_kids else store
    sug = st.suggest(src, {"problem": PROBLEM}, by="ep2c",
                     ctx_now="absent",
                     obs_now={"E": "absent", "V": envver})
    sid = sug.get("strategy_id")
    refs = list(sug.get("knowledge_refs") or [])
    acts = [a for a in (sug.get("candidate_actions") or [])
            if a.get("type") == "command"]
    rec = {"step": ep, "world": world, "noise": noise, "envver": envver,
           "strategy_id": sid, "knowledge_refs": refs,
           "excluded_visible": bool(set(refs) & set(excl_kids or [])),
           "ref_outcome": None}
    if sid == "S3" or not acts:
        rec.update({"mode": "S3", "action": None, "outcome": None})
        return rec
    ref_row = row_of(store, refs[0]) if refs else None
    rec["ref_outcome"] = outcome_of_row(ref_row) if ref_row else None
    cmd = acts[0].get("command")
    rec["mode"] = "S2"
    res = _do_action(store, cmd, ep, "S2")
    rec.update({"action": res["action"], "outcome": res["outcome"],
                "ok": res["ok"],
                "created_knowledge_id": res["created_knowledge_id"]})
    return rec


def explore_episode(store, world, noise, envver, ep):
    env_set(world, noise, envver)
    res = _do_action(store, "fix-aq", ep, "explore")
    return {"step": ep, "mode": "explore", "action": "fix-aq",
            "outcome": res["outcome"], "ok": res["ok"],
            "knowledge_refs": [], "ref_outcome": None,
            "created_knowledge_id": res["created_knowledge_id"]}


def snapshot_all(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        rows.append({
            "knowledge_id": v["knowledge_id"], "version": v["version"],
            "status": v["status"], "schema_version": v.get("schema_version"),
            "context": v.get("context"),
            "lineage_generation": v.get("lineage_generation"),
            "applicable_when": v.get("applicable_when"),
            "applicability_observations": v.get(
                "applicability_observations"),
            "experience_refs": v.get("experience_refs"),
        })
    rows.sort(key=lambda r: r["knowledge_id"])
    return rows


def run_cell(cell):
    unit, sem, right, rep = cell.split("|")
    assert unit in HISTORIES and sem in ("POOL", "TEMP") and \
        right in ("R", "S"), cell
    conf = TRIGGERS[unit]
    st = load_strategy()
    store = fresh_store(cell)
    learn_steps, phase_steps = HISTORIES[unit]
    rec = {"cell": cell, "unit": unit, "sem": sem, "right": right,
           "rep": rep, "role": ROLES[unit], "conf": conf, "learn": [],
           "steps": [], "events": [], "checks": [], "line_trace": [],
           "audit_before": hash_layers(), "final_snapshot": None}
    with open(os.path.join(DIR, "..", "applicability_addressing1",
                           "strategy_aa.py"), "rb") as f:
        rec["branch_module_sha"] = hashlib.sha256(f.read()).hexdigest()[:16]

    for lw, lv in learn_steps:
        learn_episode(store, lw, lv, "fix-a", 0)
        rec["learn"].append({"world": lw, "envver": lv})

    excl_kids = []
    slot = "none"
    sol_done = False
    explore_pending = False
    for i, (envver, world, noise) in enumerate(phase_steps, start=1):
        # триггер (однократно) + опциональный стресс-эксkлюжн (U5b)
        if not excl_kids:
            mem = line_members(store, st)
            if trigger_check(conf, mem):
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                if kid:
                    excl_kids.append(kid)
                    if right == "R":
                        _install_retract(list(excl_kids))
                    rec["events"].append({
                        "event": "exclusion", "step": i - 1,
                        "knowledge_id": kid, "conf": conf,
                        "stress": False, "trigger_ref": "E1"})
                    if unit == "U5b":
                        others = [m for m in succ if m["kid"] != kid]
                        if others:
                            k1 = others[-1]["kid"]
                            excl_kids.append(k1)
                            _install_retract(list(excl_kids))
                            rec["events"].append({
                                "event": "exclusion", "step": i - 1,
                                "knowledge_id": k1, "conf": conf,
                                "stress": True, "trigger_ref": "E2"})
                    # pool-инъекция
                    sug_f = st.suggest(FilteredStore(store, excl_kids),
                                       {"problem": PROBLEM},
                                       by="ep2c-chk", save=False,
                                       ctx_now="absent",
                                       obs_now={"E": "absent", "V": envver})
                    seen_f = [s.get("knowledge_id") for s in
                              (sug_f.get("knowledge_snapshot") or [])]
                    rec["checks"].append({
                        "step": i, "type": "pool_injection",
                        "poolled_excl": all(k not in seen_f
                                            for k in excl_kids)})
        # attempt (TEMP; в EP-2C не активируется)
        if sem == "TEMP" and slot == "open":
            step = {"step": i, "mode": "attempt", "action": "fix-a",
                    "outcome": None, "knowledge_refs": [excl_kids[0]],
                    "ref_outcome": None}
            slot = "consumed"
        elif explore_pending:
            step = explore_episode(store, world, noise, envver, i)
            explore_pending = False
            rec["events"].append({
                "event": "explore", "step": i, "action": "fix-aq",
                "outcome": step["outcome"],
                "new_candidate": step.get("created_knowledge_id")})
            # K-невозврат: после explore excluded не вернулся
            sug_f = st.suggest(FilteredStore(store, excl_kids),
                               {"problem": PROBLEM}, by="ep2c-chk",
                               save=False, ctx_now="absent",
                               obs_now={"E": "absent", "V": envver})
            seen_f = [s.get("knowledge_id") for s in
                      (sug_f.get("knowledge_snapshot") or [])]
            rec["checks"].append({
                "step": i, "type": "post_explore_k_not_returned",
                "k_absent": all(k not in seen_f for k in excl_kids)})
        else:
            step = check_episode(store, st, world, noise, envver, i,
                                 excl_kids)
            if step.get("mode") == "S3" and excl_kids:
                rec["events"].append({"event": "s3_detected", "step": i})
                explore_pending = True
        rec["steps"].append(step)
        rec["line_trace"].append(
            [{k: m[k] for k in ("kid", "outcome", "aw", "kinds")}
             for m in line_members(store, st)])
        # SOL (TEMP): success ЧЛЕНА L, mode=="S2"
        if (sem == "TEMP" and excl_kids and not sol_done
                and step.get("mode") == "S2"
                and step.get("outcome") == "success"):
            ref0 = (step.get("knowledge_refs") or [None])[0]
            l_kids = [m["kid"] for m in line_members(store, st)]
            if ref0 in l_kids and ref0 != excl_kids[0]:
                sol_done = True
                slot = "open"
                rec["events"].append({"event": "sol", "step": i,
                                      "knowledge_id": ref0})
                rec["events"].append({"event": "slot", "step": i,
                                      "knowledge_id": excl_kids[0],
                                      "trigger_ref": "E1"})
    rec["final_snapshot"] = snapshot_all(store)
    rec["audit_after"] = hash_layers()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    cell = args.cell
    assert cell.count("|") == 3, "cell: UNIT|SEM|RIGHT|rep"
    rec = run_cell(cell)
    out = os.path.join(DIR, "EP2C_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    evs = [(e["event"], e.get("step")) for e in rec["events"]]
    print("saved %s; steps=%d; events=%s; audit=%s"
          % (out, len(rec["steps"]), evs,
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"


if __name__ == "__main__":
    main()
