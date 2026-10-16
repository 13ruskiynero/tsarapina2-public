# -*- coding: utf-8 -*-
"""Продолжение LONGITUDINAL-1: UA2–UA6 + SW (после технической
остановки на UA2 — дефект фильтра k_old в драйвере). Использует
существующий tsar-стор с E1–E50 run-2. Протокол не меняется."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from longitudinal1_driver import (Store, declare_conflict_op, learn, log,
                                  last_a_success_kid, retract_op,
                                  tsar_solve)

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_tsar")
tt = Store(os.path.join(DATA, "tsarapina.db"), DATA)

# k_fail: последнее активное «НЕ перевело» с опытом symptom=a
k_fail = None
for v in reversed(sorted(tt.read_knowledge_versions_all(),
                         key=lambda v: v.get("created_at", ""))):
    if v["status"] == "active" and "НЕ перевело" in v.get("content", ""):
        for eid in v.get("experience_refs", []):
            e = tt.read_experience(eid)
            if e and re.search(r"symptom=a(?: |$)", e.get("problem", "")):
                k_fail = v["knowledge_id"]
                break
    if k_fail:
        break

k_old = last_a_success_kid(tt)
print("k_old:", k_old, "| k_fail:", k_fail, flush=True)

if k_old and k_fail and k_old != k_fail:
    declare_conflict_op(tt, "UA2", k_old, k_fail)
else:
    log({"ep": "UA2", "event": "operator_conflict", "error":
         "k_old/k_fail не найдены или равны", "k_old": k_old,
         "k_fail": k_fail})

tsar_solve(tt, "UA3", "a2")   # ожидание S3 (защита)
learn(tt, "UA4", "a2", "fix-a2")
if k_old:
    retract_op(tt, "UA5", k_old, "среда изменилась: fix-a2")
if k_fail and k_fail != k_old:
    retract_op(tt, "UA5b", k_fail, "устарело после fix-a2")
tsar_solve(tt, "UA6", "a2")   # ожидание S2 fix-a2
tsar_solve(tt, "SW1", "a", provider="qwen25")
tsar_solve(tt, "SW2", "a", provider="qwen25")

kb = 0
kt = len({v["knowledge_id"] for v in tt.read_knowledge_versions_all()})
log({"event": "final", "knowledge_bare": kb, "knowledge_tsar": kt})
print("== UA/SW DONE: knowledge tsar=%d ==" % kt, flush=True)
