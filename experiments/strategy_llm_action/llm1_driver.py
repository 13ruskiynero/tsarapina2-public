# -*- coding: utf-8 -*-
"""LLM1 driver (12 runs; PROTOCOL FROZEN 11.09.2026).

Клетки: P1 (live), N1 (invalid output), N2 (unknown action),
N3 (LLM error), N4 (excluded candidate), N5 (not-permitted);
r1/r2. Запуск: python3 llm1_driver.py --cell "P1|r1".

Среды: полигон tsasvc; свежий стор на клетку; K1 (fix-a, success)
через канонический learn-эпизод. strategy_state фиксируется
(внешний trigger — policy; strategy.py не трогается).
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
from strategy import strategy  # noqa: E402
from strategy import exclusion  # noqa: E402
from update import update  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge import Bridge  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
PROBLEM = "tsasvc.service inactive symptom=a"
LOG = os.path.join(DIR, "LLM1_run.log")

RAW_N1 = "Извините, я не могу предложить действие."
RAW_N2 = '{"candidate_actions": [{"type": "command", "command": "reboot"}]}'
RAW_EXCL = ('{"candidate_actions": [{"type": "command", '
            '"command": "fix-a"}]}')
URL_N3 = "http://localhost:9/v1/chat/completions"

LAYER_FILES = [
    "strategy/strategy.py", "strategy/exclusion.py",
    "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py", "llm/adapter.py",
]


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


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def env_set(world):
    flags = ["a"]
    if world == "w2":
        flags.append("q")
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in ("/run/tsasvc.dbg", "/run/tsasvc.pulse"):
        if os.path.exists(f):
            os.remove(f)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write("1")
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def fresh_store(cell):
    d = os.path.join(DIR, "data_llm1_%s" % cell)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def learn_k1(store):
    """Канонический learn-эпизод: K1 (fix-a, success)."""
    env_set("w1")
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1",
           "action_id": "act_llm1_learn_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": "fix-a",
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "LLM1 learn"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(problem=PROBLEM, observations=facts,
                                actions=[act["action_id"]],
                                result_ref=res["result_id"],
                                machine="llm1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return (k.get("knowledge_id") if k else None), outcome


def run_cell(cell):
    code, rep = cell.split("|")
    assert code in ("P1", "N1", "N2", "N3", "N4", "N5"), cell
    store = fresh_store(cell)
    k1, outcome = learn_k1(store)
    audit_before = hash_layers()

    # strategy_state фиксируется (внешний trigger: strategy не
    # инициирует; EF-12 OPEN)
    sug = strategy.suggest(store, {"problem": PROBLEM}, by="llm1",
                           ctx_now="absent",
                           obs_now={"E": "absent", "V": "1"})
    strategy_state = {"strategy_id": sug.get("strategy_id"),
                      "knowledge_refs": sug.get("knowledge_refs")}

    excluded_commands = set()
    module = None
    if code == "N4":
        module = exclusion.GateModule(store, "POOL")
        module.exclude(k1, trigger_ref="E1")
        excluded_commands = {"fix-a"}

    bridge = Bridge(store, excluded_commands=excluded_commands)
    context = ("Полигон: сервис tsasvc неактивен (symptom=a). "
               "Выбери РОВНО ОДНУ команду из разрешённых: %s. "
               "Верни JSON согласно формату." %
               ", ".join(executor.ALLOWED_PREFIXES))
    kwargs = {}
    grant = True
    if code == "P1":
        pass
    elif code == "N1":
        kwargs["raw_override"] = RAW_N1
    elif code == "N2":
        kwargs["raw_override"] = RAW_N2
    elif code == "N3":
        kwargs["url_override"] = URL_N3
        kwargs["timeout"] = 10
    elif code == "N4":
        kwargs["raw_override"] = RAW_EXCL
    elif code == "N5":
        kwargs["raw_override"] = RAW_EXCL
        grant = False

    rec = bridge.invoke(
        task=PROBLEM, context=context,
        episode_id="llm1_%s_%s" % (code, rep), grant=grant, **kwargs)
    rec["cell"] = cell
    rec["code"] = code
    rec["rep"] = rep
    rec["k1"] = k1
    rec["learn_outcome"] = outcome
    rec["strategy_state"] = strategy_state
    rec["s3_events"] = []
    rec["explore_events"] = []
    if module is not None:
        rec["exclusion_after"] = list(module.exclusions)
        rec["k_remains_excluded"] = k1 in module.exclusions
        # EF-13 (fix): регистрация — через exclusion-контур
        # (eligible pool), а не сырой suggest
        mod_elig, _ = module.eligible_pool(
            PROBLEM, "absent", {"E": "absent", "V": "1"})
        rec["post_exclusion_eligible"] = [x["knowledge_id"]
                                          for x in mod_elig]
    rec["audit_before"] = audit_before
    rec["audit_after"] = hash_layers()

    out = os.path.join(DIR, "LLM1_cell_%s.json" % cell.replace("|", "_"))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    log({"cell": cell, "decision": rec["decision"],
         "reason": rec["no_action_reason"],
         "action": (rec["parsed"] or {}).get("action"),
         "executed": rec["executed"],
         "audit": rec["audit_before"] == rec["audit_after"]})
    print("saved %s; decision=%s; reason=%s; executed=%s; audit=%s"
          % (out, rec["decision"], rec["no_action_reason"],
             rec["executed"],
             rec["audit_before"] == rec["audit_after"]), flush=True)
    assert rec["audit_before"] == rec["audit_after"], "слои изменились"
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", required=True)
    args = ap.parse_args()
    run_cell(args.cell)


if __name__ == "__main__":
    main()
