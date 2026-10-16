# -*- coding: utf-8 -*-
"""INTEGRATION GATE v0.6.x driver (FROZEN 07.09.2026).

Дизайн: INTEGRATION_GATE_V06X_DESIGN.md (FROZEN); контракт:
APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md (FROZEN, L1–L6).
Реальный код, БЕЗ in-process-патчей:
  --impl v06x : рабочие слои (update.py live, v0.6.x-контракт);
  --impl v06  : baseline-модуль update_v06_baseline.py (v0.6-семантика,
                для G5-сравнения поведения; recorder отсутствует).
Сценарии: S0..S5, S6b, P1, P2 (9) x r1/r2 = 18 прогонов на impl.
Регистрация: снапшот knowledge-версий (вкл. context,
lineage_generation) после каждого шага; prior/pivot/fb_existed на
success-шагах; пробы w1/wY/noise/noise2; audit слоёв до/после.
"""
import argparse
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = None

SEQUENCES = {
    "S0": ["w1", "wY"],
    "S1": ["w1", "noise", "wY"],
    "S2": ["noise", "w1", "wY"],
    "S3": ["w1", "noise", "noise", "wY"],
    "S4": ["w1", "w1", "noise", "wY"],
    "S5": ["noise", "wY"],
    "S6b": ["w1", "noise2", "wY"],
    "P1": ["w1", "noise2", "wY", "noise", "wY"],
    "P2": ["w1", "noise2", "wY", "noise", "wY", "noise", "wY"],
}
ALL_SEQS = ("S0", "S1", "S2", "S3", "S4", "S5", "S6b", "P1", "P2")
PROBE_WORLDS = ["w1", "wY", "noise", "noise2"]

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


