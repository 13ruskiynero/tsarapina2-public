# -*- coding: utf-8 -*-
"""EVENT-SUFFICIENCY-1 / E0-TARGET (06.09.2026; FREEZE профессора).

Контрольная пара классов (оба: symptom=a, fix-a -> failure, ПОЛНЫЙ
канал через тот же Executor; v0.3/F0: без declare, без exploration,
только запись фактов):

  STALE:     a + extra (скрытое устаревание мира; fix-a не лечит)
  NOISE-real: a + n    (скрытый шумовой фактор; fix-a его не снимает,
                        'n' не виден Observer; мир НЕ устарел)

Граница протокола (записана до прогона):
  НЕ считать сам факт failure достаточным сигналом: failure — то,
  что разлагается (failure = stale | noise).

Измерение: полный канал каждого эпизода (state_before/state_after —
9 сенсоров, stdout/stderr/exit, вердикт evaluation, action).
Серии: learn a (старый мир) → 6 эпизодов класса на отдельном сторе.
Критерий: если после нормализации каналы STALE ≈ NOISE-real и
различие класса недоступно до первого действия → информационная
граница наблюдателя (H-E0 подтверждена) → маршрут A (E1/E2).
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
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402
from strategy_v5 import suggest_v5  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "E0_TARGET_run.log")
N = 6


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(extra_flag):
    """Мир: a + extra_flag ('extra'|'n'|None). Оба флага скрыты от
    симптом-сенсора."""
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


def symptom_now():
    from observer import polygon_sensor
    return polygon_sensor.sensor_symptom()[4]


def mk_action(store, command, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "E0-TARGET"}
    store.append_action(a)
    return a


def learn_a(store, ep):
    """learn: fix-a в СТАРОМ мире (без скрытых флагов)."""
    env_clean()
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, "fix-a", proposed_by="operator/learn")
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    exp_full = experience.build(
        problem=problem, observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="e0-target")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else ev["outcome"])
    log({"ep": ep, "event": "LEARN_A", "ok": ok})
    return ok


def class_episode(store, cls, flag, i, mech="F0"):
    """Эпизод класса: среда a+flag; контур (F0) выбирает fix-a по
    exact-знанию; исполнение через Executor (полный канал);
    запись фактов; БЕЗ declare и exploration."""
    env_set(flag)
    facts = observer.collect(store)
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    sug = suggest_v5(store, {"problem": problem}, mech=mech,
                     by="e0-target")
    rec = {"ep": "e0_%s_%d" % (cls, i), "class": cls, "flag": flag,
           "symptom": symptom_now(),
           "strategy": sug["strategy_id"],
           "rule": sug["rationale"][0]["rule"] if sug["rationale"] else ""}
    cmd = None
    if sug["strategy_id"] == "S2" and sug.get("candidate_actions"):
        cmd = sug["candidate_actions"][0]["command"]
    act = mk_action(store, cmd or "fix-a",
                    proposed_by="e0/%s" % cls)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    # полный канал (нормализованный): все поля result + вердикт
    channel = {
        "class": cls,
        "command": act["command"],
        "exit_code": res.get("exit_code"),
        "stdout": res.get("stdout") or "",
        "stderr": res.get("stderr") or "",
        "state_before": res.get("state_before") or {},
        "state_after": res.get("state_after") or {},
        "verdict": outcome,
        "symptom_before": (res.get("state_before") or {}).get(
            "tsasvc.symptom"),
        "symptom_after": (res.get("state_after") or {}).get(
            "tsasvc.symptom"),
        "svc_before": (res.get("state_before") or {}).get(
            "service:tsasvc.state"),
        "svc_after": (res.get("state_after") or {}).get(
            "service:tsasvc.state"),
    }
    # опыт (для полноты журнала; без declare)
    exp_full = experience.build(
        problem=problem, observations=facts, actions=[act["action_id"]],
        result_ref=res["result_id"], machine="e0-target")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"],
                 "success" if ok else outcome)
    rec.update({"cmd": cmd, "ok": ok, "outcome": outcome})
    log({"ep": rec["ep"], "event": "EPISODE", "data": channel})
    return channel


def fresh_store(name):
    d = os.path.join(DIR, "data_e0_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== EVENT-SUFFICIENCY-1 / E0-TARGET ==", flush=True)
    print("Граница протокола: failure сам по себе НЕ сигнал;", flush=True)
    print("failure = stale | noise (разлагается).", flush=True)
    env_clean()
    out = {}
    for cls, flag in (("stale", "extra"), ("noise", "n")):
        st = fresh_store(cls)
        assert learn_a(st, "learn_%s" % cls)
        chs = [class_episode(st, cls, flag, i) for i in range(1, N + 1)]
        out[cls] = chs
        log({"event": "CLASS_DONE", "class": cls, "n": len(chs)})
    summary = json.dumps(out, ensure_ascii=False)
    log({"event": "summary", "data": out})
    with open(os.path.join(DIR, "E0_TARGET_channels.json"), "w",
              encoding="utf-8") as f:
        f.write(summary)
    print("saved E0_TARGET_channels.json + E0_TARGET_run.log", flush=True)


if __name__ == "__main__":
    main()
