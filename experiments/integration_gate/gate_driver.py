# -*- coding: utf-8 -*-
"""INTEGRATION GATE driver (FROZEN 10.09.2026).

Драйвер = policy/external стор: выдает права (exclusion по триггеру;
R/S-режим; explore-действие по dispatch модуля), исполняет эпизоды,
регистрирует RAW. Модуль (gate_module.py) = механизмы.

Клетки:
  --cell "c2|POOL|R|r1"      (carrier|sem|right|rep)
  carriers: c1 N1D-B (addressing; без прав)
            c2 E6N-POOL (G2+G3+G8)   c3 E6N-TEMP (G4)
            c4 TempF-TEMP (G5)       c5 SD-POOL (G6)
            c6 N6bV3-TEMP (G7)       c7 SD4-POOL (R1)
            c8 S6bV3-POOL (R1)
  --cell "R0|S3|NA|r1"        (R0-режим: v0.6.x anchor на модуле)
"""
import argparse
import glob
import hashlib
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_module as gm  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"

# carrier -> (learn_steps, phase_steps, sem, trigger)
CARRIERS = {
    "c1": ([("w1", "1")],
           [("1", "w1", "n"), ("1", "w1", None), ("1", "w1", None)],
           "POOL", None),
    "c2": ([("w1", "1"), ("w1", "2")],
           [("1", "w1", "n"), ("1", "w1", None), ("1", "w1", None)],
           "POOL", "C5"),
    "c3": ([("w1", "1"), ("w1", "2")],
           [("1", "w1", "n"), ("1", "w1", None), ("1", "w1", None)],
           "TEMP", "C5"),
    "c4": ([("w1", "1"), ("w1", "2")],
           [("1", "w1", "n"), ("1", "w1", None),
            ("1", "w2", None), ("1", "w2", None)],
           "TEMP", "C5"),
    "c5": ([("w1", "1")],
           [("1", "w2", None)] * 4,
           "POOL", "C1"),
    "c6": ([("w1", "1"), ("w1", "2")],
           [("3", "w1", "n"), ("3", "w1", None),
            ("3", "w1", None), ("3", "w1", None)],
           "TEMP", "C5"),
    "c7": ([("w1", "1")],
           [("1", "w2", None)] * 3 + [("1", "w2", None)] * 3,
           "POOL", "C3"),
    "c8": ([("w1", "1"), ("w1", "2")],
           [("3", "w2", None)] * 4,
           "POOL", "C5"),
}
G_MAP = {"c1": "G1", "c2": "G2+G3+G8", "c3": "G4", "c4": "G5",
         "c5": "G6", "c6": "G7", "c7": "R1", "c8": "R1"}

SEQUENCES_R0 = {
    "S0": ["w1", "wY"], "S1": ["w1", "noise", "wY"],
    "S2": ["noise", "w1", "wY"],
    "S3": ["w1", "noise", "noise", "wY"],
    "S4": ["w1", "w1", "noise", "wY"],
    "S5": ["noise", "wY"], "S6b": ["w1", "noise2", "wY"],
    "P1": ["w1", "noise2", "wY", "noise", "wY"],
    "P2": ["w1", "noise2", "wY", "noise", "wY", "noise", "wY"],
}
WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
    "noise": (["a", "n"], "absent", "1"),
    "noise2": (["a", "n"], "absent", "2"),
}

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]
_ORIG_PRIOR_LINEAGE = update._prior_lineage


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
    d = os.path.join(DIR, "data_gate_a1_%s" % cell)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def _do_action(store, cmd, ep, kind):
    facts = observer.collect(store)
    act = {"schema_version": "0.1",
           "action_id": "act_gatea1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": cmd,
           "args": {"goal": GOAL, "ctx_extra": "absent"}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "GATE-A1-%s" % kind}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="gatea1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return outcome, (k.get("knowledge_id") if k else None)


def _outcome_of(v):
    m = re.search(r"outcome=(\w+)", v.get("context") or "")
    return m.group(1) if m else None


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


def _line_members(store, st):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    mem = []
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
        if "a" in syms and a[1] == "absent" and a[2] == "fix-a":
            mem.append({"kid": v["knowledge_id"],
                        "outcome": _outcome_of(v),
                        "created_at": v.get("created_at")})
    mem.sort(key=lambda m: (m["created_at"], m["kid"]))
    return mem


def _fresh(store, st):
    mem = _line_members(store, st)
    last = -1
    for i, m in enumerate(mem):
        if m["outcome"] == "success":
            last = i
    return mem[last + 1:], mem


def _conflict(store, st):
    # сравнение V-значений по success-записям (как EP-2B/2C)
    vals = set()
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    for v in latest.values():
        if _outcome_of(v) != "success":
            continue
        aw = v.get("applicable_when") or {}
        if "V" in aw:
            vals.add(str(aw["V"]))
        for o in (v.get("applicability_observations") or []):
            if o.get("signal") == "V":
                vals.update(str(x) for x in (o.get("values_seen") or []))
    return len(vals) >= 2


def trigger_ok(conf, store, st):
    fresh, mem = _fresh(store, st)
    if not fresh or fresh[-1]["outcome"] == "success":
        return False
    if conf == "C1":
        return len(fresh) == 1
    if conf == "C3":
        return len(fresh) == 3
    if conf == "C5":
        return _conflict(store, st)
    return False


