# -*- coding: utf-8 -*-
"""EP-2B driver (FROZEN 10.09.2026; measurement-only; v0.6.x не меняется).

Дизайн: EVIDENCE_PERMISSION2B_DESIGN.md (FROZEN; MP-1=v1);
протокол: evidence_permission2b/PROTOCOL.md.

Клетка: --cell "E6N|POOL|R|r1"  (HIST|SEM|RIGHT|rep)
  SEM ∈ {POOL, TEMP}; RIGHT ∈ {R, S}; HALT не прогоняется (деривация
  EP-2A). POOL = pool-фильтр (K невидим для suggest; НЕ halt);
  TEMP = pool-фильтр + однократный verification slot:
  exclusion → sign-of-life(K′) → slot(K) → attempt(apply K once) →
  success ⇒ eligible / failure ⇒ remains excluded (no retries).

Среды/триггеры (PROTOCOL §3): SD→C1, NpD→C2, S6bV3/E6S/E6N-V3/E6N→
C5, C6N→C6.
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

HISTORIES = {
    "SD": ([("w1", "1")],
           [("f", "1", "w2", None)] * 3),
    "NpD": ([("w1", "1")],
            [("f", "1", "w1", "n")] * 3 + [("s", "1", "w1", None)]),
    "S6bV3": ([("w1", "1"), ("w1", "2")],
              [("f", "3", "w2", None)] * 3),
    "E6S": ([("w1", "1"), ("w1", "2")],
            [("f", "1", "w2", None)] * 3),
    "E6N-V3": ([("w1", "1"), ("w1", "2")],
               [("f", "3", "w1", "n"), ("s", "1", "w1", None),
                ("s", "1", "w1", None)]),
    "E6N": ([("w1", "1"), ("w1", "2")],
            [("f", "1", "w1", "n"), ("s", "1", "w1", None),
             ("s", "1", "w1", None)]),
    "C6N": ([("w1", "1")],
            [("f", "1", "w1", "n"), ("s", "1", "w1", None),
             ("f", "1", "w1", "n"), ("s", "1", "w1", None),
             ("s", "1", "w1", None)]),
}
TRIGGERS = {"SD": "C1", "NpD": "C2", "S6bV3": "C5", "E6S": "C5",
            "E6N-V3": "C5", "E6N": "C5", "C6N": "C6"}

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

_OUTCOME_RE = re.compile(r"outcome=(\w+)")
_ORIG_PRIOR_LINEAGE = update._prior_lineage


class FilteredStore(object):
    """POOL-семантика: K невидим для чтения кандидатов (весь прочий
    API делегируется)."""

    def __init__(self, store, exclude_kid):
        self._store = store
        self._ex = exclude_kid

    def read_knowledge_versions_all(self):
        return [v for v in self._store.read_knowledge_versions_all()
                if v["knowledge_id"] != self._ex]

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
    d = os.path.join(DIR, "data_ep2b_%s" % cell)
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
    if conf == "C2":
        return len(fresh) == 2
    if conf == "C5":
        return conflict_present(members)
    if conf == "C6":
        return recovery_present(members)
    return False


def _install_retract(kid):
    orig = _ORIG_PRIOR_LINEAGE

    def wrapper(store, sym, e_val, cmd):
        return [r for r in orig(store, sym, e_val, cmd)
                if r.get("knowledge_id") != kid]
    update._prior_lineage = wrapper


def _do_action(store, cmd, ep, kind):
    facts = observer.collect(store)
    act = {"schema_version": "0.1",
           "action_id": "act_ep2b_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "EP2B-%s" % kind}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"], machine="ep2b")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return {"step": ep, "mode": kind, "action": cmd, "outcome": outcome,
            "ok": ok, "strategy_id": None,
            "created_knowledge_id": k.get("knowledge_id") if k else None}


def learn_episode(store, world, envver, cmd, ep):
    env_set(world, None, envver)
    return _do_action(store, cmd, ep, "learn")


def check_episode(store, st, world, noise, envver, ep, excl_kid):
    env_set(world, noise, envver)
    src = FilteredStore(store, excl_kid) if excl_kid else store
    sug = st.suggest(src, {"problem": PROBLEM}, by="ep2b",
                     ctx_now="absent",
                     obs_now={"E": "absent", "V": envver})
    sid = sug.get("strategy_id")
    refs = list(sug.get("knowledge_refs") or [])
    acts = [a for a in (sug.get("candidate_actions") or [])
            if a.get("type") == "command"]
    rec = {"step": ep, "world": world, "noise": noise, "envver": envver,
           "strategy_id": sid, "knowledge_refs": refs,
           "excluded_visible": bool(excl_kid and excl_kid in refs),
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


def attempt_episode(store, kid, world, noise, envver, ep):
    """Контролируемое применение K (verification attempt; вне suggest)."""
    env_set(world, noise, envver)
    res = _do_action(store, "fix-a", ep, "attempt")
    rec = {"step": ep, "mode": "attempt", "action": "fix-a",
           "outcome": res["outcome"], "ok": res["ok"],
           "knowledge_refs": [kid], "ref_outcome": None,
           "created_knowledge_id": res["created_knowledge_id"]}
    return rec


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
    hist, sem, right, rep = cell.split("|")
    assert sem in ("POOL", "TEMP") and right in ("R", "S"), cell
    conf = TRIGGERS[hist]
    st = load_strategy()
    store = fresh_store(cell)
    learn_steps, verify_steps = HISTORIES[hist]
    rec = {"cell": cell, "history": hist, "sem": sem, "right": right,
           "rep": rep, "conf": conf, "learn": [], "steps": [],
           "events": [], "checks": [], "line_trace": [],
           "audit_before": hash_layers(), "final_snapshot": None}
    with open(os.path.join(DIR, "..", "applicability_addressing1",
                           "strategy_aa.py"), "rb") as f:
        rec["branch_module_sha"] = hashlib.sha256(f.read()).hexdigest()[:16]

    for lw, lv in learn_steps:
        learn_episode(store, lw, lv, "fix-a", 0)
        rec["learn"].append({"world": lw, "envver": lv})

    excl_kid = None
    slot = "none"
    sol_done = False
    attempt_done = False
    for i, (aim, envver, world, noise) in enumerate(verify_steps, start=1):
        # триггер (однократно): exclusion
        if excl_kid is None and not attempt_done:
            mem = line_members(store, st)
            if trigger_check(conf, mem):
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                if kid:
                    excl_kid = kid
                    if right == "R":
                        _install_retract(kid)
                    rec["events"].append({
                        "event": "exclusion", "step": i - 1,
                        "knowledge_id": kid, "conf": conf,
                        "trigger_ref": "E1"})
                    # checks: pool-инъекция (K невидим / видим без обёртки)
                    sug_f = st.suggest(FilteredStore(store, kid),
                                       {"problem": PROBLEM}, by="ep2b-chk",
                                       save=False, ctx_now="absent",
                                       obs_now={"E": "absent", "V": envver})
                    sug_u = st.suggest(store, {"problem": PROBLEM},
                                       by="ep2b-chk", save=False,
                                       ctx_now="absent",
                                       obs_now={"E": "absent", "V": envver})
                    rec["checks"].append({
                        "step": i, "type": "pool_injection",
                        "poolled_excl": kid not in
                        (sug_f.get("knowledge_refs") or []) and kid not in
                        [s.get("knowledge_id") for s in
                         (sug_f.get("knowledge_snapshot") or [])],
                        "unpoolled_has": kid in
                        (sug_u.get("knowledge_refs") or []) or kid in
                        [s.get("knowledge_id") for s in
                         (sug_u.get("knowledge_snapshot") or [])]})
        # attempt-эпизод (TEMP, slot open)
        if sem == "TEMP" and slot == "open":
            step = attempt_episode(store, excl_kid, world, noise, envver, i)
            ok = step["outcome"] == "success"
            rec["events"].append({
                "event": "attempt", "step": i, "knowledge_id": excl_kid,
                "result": step["outcome"], "eligible_after": ok})
            slot = "consumed"
            attempt_done = True
            if ok:
                kid0 = excl_kid
                rec["events"].append({"event": "eligible", "step": i,
                                      "knowledge_id": kid0})
                excl_kid = None
                sug_u = st.suggest(store, {"problem": PROBLEM},
                                   by="ep2b-chk", save=False,
                                   ctx_now="absent",
                                   obs_now={"E": "absent", "V": envver})
                rec["checks"].append({
                    "step": i, "type": "eligibility_injection",
                    "kid": kid0,
                    "present": kid0 in
                    (sug_u.get("knowledge_refs") or []) or kid0 in
                    [s.get("knowledge_id") for s in
                     (sug_u.get("knowledge_snapshot") or [])]})
        else:
            step = check_episode(store, st, world, noise, envver, i,
                                 excl_kid)
        rec["steps"].append(step)
        rec["line_trace"].append(
            [{k: m[k] for k in ("kid", "outcome", "aw", "kinds")}
             for m in line_members(store, st)])
        # sign-of-life (TEMP): успех другого члена L после exclusion
        if (sem == "TEMP" and excl_kid is not None and not sol_done
                and step.get("mode") == "S2"
                and step.get("outcome") == "success"
                and (step.get("knowledge_refs") or [None])[0] != excl_kid):
            sol_done = True
            slot = "open"
            rec["events"].append({
                "event": "sol", "step": i,
                "knowledge_id": (step.get("knowledge_refs") or [None])[0]})
            rec["events"].append({
                "event": "slot", "step": i, "knowledge_id": excl_kid,
                "trigger_ref": "E1"})
    rec["final_snapshot"] = snapshot_all(store)
    rec["audit_after"] = hash_layers()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    cell = args.cell
    assert cell.count("|") == 3, "cell: HIST|SEM|RIGHT|rep"
    rec = run_cell(cell)
    out = os.path.join(DIR, "EP2B_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    evs = [e["event"] for e in rec["events"]]
    print("saved %s; steps=%d; events=%s; audit=%s"
          % (out, len(rec["steps"]), evs,
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"


if __name__ == "__main__":
    main()
