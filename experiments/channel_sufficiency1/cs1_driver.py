# -*- coding: utf-8 -*-
"""CHANNEL-SUFFICIENCY-1 driver (FROZEN; measurement-only; v0.5).

Протокол: channel_sufficiency1/PROTOCOL.md. Регистратор: действие
fix-a фиксировано; suggest v0.5 записывается, не управляет;
переходы не исполняются. Каналы эпизода: consequence (полный
result), env_extra ДО действия, environment_version ДО действия,
suggest-статус. Миры: w1=[a], w2=[a,extra], noise=[a,n]; версия:
w1/noise=1, w2=2 (/run/tsasvc.envver, демон не читает).

Сторы: S0 (learn legacy без ctx — F0) и S1 (learn с ctx_extra —
F1/F2/F3); на каждом: контроль w1×2, STALE×6, NOISE×6.
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
LOG = os.path.join(DIR, "CS1_run.log")
CHANNELS = []


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(world):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    flags = {"w1": ["a"], "w2": ["a", "extra"], "noise": ["a", "n"]}[world]
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    ver = "2" if world == "w2" else "1"
    with open("/run/tsasvc.envver", "w", encoding="utf-8") as f:
        f.write(ver)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def mk_action(store, command, proposed_by, ctx=None):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "CS-1"}
    if ctx is not None:
        a["args"]["ctx_extra"] = ctx
    store.append_action(a)
    return a


def save_episode(store, problem, facts, act, result_id, outcome):
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=result_id,
        machine="cs1")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"], outcome)


def learn(store, ep, with_ctx=True):
    """learn fix-a в w1; with_ctx=False — legacy (без ctx_extra)."""
    env_set("w1")
    problem = "tsasvc.service inactive symptom=%s" % \
        polygon_sensor.sensor_symptom()[4]
    facts = observer.collect(store)
    act = mk_action(store, "fix-a", proposed_by="operator/learn",
                    ctx=polygon_sensor.sensor_envfact()[4]
                    if with_ctx else None)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    save_episode(store, problem, facts, act, res["result_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN", "with_ctx": with_ctx, "ok": ok})
    return ok


def episode(store, world, ep, series):
    """Регистратор-эпизод: каналы ДО действия, фиксированное
    fix-a, полный consequence."""
    env_set(world)
    # каналы ДО первого действия
    env_extra_before = polygon_sensor.sensor_envfact()[4]
    env_ver_before = polygon_sensor.sensor_envver()[4]
    symptom_before = polygon_sensor.sensor_symptom()[4]
    problem = "tsasvc.service inactive symptom=%s" % symptom_before
    # suggest v0.5 (запись; не управляет)
    ctx = polygon_sensor.sensor_envfact()[4]
    sug = strategy.suggest(store, {"problem": problem}, ctx_now=ctx,
                            by="cs1-registrator")
    sid = sug["strategy_id"]
    # фиксированное действие
    act = mk_action(store, "fix-a", proposed_by="cs1/%s" % ep,
                    ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    facts = observer.collect(store)
    save_episode(store, problem, facts, act, res["result_id"], outcome)
    ch = {
        "ep": ep, "series": series, "world": world,
        "channels": {
            "F1_env_extra_before": env_extra_before,
            "F3_env_version_before": env_ver_before,
            "symptom_before": symptom_before,
            "consequence": {
                "exit_code": res.get("exit_code"),
                "stdout": (res.get("stdout") or "")[:40],
                "stderr": (res.get("stderr") or "")[:60],
                "svc_before": (res.get("state_before") or {}).get(
                    "service:tsasvc.state"),
                "svc_after": (res.get("state_after") or {}).get(
                    "service:tsasvc.state"),
                "sym_before": (res.get("state_before") or {}).get(
                    "tsasvc.symptom"),
                "sym_after": (res.get("state_after") or {}).get(
                    "tsasvc.symptom"),
                "outcome": outcome,
            },
            "suggest_strategy": sid,
            "ctx_now": ctx,
        },
        "ok": ok,
    }
    CHANNELS.append(ch)
    log({"ep": ep, "series": series, "event": "EPISODE", "world": world,
         "ok": ok, "outcome": outcome, "suggest": sid,
         "env_extra": env_extra_before, "env_version": env_ver_before})
    return ch


def fresh_store(name):
    d = os.path.join(DIR, "data_cs1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def run_store(store_name, with_ctx, prefix):
    st = fresh_store(store_name)
    learn(st, "%s_learn" % prefix, with_ctx=with_ctx)
    for i in (1, 2):
        episode(st, "w1", "%s_w1_%d" % (prefix, i), "%s-CTRL" % prefix)
    for i in range(1, 7):
        episode(st, "w2", "%s_st_%d" % (prefix, i), "%s-STALE" % prefix)
    for i in range(1, 7):
        episode(st, "noise", "%s_no_%d" % (prefix, i),
                "%s-NOISE" % prefix)


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== CHANNEL-SUFFICIENCY-1 (FROZEN; measurement-only) ==",
          flush=True)
    run_store("S0", with_ctx=False, prefix="F0")
    run_store("S1", with_ctx=True, prefix="F1")
    with open(os.path.join(DIR, "CS1_channels.json"), "w",
              encoding="utf-8") as f:
        json.dump(CHANNELS, f, ensure_ascii=False, indent=1)
    print("saved CS1_channels.json (%d эпизодов)" % len(CHANNELS),
          flush=True)


if __name__ == "__main__":
    main()
