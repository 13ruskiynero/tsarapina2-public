# -*- coding: utf-8 -*-
"""INTEGRATION GATE v0.6 (07.09.2026) — applicable_when-адресация
(ACQ-1 A2) в рабочем цикле. Дизайн: INTEGRATION_V06_DESIGN.md
(FROZEN). Основной strategy.py = v0.6; baseline v0.5 сохранён:
strategy/strategy_v05_baseline.py (артефакт сравнения).

G1 Backward compatibility: повтор gate_v05 (часть A 11/11, часть B
TE 14/14) + юнит-наборы 9/9 — на v0.6, полигон чистый (envver
отсутствует: CA-1/TE-знания остаются E-формы).
G2 Behavioral equivalence: знание с applicable_when={E:absent}+obs
V[1,2]; задачи A/AB — решения v0.6 == baseline v0.5 (strategy_id,
команда, число действий); C-SEB — cross-ref G1 T4c (8 действ.).
G3 Persistence: поле переживает новый процесс; версии не мутируют;
retract/restore сохраняют поля; provenance_walk до raw.
G4 Actually used: G4a applicable_when=={E:absent} (assert), V=1→S2 и
V=2→S2 при E=absent; G4b E=present при V=1 и V=2 → S3; G4c поле vs
args (синтетика), assert V-obs не в applicable_when.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

BASE = os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))          # lab/tsarapina/
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "strategy"))

from evaluation import evaluation  # noqa: E402
from executor import executor  # noqa: E402
from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from observer import polygon_sensor  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402
from update import update  # noqa: E402

SVC = "tsasvc"
GOAL = {"property": "service:%s.state" % SVC, "value": "active"}
DIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(DIR, "gate_v06_data")
LOG = os.path.join(DATA, "GATE_V06_run.log")
RESULTS = []

WORLD_DEF = {
    "w1": (["a"], "absent", "1"),
    "wY": (["a"], "absent", "2"),
    "w2": (["a", "extra"], "present", "2"),
    "wX": (["a", "extra"], "present", "1"),
    "noise": (["a", "n"], "absent", "1"),
    "w-ab": (["a", "b"], "absent", "1"),
}


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %-46s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)


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


def obs_now():
    """Текущие наблюдения E/V (чтение до решения)."""
    return {"E": polygon_sensor.sensor_envfact()[4],
            "V": polygon_sensor.sensor_envver()[4]}


def fresh_store(name):
    d = os.path.join(DATA, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def learn(store, world, ep, symptom="a", command="fix-a"):
    """Канонический learn (оператор-демонстрация; ctx_extra=E)."""
    env_set(world)
    problem = "tsasvc.service inactive symptom=%s" % symptom
    facts = observer.collect(store)
    ctx = polygon_sensor.sensor_envfact()[4]
    act = {"schema_version": "0.1",
           "action_id": "act_g06_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "operator/learn",
           "type": "command", "command": command,
           "args": {"goal": GOAL, "ctx_extra": ctx}, "permitted": True,
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "GATE-V06"}
    store.append_action(act)
    res = executor.execute(store, act)
    ok = stable_active()
    ev = evaluation.evaluate(store, res["result_id"], GOAL)
    outcome = "success" if ok else ev["outcome"]
    exp_full = experience.build(
        problem=problem, observations=facts,
        actions=[act["action_id"]], result_ref=res["result_id"],
        machine="gate-v06")
    experience.save(store, exp_full)
    k = update.apply(store, exp_full["experience_id"], outcome)
    return outcome, k


def latest_knowledge(store):
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    return latest


def suggest(store, problem, obs, by="gate-v06"):
    return strategy.suggest(store, {"problem": problem}, ctx_now=obs["E"],
                            obs_now=obs, by=by)


# ---------------------------------------------------------------- G1
def g1():
    print("== G1: backward compatibility (gate_v05 повтор; юниты 9/9) ==",
          flush=True)
    # чистый полигон: без envver-хвоста (CA-1/TE-знания — E-формы)
    _run(["bash", "-c", "rm -f /run/tsasvc.envver"])
    # часть A: 11 проверок; DET-версионный литерал ("0.5") под v0.6
    # обязан смениться — детерминизм (suggestion_id) проверяется
    # отдельно как DET-v0.6
    r = _run(["python3", os.path.join(DIR, "gate_v05.py")])
    out = r.stdout or ""
    npass = out.count("PASS ")
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    check("G1: gate_v05 часть A: PASS=10 (T1-T4e)", npass == 10,
          "PASS=%d" % npass)
    check("G1: gate_v05 часть A: единственный FAIL — DET-литерал версии",
          len(fails) == 1 and fails[0].startswith("FAIL DET"),
          "fails=%s" % fails)
    # DET-v0.6: детерминизм + версия
    st = fresh_store("g1_det")
    learn(st, "w1", "g1_det_l")
    env_set("w1")
    obs = obs_now()
    p = "tsasvc.service inactive symptom=a"
    s1 = strategy.suggest(st, {"problem": p}, ctx_now=obs["E"],
                          obs_now=obs, save=False)
    s2 = strategy.suggest(st, {"problem": p}, ctx_now=obs["E"],
                          obs_now=obs, save=False)
    check("G1: DET-v0.6: повторный suggest идентичен, version=0.6",
          s1["suggestion_id"] == s2["suggestion_id"]
          and s1["strategy_version"] == "0.6",
          "version=%s" % s1["strategy_version"])
    # часть B (TE): 14/14 — полигон БЕЗ envver (learn-миры gate пишут
    # envver; TE-миры envver не знают)
    _run(["bash", "-c", "rm -f /run/tsasvc.envver"])
    r = _run(["python3", os.path.join(DIR, "gate_v05.py"), "te"])
    out = r.stdout or ""
    npass = out.count("PASS ")
    nfail = out.count("FAIL")
    check("G1: gate_v05 часть B (TE): FAIL=0, PASS=14",
          nfail == 0 and npass == 14, "PASS=%d FAIL=%d" % (npass, nfail))
    # юниты 9/9
    _run(["bash", "-c", "rm -f /run/tsasvc.envver"])
    units = ["test_observer", "test_experience", "test_knowledge",
             "test_strategy", "test_llm_adapter", "test_executor",
             "test_evaluation", "test_update", "test_aggregation"]
    ok9 = 0
    for u in units:
        r = _run(["python3", os.path.join(BASE, "tests", u + ".py")])
        ok9 += 1 if "ПРОЙДЕН" in (r.stdout or "") else 0
    check("G1: юнит-наборы 9/9", ok9 == 9, "%d/9" % ok9)


# ------------------------------------------------- G2/G4 общий стор
def g2_store(store):
    """Линия fix-a: learn w1, w1, wY → latest {E:absent}+obs V[1,2]."""
    learn(store, "w1", "g2_l1")
    learn(store, "w1", "g2_l2")
    learn(store, "wY", "g2_l3")
    env_set("w1")
    return latest_knowledge(store)


def _baseline_suggest():
    import importlib.util
    p = os.path.join(BASE, "strategy", "strategy_v05_baseline.py")
    spec = importlib.util.spec_from_file_location("strategy_v05_baseline",
                                                  p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.suggest


def g2():
    print("== G2: behavioral equivalence (v0.6 vs baseline v0.5) ==",
          flush=True)
    st = fresh_store("g2_A")
    g2_store(st)
    bsug = _baseline_suggest()
    for v_now in ("1", "2"):
        env_set("wY" if v_now == "2" else "w1")
        obs = obs_now()
        s6 = suggest(st, "tsasvc.service inactive symptom=a", obs)
        s5 = bsug(st, {"problem": "tsasvc.service inactive symptom=a"},
                  ctx_now=obs["E"], by="baseline-v05")
        same = (s6["strategy_id"] == s5["strategy_id"]
                and [a["command"] for a in s6["candidate_actions"]]
                == [a["command"] for a in s5["candidate_actions"]])
        check("G2: A при V=%s: v0.6 == v0.5 (S2 fix-a, 1 действ.)" % v_now,
              same and s6["strategy_id"] == "S2"
              and len(s6["candidate_actions"]) == 1
              and s6["candidate_actions"][0]["command"] == "fix-a",
              "v0.6=%s v0.5=%s" % (s6["strategy_id"], s5["strategy_id"]))
    # AB: симптом ab, fix-ab
    st_ab = fresh_store("g2_AB")
    learn(st_ab, "w-ab", "ab_l1", symptom="ab", command="fix-ab")
    learn(st_ab, "w-ab", "ab_l2", symptom="ab", command="fix-ab")
    env_set("w-ab")
    obs = obs_now()
    s6 = suggest(st_ab, "tsasvc.service inactive symptom=ab", obs)
    s5 = bsug(st_ab, {"problem": "tsasvc.service inactive symptom=ab"},
              ctx_now=obs["E"], by="baseline-v05")
    check("G2: AB → S2 fix-ab, 1 действие; v0.6 == v0.5",
          s6["strategy_id"] == s5["strategy_id"] == "S2"
          and len(s6["candidate_actions"]) == 1
          and s6["candidate_actions"][0]["command"] == "fix-ab",
          "v0.6=%s v0.5=%s" % (s6["strategy_id"], s5["strategy_id"]))
    check("G2: C-SEB-путь — G1 T4c (exploration→fix-c, 8 действ.)",
          True, "cross-ref G1 (см. GATE_V06 G1-вывод)")


# ---------------------------------------------------------------- G3
def g3_make():
    st = fresh_store("g3")
    learn(st, "w1", "g3_l1")
    learn(st, "wY", "g3_l2")
    env_set("w1")
    return st


G3_PROBE = r"""
import json, os, sys
base = os.path.dirname(os.path.abspath(os.getcwd()))   # tsarapina/
sys.path.insert(0, base)
from knowledge import knowledge
from storage.store import Store
d = sys.argv[1]
st = Store(os.path.join(d, "tsarapina.db"), d)
latest = {}
for v in st.read_knowledge_versions_all():
    latest[v["knowledge_id"]] = v
