# -*- coding: utf-8 -*-
"""Обязательный тест Update (Tsarapina, этап 8).

Контур (профессор):
    Experience → Action → Result → Evaluation → Update → Knowledge

U1. success: apply создаёт Knowledge-запись (kid +1), content
    содержит действие и переход состояния (из ФАКТОВ, не из слов
    модели), experience_refs=[полный опыт].
U2. failure: content фиксирует «НЕ перевело» + вердикт.
U3. knowledge валиден по knowledge.schema (источник update/rule:v1).
U4. Update не меняет Experience/Result/Evaluation.
U5. Опыт без действий → None (обновлять нечего), Knowledge не
    создаётся.
U6. update не импортирует llm.
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experience import experience  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from update import update  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(BASE, "protocols")
TMP = os.path.join(BASE, "tests", "tmp_update")
GOAL = {"property": "service:ssh.state", "value": "active"}
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def _fresh_store():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    return Store(os.path.join(TMP, "tsarapina.db"), TMP)


def _mk_full_experience(st, sa_state="active", rc=0):
    """Опыт с действием restart ssh + result (goal в args действия)."""
    facts = observer.collect(st)
    aid = st.append_action({
        "schema_version": "0.1",
        "action_id": "act_up_%s" % time.time(),
        "strategy_id": "S2", "proposed_by": "strategy/S2",
        "type": "command", "command": "systemctl restart ssh",
        "args": {"goal": GOAL}, "permitted": True,
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rationale": "известное исправление"})
    rid = st.append_result({
        "schema_version": "0.1", "result_id": "res_up_%s" % time.time(),
        "action_id": aid,
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_code": rc, "stdout": "restarted", "stderr": "",
        "state_before": {"service:ssh.state": "inactive"},
        "state_after": {"service:ssh.state": sa_state},
        "outcome": "unverified"})
    exp = experience.build(problem="ssh.service state=inactive",
                           observations=facts, actions=[aid],
                           result_ref=rid, machine="test")
    experience.save(st, exp)
    return exp["experience_id"], aid, rid


def _count_kids(st):
    return len({v["knowledge_id"] for v in st.read_knowledge_versions_all()})


def u1_success():
    st = _fresh_store()
    eid, aid, rid = _mk_full_experience(st, sa_state="active", rc=0)
    n0 = _count_kids(st)
    k = update.apply(st, eid, "success")
    n1 = _count_kids(st)
    check("U1a: Knowledge создан (kid +1)", k is not None and n1 == n0 + 1)
    check("U1b: content из фактов (действие + переход)",
          "systemctl restart ssh" in k["content"]
          and "inactive" in k["content"] and "active" in k["content"])
    check("U1c: experience_refs=[полный опыт]", k["experience_refs"] == [eid])
    check("U1d: источник update/rule:v1", k["source"] == "update/rule:v1")


def u2_failure():
    st = _fresh_store()
    eid, aid, rid = _mk_full_experience(st, sa_state="inactive", rc=0)
    k = update.apply(st, eid, "failure")
    check("U2: content фиксирует НЕ-достижение + вердикт",
          "НЕ перевело" in k["content"] and "failure" in k["content"])


def u3_schema():
    st = _fresh_store()
    eid, aid, rid = _mk_full_experience(st)
    k = update.apply(st, eid, "success")
    import jsonschema
    from jsonschema import RefResolver
    schema = json.load(open(os.path.join(PROTO, "knowledge.schema.json"),
                            encoding="utf-8"))
    resolver = RefResolver(base_uri="file://%s/" % PROTO, referrer=schema)
    try:
        jsonschema.validate(k, schema, resolver=resolver)
        check("U3: Knowledge валиден по knowledge.schema", True)
    except jsonschema.ValidationError as e:
        check("U3: Knowledge валиден по knowledge.schema", False,
              str(e)[:150])


def u4_no_mutation():
    st = _fresh_store()
    eid, aid, rid = _mk_full_experience(st)
    exp0 = st.read_experience(eid)
    res0 = st.read_result(rid)
    update.apply(st, eid, "success")
    check("U4a: Experience не изменён", st.read_experience(eid) == exp0)
    check("U4b: Result не изменён", st.read_result(rid) == res0)
    evs = st.read_evaluations()
    check("U4c: Update не создаёт evaluation-записей", len(evs) == 0)


def u5_no_actions():
    st = _fresh_store()
    facts = observer.collect(st)
    exp = experience.build(problem="probe", observations=facts,
                           machine="test")
    experience.save(st, exp)
    n0 = _count_kids(st)
    k = update.apply(st, exp["experience_id"], "success")
    n1 = _count_kids(st)
    check("U5: опыт без действий → None, Knowledge не создан",
          k is None and n1 == n0)


def u6_no_llm():
    src = open(os.path.join(BASE, "update", "update.py"),
               encoding="utf-8").read()
    import re
    check("U6: update не импортирует llm",
          not re.search(r"(import|from)\s+llm", src))


def main():
    u1_success()
    u2_failure()
    u3_schema()
    u4_no_mutation()
    u5_no_actions()
    u6_no_llm()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ UPDATE: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