def run_cell(cell):
    carrier, sem, right, rep = cell.split("|")
    learn_steps, phase, car_sem, conf = CARRIERS[carrier]
    assert sem == car_sem, (cell, car_sem)
    module = gm.GateModule(fresh_store(cell), sem)
    st = module.st
    rec = {"cell": cell, "carrier": carrier, "g_map": G_MAP[carrier],
           "sem": sem, "right": right, "rep": rep, "conf": conf,
           "events": [], "steps": [], "checks": [],
           "audit_before": hash_layers(), "final_snapshot": None}

    # learn-фаза (forced)
    for lw, lv in learn_steps:
        env_set(lw, None, lv)
        _do_action(module.store, "fix-a", 0, "learn")

    retract_installed = False
    for i, (envver, world, noise) in enumerate(phase, start=1):
        # external policy: выдача exclusion по конфигурации
        if conf and not module.exclusions:
            if trigger_ok(conf, module.store, st):
                _, mem = _fresh(module.store, st)
                succ = [m for m in mem if m["outcome"] == "success"]
                kid = succ[-1]["kid"] if succ else None
                if kid:
                    module.exclude(kid, trigger_ref="E1")
                    if right == "R" and not retract_installed:
                        kids = list(module.exclusions)
                        orig = _ORIG_PRIOR_LINEAGE

                        def wrapper(store, sym, e_val, cmd, _k=kids):
                            return [r for r in orig(store, sym, e_val,
                                                    cmd)
                                    if r.get("knowledge_id") not in _k]
                        update._prior_lineage = wrapper
                        retract_installed = True
                    rec["trigger"] = {"conf": conf, "step": i - 1,
                                      "kid": kid}
        # эпизод
        env_set(world, noise, envver)
        if module.attempt_needed():
            kid0 = module.exclusions[0]
            outcome, _ = _do_action(module.store, "fix-a", i, "attempt")
            step = {"step": i, "mode": "attempt", "action": "fix-a",
                    "outcome": outcome, "refs": [kid0]}
            module.process_attempt(kid0, outcome == "success")
        elif module.pop_explore():
            outcome, newk = _do_action(module.store, "fix-aq", i,
                                       "explore")
            step = {"step": i, "mode": "explore", "action": "fix-aq",
                    "outcome": outcome, "refs": [],
                    "new_candidate": newk}
            rec["events"].append({"event": "explore", "step": i,
                                  "outcome": outcome})
        else:
            sug, info = module.decide(PROBLEM, "absent",
                                      {"E": "absent", "V": envver},
                                      by="gate")
            rec["checks"].append({"step": i, "pool_info": info})
            if sug is None:
                step = {"step": i, "mode": "S3", "action": None,
                        "outcome": None, "refs": []}
            else:
                cmd = [a["command"] for a in sug["candidate_actions"]
                       if a.get("type") == "command"]
                refs = list(sug.get("knowledge_refs") or [])
                outcome, _ = _do_action(module.store, cmd[0], i, "S2")
                step = {"step": i, "mode": "S2", "action": cmd[0],
                        "outcome": outcome, "refs": refs,
                        "strategy_id": sug.get("strategy_id")}
        rec["steps"].append(step)
        module.on_episode({"mode": step["mode"],
                           "outcome": step["outcome"],
                           "knowledge_refs": step["refs"]})
    rec["events"] = list(module.events) + rec["events"]
    rec["guards"] = module.guards
    rec["exclusions_final"] = list(module.exclusions)
    rec["slot_state"] = dict(module.slot_state)
    rec["final_snapshot"] = snapshot_all(module.store)
    rec["audit_after"] = hash_layers()
    out = os.path.join(DIR, "GATE_A1_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved %s; steps=%d; events=%s; guards_ok=%s; audit=%s"
          % (out, len(rec["steps"]),
             [e["event"] for e in rec["events"]],
             all(g["ok"] for g in rec["guards"]),
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"
    return rec


def run_r0(cell):
    _, seq, _, rep = cell.split("|")
    module = gm.GateModule(fresh_store(cell), "POOL")
    rec = {"cell": cell, "seq": seq, "rep": rep, "steps": [],
           "probes": [], "audit_before": hash_layers()}
    for i, world in enumerate(SEQUENCES_R0[seq], start=1):
        flags = WORLD_DEF[world]
        noise = "n" if world in ("noise", "noise2") else None
        env_set(world, noise, flags[2])
        outcome, _ = _do_action(module.store, "fix-a", i, "learn")
        rec["steps"].append({"step": i, "world": world,
                             "outcome": outcome})
    for w in ("w1", "wY", "noise", "noise2"):
        flags = WORLD_DEF[w]
        env_set(w, "n" if w in ("noise", "noise2") else None, flags[2])
        sug, info = module.decide(PROBLEM, "absent",
                                  {"E": "absent", "V": flags[2]},
                                  by="gate")
        if sug is None:
            rec["probes"].append({"world": w, "strategy_id": "S3",
                                  "candidate_commands": [],
                                  "knowledge_refs": [],
                                  "pool_info": info})
        else:
            cmds = [a["command"] for a in sug["candidate_actions"]
                    if a.get("type") == "command"]
            rec["probes"].append({
                "world": w, "strategy_id": sug.get("strategy_id"),
                "candidate_commands": cmds,
                "knowledge_refs": sug.get("knowledge_refs"),
                "pool_info": info})
    rec["audit_after"] = hash_layers()
    out = os.path.join(DIR, "GATE_A1_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved %s; steps=%d; probes=%d; audit=%s"
          % (out, len(rec["steps"]), len(rec["probes"]),
             rec["audit_before"] == rec["audit_after"]), flush=True)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    cell = args.cell
    assert cell.count("|") == 3, "cell: C|SEM|RIGHT|rep"
    if cell.startswith("R0|"):
        run_r0(cell)
    else:
        run_cell(cell)


if __name__ == "__main__":
    main()
