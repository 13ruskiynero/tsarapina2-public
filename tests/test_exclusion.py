# -*- coding: utf-8 -*-
"""Обязательный тест exclusion-механизма (Tsarapina, v0.6.x+A1).

Главный вопрос (профессор):
> Перенесённый в production механизм exclusion сохраняет семантику
> experimental A1: POOL/TEMP, пустой пул → S3 → внешний Explore,
> append-only историю, fail-closed конфиг?

Границы (FROZEN, A1_PRODUCTION_TRANSFER_DESIGN.md §5):
P: POOL — исключённый K невидим; sibling доступен; failure-derived
   не попадает в selection (A1-addressing).
T: TEMP — exclusion → sol → slot → attempt; success → eligible;
   non-success → remains; второй автоматический slot не появляется.
E: empty pool — отсутствие обнаруживается; exclusion сам Explore не
   вызывает; dispatch — только через внешний вызов.
H: история/guards — K record не мутируется; события append-only;
   запрещённый K не возвращается в selection; provenance целы.
F: FAIL CLOSED — missing/невалидный exclusion_semantics → ValueError.
"""
import os
import shutil
import sys
import uuid

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import exclusion  # noqa: E402

TMP = os.path.join(BASE, "tests", "tmp_exclusion")
PROBLEM = "tsasvc.service inactive symptom=a"
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def _fresh_store(tag):
    d = os.path.join(TMP, tag)
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return Store(os.path.join(d, "tsarapina.db"), d)


def _mk_action(st, cmd, ctx="absent"):
    aid = "act_test_%s" % uuid.uuid4().hex[:8]
    act = {"schema_version": "0.1", "action_id": aid, "strategy_id": None,
           "proposed_by": "test/exclusion", "type": "command",
           "command": cmd, "args": {"goal": {}, "ctx_extra": ctx},
           "permitted": True, "proposed_at": "2026-09-11T00:00:00",
           "rationale": "test"}
    st.append_action(act)
    return aid


def _mk_knowledge(st, cmd="fix-a", aw=None, outcome="success",
                  ctx="absent", syms="a", content=None):
    """Знание с адресом (syms, ctx, cmd) и context outcome=...;
    outcome=success → поле aw (если задано); иначе legacy/failure."""
    aid = _mk_action(st, cmd, ctx)
    facts = observer.collect(st)
    exp = experience.build(
        problem="tsasvc.service inactive symptom=%s" % syms,
        observations=facts, actions=[aid], machine="test-exclusion")
    experience.save(st, exp)
    eid = exp["experience_id"]
    k = knowledge.create(
        st, content=content or ("%s for symptom=%s" % (cmd, syms)),
        source="test/exclusion", observer="test", experience_refs=[eid],
        context="experience=%s outcome=%s" % (eid, outcome),
        applicable_when=aw, lineage_generation=1)
    return k["knowledge_id"]


# --- P: POOL -----------------------------------------------------------
def t_pool():
    st = _fresh_store("pool")
    k1 = _mk_knowledge(st, aw={"E": "absent", "V": "1"})
    k2 = _mk_knowledge(st, aw={"E": "absent", "V": "2"})
    f1 = _mk_knowledge(st, aw=None, outcome="partial")
    m = exclusion.GateModule(st, "POOL")
    obs_v2 = {"E": "absent", "V": "2"}
    elig0, info0 = m.eligible_pool(PROBLEM, "absent", obs_v2)
    check("P0: failure-derived не в pool (A1-addressing; legacy-путь "
          "не воскрешает)", f1 not in info0["eligible_ids"]
          and f1 not in info0["excluded_seen"])
    check("P1: baseline — k2 eligible без exclusion",
          k2 in info0["eligible_ids"])
    m.exclude(k2)
    elig1, info1 = m.eligible_pool(PROBLEM, "absent", obs_v2)
    check("P2: excluded K отсутствует в eligible pool",
          k2 not in info1["eligible_ids"]
          and len(info1["eligible_ids"]) == len(info0["eligible_ids"]) - 1)
    elig2, info2 = m.eligible_pool(PROBLEM, "absent",
                                   {"E": "absent", "V": "1"})
    check("P3: sibling eligible остаётся доступен (k1 при V=1)",
          k1 in info2["eligible_ids"] and k2 not in info2["eligible_ids"])
    sug, info3 = m.decide(PROBLEM, "absent", {"E": "absent", "V": "1"})
    refs = (sug or {}).get("knowledge_refs") or []
    check("P4: запрещённый K не возвращается в selection",
          sug is not None and k2 not in refs and k1 in refs)
    g = [x for x in m.guards if x["guard"] == "excluded_not_selected"]
    check("P5: guard excluded_not_selected = ok",
          bool(g) and all(x["ok"] for x in g))


