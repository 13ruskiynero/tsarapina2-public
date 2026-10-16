# -*- coding: utf-8 -*-
"""TRUST-1 driver: сценарии S1–S6 × механики (зона 3, Tsarapina).

Дизайн: TRUST1_DESIGN.md (frozen). Синтетика, без полигона и без
LLM: эпизоды через существующие слои (experience/evaluation/update),
выбор — strategy_v3.suggest_v3 (ветка; основная Strategy не
тронута). T1 (auto_conflict) вызывается контуром после каждого
проверенного эпизода. Для каждой механики сценарий воспроизводится
на чистом хранилище. Измерения: M1 действия до успеха/остановки,
M2 корректность финального выбора, M4 S3-остановки, M5 детерминизм
(двойной прогон). M3 (история цела) — проверкой числа версий.
"""
import json
import os
import shutil
import sys
import time

import os.path as _p

TRUST1 = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(TRUST1)
BASE = os.path.dirname(EXP)
sys.path.insert(0, BASE)
sys.path.insert(0, _p.join(BASE, "tests"))
sys.path.insert(0, TRUST1)

from aggregation import aggregation  # noqa: E402
from test_aggregation import _fresh_store, mk_episode  # noqa: E402
from strategy_v3 import (auto_conflict, suggest_v3)  # noqa: E402

MECHS = ["", "T1", "T1+T2", "T1+T2+T3"]
OUT_DIR = TRUST1
LOG = _p.join(OUT_DIR, "TRUST1_run.log")
REPORT = _p.join(OUT_DIR, "TRUST1_grid_report.json")
MAX_ACTS = 6


def log(rec):
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def last_update_kid(store):
    """kid последнего созданного проверенного знания (update/rule)."""
    best, best_t = None, ""
    for v in store.read_knowledge_versions_all():
        if v["source"] == "update/rule:v1" and v["version"] == 1:
            if v["created_at"] > best_t:
                best, best_t = v["knowledge_id"], v["created_at"]
    return best


def add_ep(store, sym, cmd, outcome, mech):
    """Эпизод через слои; затем T1-автоконфликт (если в mech)."""
    mk_episode(store, sym, cmd, outcome)
    if "T1" in mech:
        kid = last_update_kid(store)
        if kid:
            auto_conflict(store, kid)


def cmd_of_sug(sug):
    for a in sug.get("candidate_actions", []):
        if a.get("type") == "command" and a.get("command"):
            return a["command"]
    return None


def run_task(store, sym, mech, truth, max_acts=MAX_ACTS):
    """Задача: контур выбирает, мир отвечает (cmd==truth → success;
    truth=None → любое действие failure). Возвращает итог."""
    n = 0
    for _ in range(max_acts):
        sug = suggest_v3(store, {"problem": "tsasvc.service inactive "
                                "symptom=%s" % sym}, mech=mech,
                         save=False)
        sid = sug["strategy_id"]
        if sid in ("S3", "S1"):
            return {"actions": n, "final": sid, "success": False}
        cmd = cmd_of_sug(sug)
        if cmd is None:
            return {"actions": n, "final": sid + ":no_cmd",
                    "success": False}
        n += 1
        outcome = "success" if truth is not None and cmd == truth \
            else "failure"
        add_ep(store, sym, cmd, outcome, mech)
        if outcome == "success":
            return {"actions": n, "final": cmd, "success": True}
    return {"actions": n, "final": "loop", "success": False}


def run_scenario(mech):
    """Каждый сценарий S1–S6 воспроизводится на ЧИСТОМ хранилище
    (как заявлено в TRUST1_DESIGN: «сценарий воспроизводится на
    чистом хранилище»; накопительная «одна жизнь» — дополнительный
    прогон run_accumulated). Вернуть dict."""
    res = {}

    # S1: устаревание-канон: s → f → задача (правильного нет)
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-a", "failure", mech)
    res["S1"] = run_task(st, "a", mech, truth=None)

    # S2: чередование s,f,s → задача: fix-a работает
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-a", "failure", mech)
    add_ep(st, "a", "fix-a", "success", mech)
    res["S2"] = run_task(st, "a", mech, truth="fix-a")

    # S3: конфликт действий: fix-a success + fix-b failure (без declare)
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-b", "failure", mech)
    res["S3"] = run_task(st, "a", mech, truth="fix-a")

    # S4: шум: s, f(внешняя причина), s → задача: fix-a работает
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-a", "failure", mech)
    add_ep(st, "a", "fix-a", "success", mech)
    res["S4"] = run_task(st, "a", mech, truth="fix-a")

    # S5: evidence: 3× fix-a success → агрегация; затем 1× fix-b success
    st = _fresh_store()
    for _ in range(3):
        add_ep(st, "a", "fix-a", "success", mech)
    aggregation.aggregate(st)
    add_ep(st, "a", "fix-b", "success", mech)
    res["S5"] = run_task(st, "a", mech, truth="fix-a")

    # S6: полный UA: s → задача (всё failure: устаревание) → learn
    # fix-a2 → задача: fix-a2 работает
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    r6a = run_task(st, "a", mech, truth=None)      # fix-a не работает
    add_ep(st, "a", "fix-a2", "success", mech)     # оператор показал
    r6b = run_task(st, "a", mech, truth="fix-a2")
    res["S6a"] = r6a
    res["S6b"] = r6b

    # M3: версии не удалялись (на S6-сторе)
    res["_versions"] = len(st.read_knowledge_versions_all())
    return res


