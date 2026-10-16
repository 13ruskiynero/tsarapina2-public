# -*- coding: utf-8 -*-
"""AB-1 driver (FROZEN 07.09.2026; measurement-only; v0.6 НЕ меняется).

Гипотеза: failure-знание (без applicable_when) в линии (a, absent,
fix-a) становится prior[-1] → переоткрытие условия из контекста
последнего success: w1-s → noise-f → wY-s даёт {E:absent,V:2} вместо
{E:absent} + obs V[1,2].

Канонический learn: env_set → collect → действие fix-a (ctx_extra=E)
→ executor → evaluation → experience → update.apply. Миры w1/wY —
verified success; noise — failure. Последовательности S1..S4 × r1/r2.
Регистрация: снапшот knowledge-версий после каждого шага +
eligibility-пробы (suggest при w1/wY/noise) после финального шага.
Audit: sha256 слоёв v0.6 до/после прогона.
"""
import glob
import hashlib
import json
import os
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
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "AB1_run.log")

SEQUENCES = {
    "S1": ["w1", "noise", "wY"],
    "S2": ["noise", "w1", "wY"],
    "S3": ["w1", "noise", "noise", "wY"],
    "S4": ["w1", "w1", "noise", "wY"],
}
PROBE_WORLDS = ["w1", "wY", "noise"]

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
    "noise": (["a", "n"], "absent", "1"),
}

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]


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
    d = os.path.join(DIR, "data_ab1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def learn(store, world, ep):
    env_set(world)
    problem = "tsasvc.service inactive symptom=a"
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1",
           "action_id": "act_ab1_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": "fix-a",
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "AB-1"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="ab1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    log({"event": "STEP", "ep": ep, "world": world, "outcome": outcome,
         "ok": ok})
    return outcome, k


def snapshot(store):
    """Полный снапшот latest-версий knowledge стора."""
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
            "content": v.get("content"),
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
                           obs_now=obs, by="ab1")
    return {"world": world, "obs": obs, "strategy_id": sug["strategy_id"],
            "candidate_commands": [a["command"]
                                   for a in sug["candidate_actions"]],
            "knowledge_refs": sug.get("knowledge_refs"),
            "rationale": [r.get("rule") for r in sug["rationale"]]}


def run_sequence(name, rep):
    st = fresh_store("%s_%s" % (name, rep))
    rec = {"sequence": name, "rep": rep, "steps": []}
    for i, world in enumerate(SEQUENCES[name], start=1):
        outcome, k = learn(st, world, "%s_%s_m%d" % (name, rep, i))
        rec["steps"].append({"step": i, "world": world, "outcome": outcome,
                             "snapshot": snapshot(st)})
    rec["probes"] = [probe(st, w) for w in PROBE_WORLDS]
    return rec


def main():
    open(LOG, "w", encoding="utf-8").close()
    audit_before = hash_layers()
    print("== AB-1 (FROZEN 07.09; measurement-only; v0.6 не меняется) ==",
          flush=True)
    runs = []
    for name in ("S1", "S2", "S3", "S4"):
        for rep in ("r1", "r2"):
            runs.append(run_sequence(name, rep))
    audit_after = hash_layers()
    same = audit_before == audit_after
    with open(os.path.join(DIR, "AB1_records.json"), "w",
              encoding="utf-8") as f:
        json.dump({"audit_before": audit_before,
                   "audit_after": audit_after, "runs": runs},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(DIR, "AB1_audit.txt"), "w",
              encoding="utf-8") as f:
        for rel in sorted(set(audit_before) | set(audit_after)):
            f.write("%s before=%s after=%s\n"
                    % (rel, audit_before.get(rel), audit_after.get(rel)))
        f.write("LAYERS_UNCHANGED=%s\n" % same)
    print("saved AB1_records.json (%d прогонов); layers unchanged: %s"
          % (len(runs), same), flush=True)
    assert same, "слои v0.6 изменились во время AB-1"


if __name__ == "__main__":
    main()