# --- T: TEMP -----------------------------------------------------------
def t_temp():
    st = _fresh_store("temp_ok")
    k1 = _mk_knowledge(st, aw={"E": "absent", "V": "1"})
    k2 = _mk_knowledge(st, aw={"E": "absent", "V": "2"})
    m = exclusion.GateModule(st, "TEMP")
    m.exclude(k2)
    check("T1: exclusion → slot none", m.slot_state.get(k2) == "none")
    added = m.on_episode({"mode": "S2", "outcome": "success",
                          "knowledge_refs": [k1]})
    check("T2: exclusion → sign-of-life → slot",
          added == ["sol", "slot"] and m.slot_state.get(k2) == "open")
    check("T3: attempt_needed=True (slot открыт)", m.attempt_needed())
    m.process_attempt(k2, True)
    check("T4: success → eligible (exclusion снят)",
          k2 not in m.exclusions and
          m.slot_state.get(k2) == "consumed" and not m.attempt_needed())
    evs = [e["event"] for e in m.events]
    check("T5: события цикла в порядке",
          evs == ["exclusion", "sol", "slot", "eligible"])

    st2 = _fresh_store("temp_fail")
    k1b = _mk_knowledge(st2, aw={"E": "absent", "V": "1"})
    k2b = _mk_knowledge(st2, aw={"E": "absent", "V": "2"})
    m2 = exclusion.GateModule(st2, "TEMP")
    m2.exclude(k2b)
    m2.on_episode({"mode": "S2", "outcome": "success",
                   "knowledge_refs": [k1b]})
    m2.process_attempt(k2b, False)
    check("T6: non-success → остаётся excluded",
          k2b in m2.exclusions and
          m2.slot_state.get(k2b) == "consumed")
    m2.on_episode({"mode": "S2", "outcome": "success",
                   "knowledge_refs": [k1b]})
    slots = [e for e in m2.events if e["event"] == "slot"]
    check("T7: второй автоматический slot не появляется",
          len(slots) == 1 and not m2.attempt_needed())
    att = [e for e in m2.events if e["event"] == "attempt"]
    check("T8: событие attempt зафиксировано (remains_excluded)",
          len(att) == 1 and att[0].get("remains_excluded") is True)


# --- E: empty pool -----------------------------------------------------
def t_empty():
    st = _fresh_store("empty")
    k1 = _mk_knowledge(st, aw={"E": "absent", "V": "1"})
    m = exclusion.GateModule(st, "POOL")
    m.exclude(k1)
    elig, info = m.eligible_pool(PROBLEM, "absent", {"E": "absent",
                                                     "V": "1"})
    check("E1: отсутствие eligible candidate обнаруживается",
          len(elig) == 0 and info["n_eligible"] == 0)
    check("E2: exclusion сам Explore не вызывает",
          m.pop_explore() is False)
    sug, info2 = m.decide(PROBLEM, "absent", {"E": "absent", "V": "1"})
    check("E3: S3 фиксируется механизмом (pool_empty)",
          sug is None and info2["pool_empty"] is True
          and info2["s3_triggered"] is True)
    check("E4: dispatch — только через внешний вызов pop_explore()",
          m.pop_explore() is True and m.pop_explore() is False)


# --- H: история / guards ----------------------------------------------
def t_history():
    st = _fresh_store("hist")
    k1 = _mk_knowledge(st, aw={"E": "absent", "V": "1"})
    before = st.read_knowledge(k1)
    m = exclusion.GateModule(st, "TEMP")
    m.exclude(k1)
    m.on_episode({"mode": "S2", "outcome": "success",
                  "knowledge_refs": [k1]})   # ref0 == k0 → SOL не должен
    after = st.read_knowledge(k1)
    same = (before["version"] == after["version"] == 1
            and before["content"] == after["content"]
            and before.get("applicable_when") == after.get(
                "applicable_when")
            and before.get("experience_refs") == after.get(
                "experience_refs")
            and before.get("lineage_generation") == after.get(
                "lineage_generation"))
    check("H1: K record не мутируется (append-only)" + " (version=1)",
          same)
    exps = [st.read_experience(e) for e in
            (after.get("experience_refs") or [])]
    check("H2: provenance/lineage не теряются",
          bool(exps) and all(e is not None for e in exps)
          and after.get("lineage_generation") == 1)
    snap = [dict(e) for e in m.events]
    m.exclude(k1)          # дубль → no-op (возврат до append)
    m.pop_explore()        # no-op
    check("H3: события append-only; дубли и no-op не пишут",
          m.events == snap
          and len([e for e in m.events
                   if e["event"] == "exclusion"]) == 1)


# --- F: FAIL CLOSED ----------------------------------------------------
def t_fail_closed():
    st = _fresh_store("fc")
    ok_none = ok_halt = False
    try:
        exclusion.GateModule(st, None)
    except ValueError:
        ok_none = True
    try:
        exclusion.GateModule(st, "HALT")
    except ValueError:
        ok_halt = True
    check("F1: missing exclusion_semantics → FAIL CLOSED (ValueError)",
          ok_none)
    check("F2: невалидный semantics (HALT) → FAIL CLOSED", ok_halt)
    ok_ok = True
    for sem in ("POOL", "TEMP"):
        try:
            exclusion.GateModule(st, sem)
        except ValueError:
            ok_ok = False
    check("F3: POOL и TEMP конструируются без дефолта", ok_ok)


def main():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    t_pool()
    t_temp()
    t_empty()
    t_history()
    t_fail_closed()
    fails = [r for r in RESULTS if not r[1]]
    print("")
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ EXCLUSION: %s%s ===" % (
        "ПРОЙДЕН" if not fails else "НЕ ПРОЙДЕН",
        "" if not fails else " (%d)" % len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
