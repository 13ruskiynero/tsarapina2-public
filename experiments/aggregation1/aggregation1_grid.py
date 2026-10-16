# -*- coding: utf-8 -*-
"""AGGREGATION-1 grid: A–F, baseline vs aggregation (Tsarapina).

Дизайн: AGGREGATION1_DESIGN.md (frozen). Для каждого набора два
хранилища с ОДНИМИ эпизодами: baseline (без агрегации) и agg
(+aggregate()). Оба прогоняются через ОДНУ И ТУ ЖЕ R1 Strategy
(заморожена). Метрики M1–M5 считаются до интерпретации; отчёт —
JSON + таблица. Ничего не интерпретируется до завершения сетки.
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "tests"))

from aggregation import aggregation  # noqa: E402
from test_aggregation import (_active_count, _fresh_store, _latest,  # noqa
                              mk_episode)  # noqa: E402
from knowledge import knowledge  # noqa: E402
from strategy import strategy  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
OUT_DIR = os.path.join(BASE, "experiments", "aggregation1")
os.makedirs(OUT_DIR, exist_ok=True)
REPORT = os.path.join(OUT_DIR, "AGGREGATION1_grid_report.json")
LOG = os.path.join(OUT_DIR, "AGGREGATION1_grid.log")


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def build(name, store, episodes):
    """episodes: список (symptom, command, outcome[, state_after]).
    Возвращает eids."""
    eids = []
    for ep in episodes:
        sym, cmd, out = ep[0], ep[1], ep[2]
        sa = ep[3] if len(ep) > 3 else ("active" if out == "success"
                                        else "inactive")
        eids.append(mk_episode(store, sym, cmd, out, state_after=sa))
    return eids


def all_refs(store):
    """Все experience_refs активных знаний (последние версии)."""
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    return {e for v in latest.values()
            if v["status"] in ("active", "conflicted")
            for e in v.get("experience_refs", [])}


def suggest(store, symptom):
    sug = strategy.suggest(store, {"problem": "tsasvc.service inactive "
                               "symptom=%s" % symptom},
                           by="strategy/deterministic")
    cmd = None
    if sug["strategy_id"] == strategy.S2 and sug["candidate_actions"]:
        cmd = sug["candidate_actions"][0].get("command")
    return sug["strategy_id"], cmd, sug["knowledge_refs"]


def declare_last_pair(store, eids_a, eids_b):
    """declare_conflict между знаниями, чьи опыты — последние eids."""
    kids = {}
    for v in store.read_knowledge_versions_all():
        if v["status"] not in ("active", "conflicted"):
            continue
        for e in v.get("experience_refs", []):
            kids.setdefault(e, v["knowledge_id"])
    knowledge.declare_conflict(store, kids[eids_a[-1]], kids[eids_b[-1]])


def run_set(name, episodes, task_symptom, conflict_pair=None):
    """Прогнать набор: baseline + agg. Вернуть dict метрик."""
    out = {"name": name, "episodes": len(episodes)}

    def _mk():
        return _fresh_store()

    # baseline
    b = _mk()
    be = build(name + "-b", b, episodes)
    if conflict_pair:
        declare_last_pair(b, [be[i] for i in conflict_pair[0]],
                          [be[i] for i in conflict_pair[1]])
    b_active = _active_count(b)
    b_refs = all_refs(b)
    b_sug = suggest(b, task_symptom)

    # agg (те же эпизоды)
    a = _mk()
    ae = build(name + "-a", a, episodes)
    if conflict_pair:
        declare_last_pair(a, [ae[i] for i in conflict_pair[0]],
                          [ae[i] for i in conflict_pair[1]])
    # M2 измеряется ВНУТРИ agg-стора: refs активных до агрегации vs
    # после (coverage исходных свидетельств агрегатами)
    m2_before_refs = all_refs(a)
    rep = aggregation.aggregate(a)
    m2_after_refs = all_refs(a)
    a_active = _active_count(a)
    a_refs = m2_after_refs

    # M1: компрессия
    out["M1_active_before"] = b_active
    out["M1_active_after"] = a_active
    out["M1_compression_ratio"] = (round(b_active / a_active, 2)
                                   if a_active else None)
    out["M1_evidence_after"] = rep.get("evidence_after")
    # M2: coverage (внутри agg-стора)
    out["M2_refs_before_agg"] = len(m2_before_refs)
    out["M2_refs_after_agg"] = len(m2_after_refs)
    out["M2_coverage"] = (len(m2_after_refs & m2_before_refs)
                          / len(m2_before_refs) if m2_before_refs else None)
    # M3: decision equivalence на одинаковой задаче
    a_sug = suggest(a, task_symptom)
    out["M3_baseline"] = {"strategy": b_sug[0], "cmd": b_sug[1]}
    out["M3_agg"] = {"strategy": a_sug[0], "cmd": a_sug[1]}
    out["M3_equivalent"] = (b_sug[0] == a_sug[0] and b_sug[1] == a_sug[1])
    # M5: детерминизм (повтор агрегации ничего не создаёт)
    rep2 = aggregation.aggregate(a)
    out["M5_idempotent"] = len(rep2["created"]) == 0 and \
        len(rep2["conflicts_transferred"]) == 0
    log({"set": name, "aggregate": {k: (len(v) if isinstance(v, list)
                                        else v) for k, v in rep.items()},
         "M1": {"before": b_active, "after": a_active},
         "M2": {"coverage": out["M2_coverage"],
                "refs": [len(m2_before_refs), len(m2_after_refs)]},
         "M3": {"baseline": out["M3_baseline"], "agg": out["M3_agg"],
                "equivalent": out["M3_equivalent"]},
         "M5": out["M5_idempotent"]})
    return out


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== AGGREGATION-1 GRID (A–F) ==", flush=True)

    A = [("a", "fix-a", "success") for _ in range(6)]
    B = [("a", "fix-a", "success") for _ in range(3)]
    C = [("a", "fix-a", "success"), ("a", "fix-b", "success")]
    D = [("a", "fix-a", "success"), ("a", "fix-a", "failure"),
         ("a", "fix-a", "success"), ("a", "fix-a", "failure")]
    E = [("a", "fix-a", "success"), ("a", "fix-b", "failure"),
         ("a", "fix-a", "success"), ("a", "fix-b", "failure")]
    F = ([("a", "fix-a", "success") for _ in range(4)]
         + [("b", "fix-b", "success") for _ in range(2)]
         + [("a", "fix-b", "success")]
         + [("a", "fix-a", "failure") for _ in range(2)])

    results = []
    results.append(run_set("A", A, "a"))
    results.append(run_set("B", B, "a"))
    results.append(run_set("C", C, "a"))
    results.append(run_set("D", D, "a", conflict_pair=([0, 2], [1, 3])))
    results.append(run_set("E", E, "a", conflict_pair=([0, 2], [1, 3])))
    results.append(run_set("F", F, "a"))

    full = {"report": results, "note": (
        "M6 (swap): решения S2 не используют LLM; агрегатор не "
        "импортирует llm (G7c); swap-свойство контура проверено в "
        "RELEVANCE-1/LONGITUDINAL-1 — агрегат ведёт себя как обычное "
        "знание для R1.")}
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=1)

    print()
    print("набор  M1(до/после)  M2-coverage  M3-экв  M5-идемп.")
    for r in results:
        print("%-5s  %3d -> %-3d       %-6s      %-5s   %s"
              % (r["name"], r["M1_active_before"], r["M1_active_after"],
                 ("%.2f" % r["M2_coverage"]) if r["M2_coverage"]
                 is not None else "n/a",
                 "ДА" if r["M3_equivalent"] else "НЕТ",
                 "ДА" if r["M5_idempotent"] else "НЕТ"))
    print("saved %s" % REPORT, flush=True)


if __name__ == "__main__":
    main()
