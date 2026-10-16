# -*- coding: utf-8 -*-
"""ACQ-1 driver (FROZEN 07.09.2026; v0.5 и слои не изменяются).

Learn-фаза: демонстрации verified-success w1 x2, wY x2 (решение 1
DESIGN) через КАНОНИЧЕСКИЙ v0.5-путь (cs1_driver.learn с ctx_extra,
как acq0_recorder). Пробы ПОСЛЕ learn-фазы: w1, w2, wX, wY, noise —
executor-only (опыт/знания не создаются), для P3 и D2.

Конфигурации: уровень (A0/A1/A2) x controls (clean/controls) x
реплики (r1/r2) = 12 прогонов (grid). Controls: D (dbg) и P (pulse)
инъецируются на learn-моменты (D: присутствие по плану [нет, есть,
нет, есть]; P: пульс-писатель в окне чтений). N (lock.n) — только
измерение (n_obs), в кандидаты НЕ входит (решение профессора:
HIDDEN n). Телеметрия observer.collect — кандидаты continuous.

Механизму (A1/A2) передаются episode_id, кандидаты и вердикт; имя
мира и GT НЕ передаются. Аудит: sha256 слоёв до/после каждого
прогона.

Режимы: python3 acq1_driver.py grid|perms (по умолчанию оба).
perms: 6 перестановок learn-порядка x A1/A2 x r1/r2 (P4b; learn-only).
"""
import glob
import hashlib
import itertools
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from acq1_mechanism import Mechanism  # noqa: E402
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
LOG = os.path.join(DIR, "ACQ1_run.log")

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
    "w2": (["a", "extra"], "present", "2"),
    "wX": (["a", "extra"], "present", "1"),
    "noise": (["a", "n"], "absent", "1"),
}
LEARN_DEFAULT = ["w1", "w1", "wY", "wY"]
PROBES = ["w1", "w2", "wX", "wY", "noise"]
D_PLAN = {1: False, 2: True, 3: False, 4: True}   # dbg присутствует?

LAYER_FILES = [
    "strategy/strategy.py", "update/update.py", "knowledge/knowledge.py",
    "experience/experience.py", "executor/executor.py",
    "evaluation/evaluation.py", "observer/observer.py",
    "observer/polygon_sensor.py", "storage/store.py",
]

PULSE_FILE = "/run/tsasvc.pulse"
DBG_FILE = "/run/tsasvc.dbg"


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
    for f in (DBG_FILE, "/run/tsasvc.envver", PULSE_FILE):
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


