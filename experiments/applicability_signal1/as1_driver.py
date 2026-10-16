# -*- coding: utf-8 -*-
"""APPLICABILITY-SIGNAL-1 driver (FROZEN; measurement-only; 06.09).

Протокол: applicability_signal1/PROTOCOL.md. Регистратор: env →
чтение кандидатов (до действия) → фиксированное fix-a через
Executor; опыт/знания не создаются. Кандидаты: E, V, N, D, P, S, L.
Серии C1–C5 × повторы r1/r2. Миры: w1=[a] ver1; w2=[a,extra] ver2;
noise=[a,n]; dbg=[a]+/run/tsasvc.dbg (демон не читает);
pulse — файл, перезаписываемый драйвером (имитация внешнего
писателя; в C5 два чтения с паузой).

Использование: python3 as1_driver.py C1 C2 [C3 ...] (по умолчанию
все пять; каждый прогон пишет обе реплики серии).
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
from observer import sensors  # noqa: E402
from storage.store import Store  # noqa: E402

SVC = "tsasvc"
DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(DIR, "AS1_run.log")
ALL = []

SERIES = {
    "C1": ["w1"] * 8,
    "C2": ["w1"] * 3 + ["w2"] * 5,
    "C3": ["w1"] * 3 + ["noise"] + ["w1"] * 3 + ["noise"],
    "C4": ["w1"] * 2 + ["dbg"] * 3 + ["w1"] * 3,
    "C5": ["w1"] * 6,
}
GT = {"C1": [True] * 8,
      "C2": [True] * 3 + [False] * 5,
      "C3": [True] * 8,
      "C4": [True] * 8,
      "C5": [True] * 6}


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def _clear_flags():
    for p in glob.glob("/run/tsasvc.lock.*"):
        os.remove(p)


def env_set(world):
    _run(["systemctl", "stop", SVC])
    _clear_flags()
    for f in ["/run/tsasvc.dbg", "/run/tsasvc.envver",
              "/run/tsasvc.pulse"]:
        if os.path.exists(f):
            os.remove(f)
    if world == "w1":
        open("/run/tsasvc.lock.a", "w").close()
        open("/run/tsasvc.envver", "w").write("1")
    elif world == "w2":
        open("/run/tsasvc.lock.a", "w").close()
        open("/run/tsasvc.lock.extra", "w").close()
        open("/run/tsasvc.envver", "w").write("2")
    elif world == "noise":
        open("/run/tsasvc.lock.a", "w").close()
        open("/run/tsasvc.lock.n", "w").close()
        open("/run/tsasvc.envver", "w").write("1")
    elif world == "dbg":
        open("/run/tsasvc.lock.a", "w").close()
        open("/run/tsasvc.dbg", "w").write("on")
        open("/run/tsasvc.envver", "w").write("1")
    else:
        raise ValueError(world)
    _run(["systemctl", "reset-failed", SVC])


def read_candidates():
    """Все кандидаты ДО действия."""
    e = polygon_sensor.sensor_envfact()[4]      # absent/present
    v = polygon_sensor.sensor_envver()[4]       # 1/2
    n = os.path.exists("/run/tsasvc.lock.n")
    d = os.path.exists("/run/tsasvc.dbg")
    p = None
    if os.path.exists("/run/tsasvc.pulse"):
        with open("/run/tsasvc.pulse", encoding="utf-8") as f:
            p = f.read().strip()
    s = polygon_sensor.sensor_symptom()[4]
    l1 = sensors.sensor_load()[4]
    return {"E": e, "V": v, "N": n, "D": d, "P": p, "S": s, "L": l1}


def pulse_tick():
    with open("/run/tsasvc.pulse", "w", encoding="utf-8") as f:
        f.write("pulse-%s" % time.time())


def run_series(name, rep, store):
    worlds = SERIES[name]
    gt = GT[name]
    rows = []
    for i, world in enumerate(worlds):
        env_set(world)
        cand1 = read_candidates()
        if name == "C5":
            pulse_tick()
            time.sleep(0.6)
            cand2 = read_candidates()
            cand1["P1"] = cand1.pop("P")
            cand1["P2"] = cand2["P"]
        # фиксированное действие fix-a (полный канал, результат)
        aid = "act_%s_%s_%d_%s" % (name, rep, i + 1,
                                    uuid.uuid4().hex[:6])
        action = {"schema_version": "0.1", "action_id": aid,
                  "strategy_id": None, "proposed_by": "as1",
                  "type": "command", "command": "fix-a",
                  "args": {}, "permitted": True,
                  "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                  "rationale": "AS-1"}
        res = executor.execute(store, action)
        row = {"series": name, "rep": rep, "ep": i + 1, "world": world,
               "gt": gt[i], "cand": cand1,
               "outcome": res.get("outcome"),
               "exit": res.get("exit_code"),
               "svc_after": (res.get("state_after") or {}).get(
                   "service:tsasvc.state")}
        rows.append(row)
        ALL.append(row)
        log({"series": name, "rep": rep, "ep": i + 1, "world": world,
             "gt": gt[i], "E": cand1.get("E"), "V": cand1.get("V"),
             "N": cand1.get("N"), "D": cand1.get("D"),
             "S": cand1.get("S"), "P": cand1.get("P1", cand1.get("P")),
             "L": cand1.get("L"), "exit": res.get("exit_code"),
             "svc_after": row["svc_after"]})
    return rows


def fresh_store(name):
    d = os.path.join(DIR, "data_as1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def main():
    series = sys.argv[1:] or list(SERIES.keys())
    if not os.path.exists(LOG):
        open(LOG, "w", encoding="utf-8").close()
    print("== APPLICABILITY-SIGNAL-1 (FROZEN); серии: %s ==" % series,
          flush=True)
    all_rows = []
    path = os.path.join(DIR, "AS1_candidates.json")
    if os.path.exists(path):          # накопление (партии)
        try:
            all_rows = json.load(open(path, encoding="utf-8"))
        except ValueError:
            all_rows = []
    for name in series:
        for rep in ("r1", "r2"):
            st = fresh_store("%s_%s" % (name, rep))
            rows = run_series(name, rep, st)
            all_rows.extend(rows)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_rows, f, ensure_ascii=False, indent=1)
    print("saved %s (%d эпизодов)" % (path, len(all_rows)), flush=True)


if __name__ == "__main__":
    main()