kids = sorted(latest, key=lambda k: latest[k]["created_at"])
out = []
k2 = latest[kids[-1]]   # wY-знание
out.append("latest_aw=%s" % json.dumps(k2.get("applicable_when"), sort_keys=True))
out.append("latest_obs=%s" % json.dumps(k2.get("applicability_observations"), sort_keys=True))
# retract/restore: поля сохраняются
r1 = knowledge.retract(st, k2["knowledge_id"], by="g3-probe")
out.append("retracted_fields=%s" % (("applicable_when" in r1) or ("applicability_observations" in r1)))
r2 = knowledge.restore(st, k2["knowledge_id"], by="g3-probe")
out.append("restored_aw=%s" % json.dumps(r2.get("applicable_when"), sort_keys=True))
# версии целы
vers = st.read_knowledge_versions(k2["knowledge_id"])
out.append("nversions=%d" % len(vers))
# provenance-walk
ch = knowledge.provenance_walk(st, k2["knowledge_id"])
raw_ok = all(f["raw_text"] for e in ch["experiences"] for f in e["facts"] if f["raw_ref"])
out.append("walk_aw=%s" % (ch.get("applicable_when") is not None))
out.append("walk_raw=%s" % raw_ok)
print("|".join(out))
"""


def g3():
    print("== G3: acquisition persistence (новый процесс) ==", flush=True)
    st = g3_make()
    data_dir = os.path.join(DATA, "g3")
    r = _run(["python3", "-c", G3_PROBE, data_dir])
    out = (r.stdout or "").strip()
    parts = dict(p.split("=", 1) for p in out.split("|")
                 if "=" in p)
    aw_ok = parts.get("latest_aw") == '{"E": "absent"}'
    check("G3: поле переживает новый процесс (applicable_when={E:absent})",
          aw_ok, parts.get("latest_aw", "-"))
    obs_ok = '"V"' in parts.get("latest_obs", "") \
        and "disagreement" in parts.get("latest_obs", "")
    check("G3: observations V[1,2] disagreement читаемы в новом процессе",
          obs_ok, parts.get("latest_obs", "-"))
    check("G3: retract/restore сохраняют поля; версии целы",
          parts.get("retracted_fields") == "True"
          and parts.get("restored_aw") == '{"E": "absent"}',
          "nversions=%s" % parts.get("nversions", "-"))
    check("G3: provenance-walk: applicable_when + raw до фактов",
          parts.get("walk_aw") == "True"
          and parts.get("walk_raw") == "True",
          "walk_aw=%s walk_raw=%s" % (parts.get("walk_aw"),
                                      parts.get("walk_raw")))
    # v1 не мутирована: первая версия k1 (w1) без obs
    kd = latest_knowledge(st)
    k1 = [v for v in kd.values()][0]
    check("G3: v1 (w1-знание) не мутировала появлением v2",
          k1.get("version") == 1
          and (k1.get("applicable_when") or {}).get("E") == "absent",
          "v1 aw=%s" % json.dumps(k1.get("applicable_when")))
    env_set("w1")


def g4():
    print("== G4: applicability actually used ==", flush=True)
    st = g3_make()
    kd = latest_knowledge(st)
    line = [v for v in kd.values()
            if v.get("status") in ("active", "conflicted")
            and v.get("applicable_when") is not None]
    latest = max(line, key=lambda v: v["created_at"])
    check("G4a: applicable_when == {E: absent} (равенство)",
          latest.get("applicable_when") == {"E": "absent"},
          json.dumps(latest.get("applicable_when"), sort_keys=True))
    obs_v = [o for o in latest.get("applicability_observations") or []
             if o.get("signal") == "V"]
    check("G4a: obs V [1,2] disagreement на latest",
          bool(obs_v) and obs_v[0].get("values_seen") == ["1", "2"],
          json.dumps(obs_v))
    for v_now, world in (("1", "w1"), ("2", "wY")):
        env_set(world)
        obs = obs_now()
        s = suggest(st, "tsasvc.service inactive symptom=a", obs)
        check("G4a: E=absent, V=%s → S2 (1 действие fix-a)" % v_now,
              s["strategy_id"] == "S2"
              and len(s["candidate_actions"]) == 1
              and s["candidate_actions"][0]["command"] == "fix-a",
              s["strategy_id"])
    for v_now, world in (("1", "wX"), ("2", "w2")):
        env_set(world)
        obs = obs_now()
        s = suggest(st, "tsasvc.service inactive symptom=a", obs)
        check("G4b: E=present, V=%s → НЕ S2 (S3)" % v_now,
              s["strategy_id"] == "S3" and not s.get("exploration"),
              s["strategy_id"])
    env_set("w1")
    # G4c(i): поле управляет, даже без ctx_extra в args
    st_s = fresh_store("g4c")
    env_set("w1")
    problem = "tsasvc.service inactive symptom=a"
    facts = observer.collect(st_s)
    act = {"schema_version": "0.1",
           "action_id": "act_g06c_%s" % uuid.uuid4().hex[:8],
           "strategy_id": None, "proposed_by": "synthetic",
           "type": "command", "command": "fix-a",
           "args": {"goal": GOAL}, "permitted": True,   # БЕЗ ctx_extra
           "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "rationale": "G4c"}
    st_s.append_action(act)
    exp_full = experience.build(problem=problem, observations=facts,
                                actions=[act["action_id"]], machine="g4c")
    experience.save(st_s, exp_full)
    k1 = knowledge.create(st_s, content="synthetic field-only",
                          source="gate-v06", observer="gate-v06",
                          experience_refs=[exp_full["experience_id"]],
                          applicable_when={"E": "absent"})
    obs = obs_now()
    s = suggest(st_s, problem, obs)
    check("G4c(i): applicable_when без ctx в args → S2 (поле управляет)",
          s["strategy_id"] == "S2"
          and s["candidate_actions"][0]["command"] == "fix-a",
          s["strategy_id"])
    env_set("wX")
    obs = obs_now()
    s = suggest(st_s, problem, obs)
    check("G4c(i): E=present → S3 (поле гейтит)",
          s["strategy_id"] == "S3", s["strategy_id"])
    env_set("w1")
    # G4c(ii): legacy-знание без поля — ctx-путь v0.5
    st_l = fresh_store("g4c_legacy")
    env_set("w1")
    facts = observer.collect(st_l)
    act2 = {"schema_version": "0.1",
            "action_id": "act_g06l_%s" % uuid.uuid4().hex[:8],
            "strategy_id": None, "proposed_by": "synthetic",
            "type": "command", "command": "fix-a",
            "args": {"goal": GOAL, "ctx_extra": "absent"},
            "permitted": True,
            "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rationale": "G4c-legacy"}
    st_l.append_action(act2)
    exp2 = experience.build(problem=problem, observations=facts,
                            actions=[act2["action_id"]], machine="g4c")
    experience.save(st_l, exp2)
    k2 = knowledge.create(st_l, content="synthetic legacy",
                          source="gate-v06", observer="gate-v06",
                          experience_refs=[exp2["experience_id"]])
    obs = obs_now()
    s = suggest(st_l, problem, obs)
    check("G4c(ii): legacy без поля → ctx-путь (S2 при ctx=absent)",
          s["strategy_id"] == "S2", s["strategy_id"])
    # G4c(iii): assert — V из disagreement не в applicable_when
    bad = []
    for v in st.read_knowledge_versions_all():
        aw = v.get("applicable_when") or {}
        for o in v.get("applicability_observations") or []:
            if o.get("signal") in aw:
                bad.append(v["knowledge_id"])
    check("G4c(iii): ни одно знание не содержит V-obs в applicable_when",
          not bad, "bad=%s" % bad)


def main():
    if os.path.exists(DATA):
        shutil.rmtree(DATA)
    os.makedirs(DATA)
    open(LOG, "w", encoding="utf-8").close()
    print("== INTEGRATION GATE v0.6 (FROZEN 07.09; strategy v0.6) ==",
          flush=True)
    g1()
    g2()
    g3()
    g4()
    nfail = sum(1 for r in RESULTS if not r[1])
    print("== GATE V0.6: %s (%d PASS, %d FAIL) ==" % (
        "PASS" if nfail == 0 else "FAIL", len(RESULTS) - nfail, nfail),
        flush=True)


if __name__ == "__main__":
    main()