class PulseWriter(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._stop = threading.Event()

    def run(self):
        while not self._stop.is_set():
            try:
                with open(PULSE_FILE, "w", encoding="utf-8") as f:
                    f.write("pulse-%s" % time.time())
            except OSError:
                pass
            time.sleep(0.12)

    def stop(self):
        self._stop.set()


def read_raw(ctl):
    """Одиночное чтение кандидатов. Возвращает dict значений."""
    out = {"E": polygon_sensor.sensor_envfact()[4],
           "V": polygon_sensor.sensor_envver()[4],
           "S": polygon_sensor.sensor_symptom()[4]}
    if ctl:
        out["D"] = os.path.exists(DBG_FILE)
        p = None
        if os.path.exists(PULSE_FILE):
            with open(PULSE_FILE, encoding="utf-8") as f:
                p = f.read().strip()
        out["P"] = p
    return out


def read_candidates(ctl):
    """Двойное чтение с паузой -> стабильность. N — только n_obs."""
    t0 = read_raw(ctl)
    time.sleep(0.6)
    t1 = read_raw(ctl)
    n_obs = os.path.exists("/run/tsasvc.lock.n")
    cands = []
    cands.append({"name": "E", "value": t0["E"], "source_type": "flag",
                  "channel": "env", "stable": t0["E"] == t1["E"]})
    cands.append({"name": "V", "value": t0["V"], "source_type": "enum",
                  "channel": "env", "stable": t0["V"] == t1["V"]})
    cands.append({"name": "S", "value": t0["S"], "source_type": "enum",
                  "channel": "symptom", "stable": t0["S"] == t1["S"]})
    if ctl:
        cands.append({"name": "D", "value": t0["D"],
                      "source_type": "flag", "channel": "control",
                      "stable": t0["D"] == t1["D"]})
        cands.append({"name": "P", "value": t0["P"],
                      "source_type": "enum", "channel": "control",
                      "stable": t0["P"] == t1["P"]})
    return cands, n_obs


def telemetry_candidates(facts):
    """Непрерывные факты observer.collect (A0-наблюдение: телеметрия
    хоста гуляет). source_type=continuous -> отсев фильтром.
    raw_ref сохраняется для P6-восстановления (до raw)."""
    out = []
    for f in facts:
        v = f.get("value")
        if isinstance(v, (int, float)) or (
                isinstance(v, str) and v.replace(".", "", 1).isdigit()):
            out.append({"name": "T_%s_%s" % (f.get("subject"),
                                             f.get("property")),
                        "value": v, "source_type": "continuous",
                        "channel": "telemetry", "stable": True,
                        "raw_ref": (f.get("provenance") or {}).get(
                            "raw_ref")})
    return out[:6]


def mk_action(store, ctx, proposed_by):
    a = {"schema_version": "0.1",
         "action_id": "act_acq1_%s" % uuid.uuid4().hex[:8],
         "strategy_id": None, "proposed_by": proposed_by,
         "type": "command", "command": "fix-a",
         "args": {"goal": GOAL}, "permitted": True,
         "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "rationale": "ACQ-1"}
    if ctx is not None:
        a["args"]["ctx_extra"] = ctx
    store.append_action(a)
    return a


def kid_set(store):
    return set(v["knowledge_id"]
               for v in store.read_knowledge_versions_all())


def learn_moment(store, mech, world, ep, ctl, d_present):
    env_set(world)
    pw = None
    if ctl:
        if d_present:
            with open(DBG_FILE, "w", encoding="utf-8") as f:
                f.write("on")
        pw = PulseWriter()
        pw.start()
    cands, n_obs = read_candidates(ctl)
    if pw is not None:
        pw.stop()
    verdict_ok = None
    problem = "tsasvc.service inactive symptom=%s" % cands[2]["value"]
    facts = observer.collect(store)
    tele = telemetry_candidates(facts)
    ctx = polygon_sensor.sensor_envfact()[4]   # оператор выбирает E
    act = mk_action(store, ctx, "operator/learn")
    before = kid_set(store)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="acq1")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    created = kid_set(store) - before
    assert len(created) <= 1
    rec = {"episode_id": ep, "world": world,
           "signals": {"E": cands[0]["value"], "V": cands[1]["value"],
                       "S": cands[2]["value"]},
           "n_obs": n_obs, "verdict": outcome, "ok": ok,
           "d_present": d_present if ctl else None,
           "telemetry": tele,
           "knowledge": None}
    if created:
        kid = sorted(created)[0]
        kr = store.read_knowledge(kid)
        assert "applicable_when" not in kr and "condition" not in kr
        addr = strategy._addr_cmd_of(store, kr)
        rec["knowledge"] = {"knowledge_id": kid,
                            "fields": sorted(kr.keys()),
                            "content": kr.get("content"),
                            "derived_addr": {
                                "symptom": sorted(addr[0]) if addr else [],
                                "ctx": addr[1] if addr else None,
                                "command": addr[2] if addr else None}}
    if mech is not None:
        mech.on_learn(ep, cands, outcome)
    log({"event": "LEARN", "cfg": getattr(mech, "level", "A0") or "A0",
         "ep": ep, "world": world, "E": cands[0]["value"],
         "V": cands[1]["value"], "S": cands[2]["value"],
         "ok": ok, "outcome": outcome})
    return rec


def probe(store, mech, world, ep, ctl):
    env_set(world)
    cands, n_obs = read_candidates(ctl)
    act = mk_action(store, None, "acq1-probe")
    res = executor.execute(store, act)
    ok = stable_active()
    out = "success" if ok else (res.get("outcome") or "failure")
    if mech is not None:
        mech.on_probe(ep, cands, out)
    rec = {"episode_id": ep, "world": world,
           "signals": {"E": cands[0]["value"], "V": cands[1]["value"],
                       "S": cands[2]["value"]},
           "n_obs": n_obs, "verdict": out, "ok": ok}
    log({"event": "PROBE", "ep": ep, "world": world,
         "E": cands[0]["value"], "V": cands[1]["value"],
         "S": cands[2]["value"], "outcome": out})
    return rec


def fresh_store(name):
    d = os.path.join(DIR, "data_acq1_%s" % name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def run_config(level, ctl, rep, learn_order=None, probes=True,
               store_tag=None):
    learn_order = learn_order or LEARN_DEFAULT
    ctl_b = (ctl == "controls")          # строковый флаг -> bool
    tag = store_tag or "%s_%s_%s" % (level, ctl, rep)
    st = fresh_store(tag)
    mech = Mechanism(level) if level != "A0" else None
    audit_before = hash_layers()
    recs = []
    for i, world in enumerate(learn_order, start=1):
        recs.append(learn_moment(st, mech, world, "%s_m%d" % (rep, i),
                                 ctl_b, D_PLAN.get(i, False)))
    if probes:
        for world in PROBES:
            recs.append(probe(st, mech, world,
                              "%s_p_%s" % (rep, world), ctl_b))
    audit_after = hash_layers()
    assert audit_before == audit_after, "слои изменились в %s_%s_%s" % (
        level, ctl, rep)
    run = {"config": "%s_%s" % (level, ctl), "rep": rep,
           "learn_order": learn_order, "audit_same": True,
           "episodes": recs,
           "mechanism": mech.final() if mech is not None else None,
           "mechanism_records": mech.records if mech is not None else None}
    return run


def main_grid():
    out = []
    for level in ("A0", "A1", "A2"):
        for ctl in ("clean", "controls"):
            for rep in ("r1", "r2"):
                out.append(run_config(level, ctl, rep))
    with open(os.path.join(DIR, "ACQ1_records.json"), "w",
              encoding="utf-8") as f:
        json.dump({"runs": out}, f, ensure_ascii=False, indent=1,
                  default=str)
    print("grid done: %d runs -> ACQ1_records.json" % len(out), flush=True)
    for r in out:
        m = r["mechanism"]
        print("  %-14s %s condition=%s d1=%d d2=%d"
              % (r["config"], r["rep"],
                 m["condition"] if m else "-",
                 len(m["obs_d1"]) if m else 0,
                 len(m["obs_d2"]) if m else 0), flush=True)


def main_perms():
    orders = sorted(set(itertools.permutations(LEARN_DEFAULT)))
    out = []
    for level in ("A1", "A2"):
        for rep in ("r1", "r2"):
            for oi, order in enumerate(orders):
                run = run_config(level, "clean", rep,
                                 learn_order=list(order), probes=False,
                                 store_tag="perm_%s_%s_%d"
                                 % (level, rep, oi))
                m = run["mechanism"]
                out.append({"level": level, "rep": rep,
                            "order": list(order),
                            "condition": m["condition"],
                            "obs_d1": m["obs_d1"],
                            "success_count": m["success_count"]})
    with open(os.path.join(DIR, "ACQ1_PERM_records.json"), "w",
              encoding="utf-8") as f:
        json.dump({"perms": out}, f, ensure_ascii=False, indent=1,
                  default=str)
    print("perms done: %d runs -> ACQ1_PERM_records.json" % len(out),
          flush=True)
    for r in out:
        print("  %-3s %s %s -> %s" % (r["level"], r["rep"], r["order"],
                                      r["condition"]), flush=True)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if not os.path.exists(LOG):
        open(LOG, "w", encoding="utf-8").close()
    print("== ACQ-1 (FROZEN 07.09); mode=%s ==" % mode, flush=True)
    if mode in ("grid", "all"):
        main_grid()
    if mode in ("perms", "all"):
        main_perms()
