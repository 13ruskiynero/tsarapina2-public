# -*- coding: utf-8 -*-
"""EVENT-SUFFICIENCY-1 / E1+E2 (маршрут A, после E0: граница
наблюдателя установлена — полные каналы stale/noise идентичны).

E1 (наблюдаемость): 'extra' становится ОТДЕЛЬНЫМ наблюдаемым фактом
среды (sensor_envfact: tsasvc.extra present/absent; НЕ симптом; 'n'
остаётся скрытым). Вопрос: возникает ли различие stale/noise ДО
первого действия?
  ожидание: stale: env_extra=present (обучение: absent) → изменение
  мира наблюдаемо; noise: env_extra=absent == обучение → сигнала нет.

E2 (контекст применимости): фиксация контекста проверки знания:
драйвер кладёт envfact в action.args (ctx_extra) при learn;
восстановимость knowledge→experience→action.args; «вне контекста
проверки» = ctx_now != ctx_learn: stale 6/6, noise 6/6 (0).
Механизм (Strategy) НЕ трогается — только фиксация и измерение.

Серии: как в E0-target (learn a в старом мире; 6 эпизодов класса;
F0; без declare/exploration; полный канал через Executor).
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
sys.path.insert(0, os.path.join(BASE, "experiments", "stale_exact1"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402
from strategy_v5 import suggest_v5  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "E1_TARGET_run.log")
N = 6


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(extra_flag):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    open("/run/tsasvc.lock.a", "w").close()
    if extra_flag:
        open("/run/tsasvc.lock.%s" % extra_flag, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def env_clean():
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    if svc_state() != "active":
        return False
    time.sleep(1.5)
    return svc_state() == "active"


def env_extra():
    """E1-сенсор: extra present/absent."""
    return polygon_sensor.sensor_envfact()[4]


def mk_action(store, command, proposed_by, extra_ctx=None):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "E1-TARGET"}
    if extra_ctx is not None:
        a["args"]["ctx_extra"] = extra_ctx
    store.append_action(a)
    return a


def learn_a(store, ep):
    """learn fix-a в старом мире; фиксация контекста (E2): ctx_extra
    в args действия (как наблюдалось в момент проверки)."""
    env_clean()
    ctx = env_extra()  # absent (старый мир)
    problem = "tsasvc.service inactive symptom=%s" % \
        polygon_sensor.sensor_symptom()[4]
    facts = observer.collect(store)
    act = mk_action(store, "fix-a", proposed_by="operator/learn",
                    extra_ctx=ctx)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem=problem, observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="e1-target")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN_A", "ok": ok, "ctx_extra_learn": ctx})
    return ok, ctx


def class_episode(store, cls, flag, i, ctx_learn):
    env_set(flag)
    # E1: факт среды ДО первого действия
    ctx_now = env_extra()
    # симптом до действия
    sym_now = polygon_sensor.sensor_symptom()[4]
    problem = "tsasvc.service inactive symptom=%s" % sym_now
    sug = suggest_v5(store, {"problem": problem}, mech="F0",
                     by="e1-target")
    cmd = None
    if sug["strategy_id"] == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
    act = mk_action(store, cmd or "fix-a", proposed_by="e1/%s" % cls)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=observer.collect(store),
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="e1-target")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else outcome)
    rec = {
        "ep": "e1_%s_%d" % (cls, i), "class": cls,
        "symptom_before": sym_now,
        "ctx_extra_before_action": ctx_now,
        "ctx_extra_learn": ctx_learn,
        "outside_learned_context": ctx_now != ctx_learn,
        "cmd": cmd, "outcome": outcome,
        "svc_after": (res.get("state_after") or {}).get(
            "service:tsasvc.state"),
    }
    log({"ep": rec["ep"], "event": "EPISODE", "data": rec})
    return rec


def fresh_store(name):
    d = os.path.join(DIR, "data_e1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def ctx_recoverable(store, ep):
    """E2: восстановимость контекста по цепочке knowledge → опыт →
    action.args.ctx_extra (последнее update-знание)."""
    kids = {}
    for v in store.read_knowledge_versions_all():
        kids.setdefault(v["knowledge_id"], v)
    latest = None
    for v in kids.values():
        if v["status"] in ("active", "conflicted"):
            if latest is None or v["created_at"] > latest["created_at"]:
                latest = v
    if latest is None:
        return None
    for eid in latest.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        for aid in exp.get("actions", []):
            a = store.read_action(aid)
            if a and "ctx_extra" in (a.get("args") or {}):
                return a["args"]["ctx_extra"]
    return None


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== EVENT-SUFFICIENCY-1 / E1+E2 (маршрут A) ==", flush=True)
    env_clean()
    out = {}
    for cls, flag in (("stale", "extra"), ("noise", "n")):
        st = fresh_store(cls)
        ok_l, ctx_learn = learn_a(st, "learn_%s" % cls)
        assert ok_l
        chs = [class_episode(st, cls, flag, i, ctx_learn)
               for i in range(1, N + 1)]
        rec_ctx = ctx_recoverable(st, "recover_%s" % cls)
        out[cls] = {"learn_ctx": ctx_learn, "episodes": chs,
                    "ctx_recovered": rec_ctx}
        log({"event": "CLASS_DONE", "class": cls,
             "ctx_recovered": rec_ctx})
    # сводка
    stale_eps = out["stale"]["episodes"]
    noise_eps = out["noise"]["episodes"]
    print("== СВОДКА E1 ==")
    print("stale: env_extra ДО действия present: %d/6; вне контекста "
          "обучения: %d/6"
          % (sum(1 for e in stale_eps
                 if e["ctx_extra_before_action"] == "present"),
             sum(1 for e in stale_eps if e["outside_learned_context"])))
    print("noise: env_extra ДО действия present: %d/6; вне контекста "
          "обучения: %d/6"
          % (sum(1 for e in noise_eps
                 if e["ctx_extra_before_action"] == "present"),
             sum(1 for e in noise_eps if e["outside_learned_context"])))
    print("== СВОДКА E2 (восстановимость контекста) ==")
    print("stale: ctx восстановлен: %r; noise: ctx восстановлен: %r"
          % (out["stale"]["ctx_recovered"],
             out["noise"]["ctx_recovered"]))
    with open(os.path.join(DIR, "E1_TARGET_results.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("saved E1_TARGET_results.json", flush=True)


if __name__ == "__main__":
    main()