def run_accumulated(mech):
    """«Одна жизнь» (L1-реализм): S1–S6 в одном сторе (накопление).
    Показывает поведение T3-evidence при долгой истории."""
    st = _fresh_store()
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-a", "failure", mech)
    r1 = run_task(st, "a", mech, truth=None)
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-a", "failure", mech)
    add_ep(st, "a", "fix-a", "success", mech)
    r2 = run_task(st, "a", mech, truth="fix-a")
    add_ep(st, "a", "fix-a", "success", mech)
    add_ep(st, "a", "fix-b", "failure", mech)
    r3 = run_task(st, "a", mech, truth="fix-a")
    for _ in range(3):
        add_ep(st, "a", "fix-a", "success", mech)
    aggregation.aggregate(st)
    add_ep(st, "a", "fix-b", "success", mech)
    r5 = run_task(st, "a", mech, truth="fix-a")
    add_ep(st, "a", "fix-a2", "success", mech)
    r6b = run_task(st, "a", mech, truth="fix-a2")
    return {"accS1": r1, "accS2": r2, "accS3": r3, "accS5": r5,
            "accS6b": r6b}


def main():
    open(LOG, "w", encoding="utf-8").close()
    print("== TRUST-1 (S1–S6 изолированно × механики) ==", flush=True)
    table = {}
    for mech in MECHS:
        r1 = run_scenario(mech)
        r2 = run_scenario(mech)  # M5: детерминизм
        det = {k: r1[k] for k in r1 if not k.startswith("_")} == \
              {k: r2[k] for k in r2 if not k.startswith("_")}
        acc = run_accumulated(mech)
        table[mech or "base"] = {"run": r1, "deterministic": det,
                                 "accumulated": acc}
        log({"mech": mech or "base", "run": r1, "deterministic": det,
             "accumulated": acc})

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)

    print()
    hdr = "%-8s %-8s %-8s %-8s %-8s %-10s %-8s %-6s"
    print(hdr % ("mech", "S1", "S2", "S3", "S4", "S5", "S6a/S6b",
                 "det"))
    for mech in MECHS:
        t = table[mech or "base"]["run"]

        def f(x):
            if x["final"] in ("S3", "S1", "loop"):
                return x["final"]
            return x["final"]
        print("%-8s %-8s %-8s %-8s %-8s %-10s %-8s %-6s"
              % (mech or "base",
                 f(t["S1"]) + "(" + str(t["S1"]["actions"]) + ")",
                 f(t["S2"]) + "(" + str(t["S2"]["actions"]) + ")",
                 f(t["S3"]) + "(" + str(t["S3"]["actions"]) + ")",
                 f(t["S4"]) + "(" + str(t["S4"]["actions"]) + ")",
                 f(t["S5"]) + "(" + str(t["S5"]["actions"]) + ")",
                 f(t["S6a"]) + "/" + f(t["S6b"]) + "(" +
                 str(t["S6b"]["actions"]) + ")",
                 "да" if table[mech or "base"]["deterministic"] else "нет"))
    print()
    print("== «одна жизнь» (накопление): accS1 accS2 accS3 accS5 accS6b ==")
    for mech in MECHS:
        a = table[mech or "base"]["accumulated"]
        row = []
        for k in ("accS1", "accS2", "accS3", "accS5", "accS6b"):
            v = a[k]
            row.append("%s(%d)" % (v["final"], v["actions"]))
        print("%-8s %s" % (mech or "base", "  ".join(row)))
    print("saved %s" % REPORT, flush=True)


if __name__ == "__main__":
    main()