def load_update(impl):
    """v06x: live update.update; v06: baseline-модуль (v0.6-семантика)."""
    if impl == "v06x":
        sys.path.insert(0, BASE)
        from update import update as um
        return um
    spec = importlib.util.spec_from_file_location(
        "update_v06_baseline_mod",
        os.path.join(BASE, "update", "update_v06_baseline.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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


def env_set(world):
    flags, e, v = WORLD_DEF[world]
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.envver", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(v)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(name):
    d = os.path.join(DIR, "data_gate_v06x_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def _capture_prior(um, store, exp_full, impl):
    sym = um._lineage_sym(exp_full)
    e_val = um._ctx_of_exp(store, exp_full)
    cmd = um._cmd_of(store, exp_full)
    rows = um._prior_lineage(store, sym, e_val, cmd)
    fb = [r for r in rows if r.get("applicable_when") is not None]
    if impl == "v06x":
        pivot = fb[-1] if fb else None      # L2
    else:
        pivot = rows[-1] if rows else None  # v0.6: prior[-1]
    return {"sym": sorted(sym) if hasattr(sym, "__iter__") else sym,
            "ctx": e_val, "cmd": cmd,
            "prior_ids": [r["knowledge_id"] for r in rows],
            "fb_existed": bool(fb),
            "pivot_id": pivot["knowledge_id"] if pivot else None,
            "pivot_has_aw": bool(pivot and pivot.get("applicable_when"))}


def learn(um, store, world, ep, impl):
    env_set(world)
    problem = "tsasvc.service inactive symptom=a"
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1",
           "action_id": "act_gate_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": "fix-a",
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "GATE-V06X"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="gate")
    experience.save(store, exp_full)
    prior_info = None
    if outcome == "success":
        prior_info = _capture_prior(um, store, exp_full, impl)
    k = um.apply(store, exp_full["experience_id"], outcome)
    return {"event": "STEP", "ep": ep, "world": world, "outcome": outcome,
            "ok": ok, "prior_info": prior_info,
            "created_knowledge_id": k.get("knowledge_id") if k else None}, k


def snapshot(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        addr = None
        try:
            a = strategy._addr_cmd_of(store, v)
            addr = (sorted(a[0]) if a else [], a[1] if a else None,
                    a[2] if a else None)
        except Exception:
            pass
        rows.append({
            "knowledge_id": v["knowledge_id"],
            "version": v["version"],
            "status": v["status"],
            "created_at": v.get("created_at"),
            "schema_version": v.get("schema_version"),
            "content": v.get("content"),
            "context": v.get("context"),
            "lineage_generation": v.get("lineage_generation"),
            "applicable_when": v.get("applicable_when"),
            "applicability_observations": v.get(
                "applicability_observations"),
            "experience_refs": v.get("experience_refs"),
            "lineage": {"sym": addr[0], "ctx": addr[1], "cmd": addr[2]}
            if addr else None,
        })
    rows.sort(key=lambda r: r["knowledge_id"])
    return rows


def probe(store, world):
    env_set(world)
    obs = {"E": polygon_sensor.sensor_envfact()[4],
           "V": polygon_sensor.sensor_envver()[4]}
    problem = "tsasvc.service inactive symptom=a"
    sug = strategy.suggest(store, {"problem": problem}, ctx_now=obs["E"],
                           obs_now=obs, by="gate")
    return {"world": world, "obs": obs, "strategy_id": sug["strategy_id"],
            "candidate_commands": [a["command"]
                                   for a in sug["candidate_actions"]],
            "knowledge_refs": sug.get("knowledge_refs"),
            "rationale": [r.get("rule") for r in sug["rationale"]]}


def run_sequence(um, impl, name, rep):
    st = fresh_store("%s_%s_%s" % (impl, name, rep))
    rec = {"impl": impl, "sequence": name, "rep": rep, "steps": []}
    for i, world in enumerate(SEQUENCES[name], start=1):
        step_rec, k = learn(um, st, world,
                            "%s_%s_%s_m%d" % (impl, name, rep, i), impl)
        step_rec["snapshot"] = snapshot(st)
        rec["steps"].append(step_rec)
    rec["probes"] = [probe(st, w) for w in PROBE_WORLDS]
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True, choices=["v06x", "v06"])
    ap.add_argument("--seqs", default=",".join(ALL_SEQS),
                    help="последовательности через запятую (для чанков)")
    args = ap.parse_args()
    impl = args.impl
    seqs = tuple(s for s in args.seqs.split(",") if s in ALL_SEQS)
    global LOG
    LOG = os.path.join(DIR, "GATE_V06X_run_%s.log" % impl)
    open(LOG, "w", encoding="utf-8").close()
    um = load_update(impl)
    audit_before = hash_layers()
    print("== GATE v0.6.x impl=%s (FROZEN 07.09.2026; реальный код) =="
          % impl, flush=True)
    runs = []
    for name in seqs:
        for rep in ("r1", "r2"):
            runs.append(run_sequence(um, impl, name, rep))
    audit_after = hash_layers()
    same = audit_before == audit_after
    rec_path = os.path.join(DIR, "GATE_V06X_records_%s.json" % impl)
    if os.path.exists(rec_path):
        with open(rec_path, encoding="utf-8") as f:
            prev = json.load(f)
        prev["runs"] += runs
        runs = prev["runs"]
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump({"impl": impl, "audit_before": audit_before,
                   "audit_after": audit_after, "runs": runs},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(DIR, "GATE_V06X_audit_%s.txt" % impl), "w",
              encoding="utf-8") as f:
        for rel in sorted(set(audit_before) | set(audit_after)):
            f.write("%s before=%s after=%s\n"
                    % (rel, audit_before.get(rel), audit_after.get(rel)))
        f.write("LAYERS_UNCHANGED=%s\n" % same)
    print("saved GATE_V06X_records_%s.json (всего %d прогонов); "
          "layers unchanged: %s" % (impl, len(runs), same), flush=True)
    assert same, "слои изменились во время gate-прогона (%s)" % impl


if __name__ == "__main__":
    main()
