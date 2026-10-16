# -*- coding: utf-8 -*-
"""AS-2 driver (FROZEN 06.09.2026; measurement-only; v0.5 не меняется).

Миры: w1..wY+noise; сигналы E/V/S до действия; фиксированное fix-a
через Executor; опыт/знания не создаются. learn-эталон на w1 на
каждую реплику. Реплики r1/r2; план: w1×2 + w2×3 + wX×3 + wY×3 +
noise×3 = 14 эпизодов на реплику. Миры: w1=[a] E=absent V=1;
w2=[a,extra] E=present V=2; wX=[a,extra] E=present V=1;
wY=[a] E=absent V=2; noise=[a,n] E=absent V=1.
"""
import glob
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

from executor import executor  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402

SVC = "tsasvc"
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "AS2_run.log")
RECORDS = []
PLAN = ["w1"] * 2 + ["w2"] * 3 + ["wX"] * 3 + ["wY"] * 3 + ["noise"] * 3

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "w2": (["a", "extra"], "present", "2"),
    "wX": (["a", "extra"], "present", "1"),
    "wY": (["a"], "absent", "2"),
    "noise": (["a", "n"], "absent", "1"),
}


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


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


def learn_ref(rep):
    env_set("w1")
    sig = signals()
    st = fresh_store("learn_%s" % rep)
    action = {"schema_version": "0.1",
              "action_id": "act_as2_l_%s" % rep,
              "strategy_id": None, "proposed_by": "as2",
              "type": "command", "command": "fix-a",
              "args": {}, "permitted": True,
              "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "rationale": "AS-2 learn"}
    executor.execute(st, action)
    ok = stable_active()
    log({"rep": rep, "event": "LEARN", "signals": sig, "ok": ok})
    assert ok
    return sig


def run_episode(store, world, rep, idx):
    env_set(world)
    sig = signals()
    action = {"schema_version": "0.1",
              "action_id": "act_as2_%s_%d_%s" % (rep, idx,
                                                 uuid.uuid4().hex[:6]),
              "strategy_id": None, "proposed_by": "as2",
              "type": "command", "command": "fix-a",
              "args": {}, "permitted": True,
              "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "rationale": "AS-2"}
    res = executor.execute(store, action)
    ok = stable_active()
    out = "success" if ok else (res.get("outcome") or "failure")
    rec = {"rep": rep, "idx": idx, "world": world, "signals": sig,
           "outcome": out, "ok": ok,
           "svc_after": (res.get("state_after") or {}).get(
               "service:tsasvc.state")}
    RECORDS.append(rec)
    log({"rep": rep, "idx": idx, "world": world, "E": sig["E"],
         "V": sig["V"], "S": sig["S"], "outcome": out})
    return rec


def fresh_store(name):
    d = os.path.join(DIR, "data_as2_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== APPLICABILITY-STRUCTURE-1 / AS-2 (FROZEN) ==", flush=True)
    refs = {}
    for rep in ("r1", "r2"):
        ref = learn_ref(rep)
        refs[rep] = ref
        st = fresh_store("ep_%s" % rep)
        for i, world in enumerate(PLAN, start=1):
            run_episode(st, world, rep, i)
    with open(os.path.join(DIR, "AS2_records.json"), "w",
              encoding="utf-8") as f:
        json.dump({"refs": refs, "records": RECORDS}, f,
                  ensure_ascii=False, indent=1)
    print("saved AS2_records.json (%d записей)" % len(RECORDS),
          flush=True)


if __name__ == "__main__":
    main()
