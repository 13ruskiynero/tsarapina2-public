# -*- coding: utf-8 -*-
"""ACQ-1 / A0 recorder (FROZEN 07.09.2026; read-only относительно v0.5).

Эмпирическая проверка раздела 2 APPLICABILITY_ACQUISITION1_DESIGN.md:
что текущий learn РЕАЛЬНО пишет в адрес/Knowledge на learn-моментах.

Learn-путь — КАНОНИЧЕСКИЙ v0.5 (cs1_driver.learn, with_ctx=True =
текущая CA-1-адресация), воспроизведён байт-в-байт. Регистратор
добавляет ТОЛЬКО чтение: сигналы E/V/S до действия, состав
Knowledge-записей и производный адрес после каждого learn-момента.

Learn-последовательность на реплику: w1 x2, затем wY x2
(verified-success демонстрации; решение 1 DESIGN). Реплики r1/r2,
свежие сторы data_acq0_r1/r2. Audit: sha256 слоёв до/после.
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
LOG = os.path.join(DIR, "ACQ0_run.log")
RECORDS = {"r1": [], "r2": []}
LEARN_PLAN = ["w1", "w1", "wY", "wY"]

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
}

LAYER_FILES = [
    "strategy/strategy.py",
    "update/update.py",
    "knowledge/knowledge.py",
    "experience/experience.py",
    "executor/executor.py",
    "evaluation/evaluation.py",
    "observer/observer.py",
    "observer/polygon_sensor.py",
    "storage/store.py",
]


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


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


def signals():
    return {"E": polygon_sensor.sensor_envfact()[4],
            "V": polygon_sensor.sensor_envver()[4],
            "S": polygon_sensor.sensor_symptom()[4]}


def mk_action(store, ctx):
    a = {"schema_version": "0.1",
         "action_id": "act_acq0_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": "operator/learn",
         "type": "command", "command": "fix-a",
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "ACQ-1 A0"}
    if ctx is not None:
        a["args"]["ctx_extra"] = ctx
    store.append_action(a)
    return a


def kid_set(store):
    return set(v["knowledge_id"]
               for v in store.read_knowledge_versions_all())


def learn_moment(store, world, rep, idx):
    env_set(world)
    sig = signals()          # чтение ДО действия (регистратор)
    problem = "tsasvc.service inactive symptom=%s" % \
        polygon_sensor.sensor_symptom()[4]
    facts = observer.collect(store)
    # оператор записывает ctx_extra = E (канонический v0.5-путь)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = mk_action(store, ctx)
    before = kid_set(store)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="acq0")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    created = kid_set(store) - before
    assert len(created) <= 1, "learn-момент создал >1 знания: %s" % created
    rec = {"rep": rep, "idx": idx, "world": world,
           "signals_before": sig, "ok": ok, "outcome": outcome,
           "action_ctx_extra": ctx,
           "facts": [{"subject": f.get("subject"),
                      "property": f.get("property"),
                      "value": f.get("value"),
                      "source": f.get("source"),
                      "raw_ref": (f.get("provenance") or {}).get("raw_ref")}
                     for f in facts],
           "knowledge_created": bool(k)}
    if created:
        kid = sorted(created)[0]
        kr = store.read_knowledge(kid)
        assert "applicable_when" not in kr, \
            "Knowledge содержит applicable_when: %s" % kid
        assert "condition" not in kr, \
            "Knowledge содержит condition: %s" % kid
        addr = strategy._addr_cmd_of(store, kr)
        rec["knowledge"] = {
            "knowledge_id": kid,
            "fields": sorted(kr.keys()),
            "has_applicable_when": False,
            "source": kr.get("source"),
            "observer": kr.get("observer"),
            "content": kr.get("content"),
            "context": kr.get("context"),
            "experience_refs": kr.get("experience_refs"),
            "derived_addr": {"symptom": sorted(addr[0]) if addr else [],
                             "ctx": addr[1] if addr else None,
                             "command": addr[2] if addr else None},
        }
    RECORDS[rep].append(rec)
    log({"rep": rep, "idx": idx, "event": "LEARN", "world": world,
         "E": sig["E"], "V": sig["V"], "S": sig["S"], "ok": ok,
         "knowledge_created": bool(k)})
    return rec


def fresh_store(name):
    d = os.path.join(DIR, "data_acq0_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(LOG, "w", encoding="utf-8").close()
    audit_before = hash_layers()
    print("== ACQ-1 / A0 (FROZEN; read-only recorder) ==", flush=True)
    for rep in ("r1", "r2"):
        st = fresh_store(rep)
        for i, world in enumerate(LEARN_PLAN, start=1):
            learn_moment(st, world, rep, i)
    audit_after = hash_layers()
    with open(os.path.join(DIR, "ACQ0_records.json"), "w",
              encoding="utf-8") as f:
        json.dump({"audit_before": audit_before,
                   "audit_after": audit_after,
                   "records": RECORDS}, f, ensure_ascii=False, indent=1)
    same = audit_before == audit_after
    with open(os.path.join(DIR, "ACQ0_audit.txt"), "w",
              encoding="utf-8") as f:
        for rel in sorted(set(audit_before) | set(audit_after)):
            f.write("%s  before=%s  after=%s\n"
                    % (rel, audit_before.get(rel), audit_after.get(rel)))
        f.write("LAYERS_UNCHANGED=%s\n" % same)
    print("saved ACQ0_records.json (%d записей/реплика); "
          "layers unchanged: %s" % (len(RECORDS["r1"]), same), flush=True)
    assert same, "слои изменились во время A0-прогона"


if __name__ == "__main__":
    main()
