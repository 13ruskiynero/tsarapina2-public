# -*- coding: utf-8 -*-
"""SUFFICIENCY-2 driver (регистратор; FROZEN 06.09.2026).

Измерительный прогон: контур v0.5, НО без переключений — каждый
эпизод S2→fix-a; переходы не исполняются (регистрация офлайн в
s2_analyze). Ячейки: noise_low/noise_high/noise_var/stale_low/
stale_high/stale_var; rep r1|r2 (шум-генератор: seed = crc32(cell+rep)
— таблица фиксирована кодом, НЕ меняется после старта).

Мир эпизода: noise: a или a+n (p); stale: эп.1-30 как noise,
эп.31-60: a+extra (w2). p: low=0.05; high=0.35; var: эпохи по 15
(0.05/0.35 попеременно, начиная 0.05).

Использование: python3 s2_driver.py noise_low:r1 noise_low:r2 ...
"""
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import time
import uuid
import zlib

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
P = {"low": 0.05, "high": 0.35, "var": None}
N_EPISODES = 60
T0 = 30
ANOMALIES = []


def p_at(cell, t):
    """Вероятность шума эпизода t (1-based). variable: эпохи 15."""
    if P[cell] is not None:
        return P[cell]
    epoch = (t - 1) // 15
    return 0.05 if epoch % 2 == 0 else 0.35


def seed_of(cell, rep):
    return zlib.crc32(("%s:%s" % (cell, rep)).encode("utf-8"))


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def env_set(flags):
    _run(["systemctl", "stop", SVC])
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)
    for f in flags:
        open("/run/tsasvc.lock.%s" % f, "w").close()
    _run(["systemctl", "reset-failed", SVC])


def svc_state():
    return _run(["systemctl", "is-active", SVC]).stdout.strip()


def stable_active():
    """Устойчивый успех: active сейчас; если active — подтвердить
    через 1.0с (окно Type=simple; при non-success проверка быстрая)."""
    if svc_state() != "active":
        return False
    time.sleep(1.0)
    return svc_state() == "active"


def ctx_now():
    return polygon_sensor.sensor_envfact()[4]


def symptom_now():
    return polygon_sensor.sensor_symptom()[4]


def mk_action(store, command, proposed_by, ctx):
    a = {"schema_version": "0.1",
         "action_id": "act_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": command,
         "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "SUFFICIENCY-2"}
    store.append_action(a)
    return a


def save_episode(store, problem, facts, act, result_id, outcome):
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=result_id,
        machine="sufficiency-2")
    experience.save(store, exp_full)
    update.apply(store, exp_full["experience_id"], outcome)


def learn_a(store):
    env_set(["a"])
    problem = "tsasvc.service inactive symptom=%s" % symptom_now()
    facts = observer.collect(store)
    act = mk_action(store, "fix-a", proposed_by="operator/learn",
                    ctx=ctx_now())
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    save_episode(store, problem, facts, act, res["result_id"],
                 "success" if ok else ev["outcome"])
    return ok


def run_series(cell, rep):
    """Одна серия: learn + 60 эпизодов S2→fix-a. Возвращает dict."""
    st = fresh_store("s2_%s_%s" % (cell, rep))
    assert learn_a(st), "learn failed"
    rng = random.Random(seed_of(cell, rep))
    outcomes = []
    anomaly_events = []
    for t in range(1, N_EPISODES + 1):
        # мир эпизода
        if cell.startswith("stale") and t > T0:
            env_set(["a", "extra"])          # w2: fix-a не лечит
        else:
            p = p_at(cell.split("_")[1], t)   # low/high/var
            if rng.random() < p:
                env_set(["a", "n"])          # скрытый шум
            else:
                env_set(["a"])               # исправный мир
        problem = "tsasvc.service inactive symptom=%s" % symptom_now()
        ctx = ctx_now()
        # контур v0.5: suggest; переход/аномалия НЕ исполняются
        sug = strategy.suggest(st, {"problem": problem}, ctx_now=ctx,
                                by="s2-registrator")
        sid = sug["strategy_id"]
        anomaly = sid != "S2" or sug.get("exploration") or \
            sug.get("event") == "E2_TRANSITION"
        if anomaly:
            anomaly_events.append({"t": t, "strategy": sid,
                                   "exploration": sug.get("exploration"),
                                   "event": sug.get("event")})
        # фиксированное действие fix-a (протокол: регистратор)
        act = mk_action(st, "fix-a", proposed_by="s2/%s" % cell, ctx=ctx)
        res = executor.execute(st, act)
        ok = stable_active()
        ev = evaluation.evaluate(st, res["result_id"], GOAL)
        out = "success" if ok else ev["outcome"]
        save_episode(st, problem, observer.collect(st), act,
                     res["result_id"], out)
        outcomes.append(out)
        print("%s %s t=%d %s%s" % (cell, rep, t,
                                   "OK" if ok else out,
                                   " [ANOMALY]" if anomaly else ""),
              flush=True)
    rec = {"cell": cell, "rep": rep, "seed": seed_of(cell, rep),
           "outcomes": outcomes,
           "anomalies": anomaly_events}
    with open(os.path.join(DIR, "S2_series_%s_%s.json" % (cell, rep)),
              "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    return rec


def fresh_store(name):
    d = os.path.join(DIR, "data_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    pairs = sys.argv[1:]
    if not pairs:
        print("usage: s2_driver.py <cell:rep> ...", flush=True)
        return
    print("== SUFFICIENCY-2 (FROZEN); серии: %s ==" % pairs, flush=True)
    all_recs = {}
    for pair in pairs:
        cell, rep = pair.split(":")
        all_recs[pair] = run_series(cell, rep)
    print("== DONE ==", flush=True)
    for pair in pairs:
        r = all_recs[pair]
        s = "".join("s" if o == "success" else "f" for o in r["outcomes"])
        print("%s %s" % (pair, s), flush=True)


if __name__ == "__main__":
    main()
