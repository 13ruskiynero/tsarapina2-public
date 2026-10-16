# -*- coding: utf-8 -*-
"""Обязательный тест Strategy (Tsarapina, этап 5).

Главный вопрос (профессор):
> Можно ли восстановить, почему Strategy предложила конкретное
> действие, какие знания она использовала и какие из них были
> доступны ей на момент решения?

T1. Suggestion имеет rationale + knowledge_refs + snapshot.
T2. Цепочка решения восстановима: rationale → knowledge (версия) →
    experience → action-запись → candidate action (тот же command).
T3. Snapshot запечатывает доступность НА МОМЕНТ: знание, созданное
    ПОСЛЕ suggest, в снапшоте отсутствует.
T4. rationale НЕ становится знанием: suggest не добавляет записей
    в knowledge.
T5. Конфликт не разрешается молча: два конфликтующих релевантных
    знания → S3 + обе ссылки в rationale.
T6. Детерминизм: повторный suggest при том же состоянии = тот же
    suggestion.
T7. strategy не импортирует llm (этап 5 — до LLM-адаптера).

ИЗВЕСТНЫЙ EXPECTED MISMATCH (EF-11, 11.09.2026): t1 использует
legacy-фабрику knowledge (create без outcome-метки); A1 (production)
такие знания кандидатами не считает — t1 падает ожидаемо. A1-фильтр
ради зелёного CI не менять; вопрос статуса outcome-unknown
knowledge — D-6 (RESEARCH_DEBT.md).
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402
from strategy import strategy  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(BASE, "tests", "tmp_strategy")
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


def _mk_exp_ssh(st, action_command="systemctl restart ssh"):
    """Опыт: ssh недоступен; в эпизоде одно действие (restart)."""
    facts = observer.collect(st)
    aid = st.append_action({
        "schema_version": "0.1",
        "action_id": "act_ssh_%s" % time.time(),
        "strategy_id": None, "proposed_by": "test",
        "type": "command", "command": action_command,
        "args": {}, "permitted": True,
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rationale": "исправление ssh"})
    exp = experience.build(problem="ssh.service state=inactive",
                           observations=facts, actions=[aid],
                           machine="test")
    experience.save(st, exp)
    return exp["experience_id"], aid


def _mk_knowledge(st, eid, content):
    return knowledge.create(st, content=content, source="aggregation",
                            observer="eval", experience_refs=[eid])


def _count_kids(st):
    return len({v["knowledge_id"] for v in st.read_knowledge_versions_all()})


def t1_structure():
    st = _fresh_store()
    eid, _ = _mk_exp_ssh(st)
    k = _mk_knowledge(st, eid, "перезапуск ssh восстанавливает доступ")
    sug = strategy.suggest(st, {"problem": "ssh.service failed"})
    check("T1a: suggestion имеет rationale (непусто)", bool(sug["rationale"]))
    check("T1b: knowledge_refs содержит использованное знание",
          k["knowledge_id"] in sug["knowledge_refs"])
    check("T1c: knowledge_snapshot непуст и содержит знание",
          any(s["knowledge_id"] == k["knowledge_id"]
              for s in sug["knowledge_snapshot"]))
    check("T1d: candidate_actions непусты", bool(sug["candidate_actions"]))


def t2_recover_chain():
    st = _fresh_store()
    eid, aid = _mk_exp_ssh(st)
    k = _mk_knowledge(st, eid, "перезапуск ssh восстанавливает доступ")
    sug = strategy.suggest(st, {"problem": "ssh.service failed"})
    # S2: повтор действия опыта
    ok = sug["strategy_id"] == strategy.S2
    check("T2a: выбрана S2 (повторить исправление)", ok)
    # candidate action = команда из action-записи опыта
    acts = [a for a in sug["candidate_actions"]
            if a.get("action_ref") == aid]
    check("T2b: candidate action ссылается на действие опыта",
          len(acts) == 1 and acts[0]["command"] == "systemctl restart ssh")
    # rationale ведёт на знание (с версией)
    r = [r for r in sug["rationale"] if r.get("rule") == "known_fix"]
    check("T2c: rationale указывает knowledge_id и его версию",
          bool(r) and r[0]["knowledge_id"] == k["knowledge_id"]
          and r[0]["knowledge_version"] == 1)
    # восстановление по цепочке: suggestion → knowledge v1 → опыт → действие
    kk = st.read_knowledge(r[0]["knowledge_id"])
    e = st.read_experience(kk["experience_refs"][0])
    a = st.read_action(e["actions"][0])
    check("T2d: цепочка S→K→E→A восстановлена (command совпадает)",
          a["command"] == "systemctl restart ssh"
          and a["action_id"] == acts[0]["action_ref"])


def t3_snapshot_moment():
    st = _fresh_store()
    eid, _ = _mk_exp_ssh(st)
    k1 = _mk_knowledge(st, eid, "знание 1: перезапуск ssh помогает")
    sug = strategy.suggest(st, {"problem": "ssh.service failed"})
    snap1 = {s["knowledge_id"]: s["version"] for s in
             sug["knowledge_snapshot"]}
    check("T3a: снапшот содержит K1(v1)", snap1.get(k1["knowledge_id"]) == 1)
    # знание ПОСЛЕ suggest — не в снапшоте
    k3 = _mk_knowledge(st, eid, "знание 3 создано после решения")
    snap_ids = set(s["knowledge_id"] for s in sug["knowledge_snapshot"])
    check("T3b: знание, созданное после решения, в снапшоте ОТСУТСТВУЕТ",
          k3["knowledge_id"] not in snap_ids)
    # версия знания в снапшоте — версия на момент решения (запечатана):
    # отзываем K1 после suggest → снапшот всё ещё v1/active
    knowledge.retract(st, k1["knowledge_id"], by="operator")
    s1 = [s for s in sug["knowledge_snapshot"]
          if s["knowledge_id"] == k1["knowledge_id"]][0]
    check("T3c: снапшот запечатан (K1 v1 active, несмотря на retract)",
          s1["version"] == 1 and s1["status"] == "active")


def t4_rationale_not_knowledge():
    st = _fresh_store()
    eid, _ = _mk_exp_ssh(st)
    _mk_knowledge(st, eid, "перезапуск ssh помогает")
    n0 = _count_kids(st)
    strategy.suggest(st, {"problem": "ssh.service failed"})
    strategy.suggest(st, {"problem": "disk full"})
    n1 = _count_kids(st)
    check("T4: suggest не создаёт знания (rationale ≠ знание)", n0 == n1)
    check("T4b: suggestion сохранён в store",
          len(st.read_suggestions()) == 2)


def t5_conflict_no_silent():
    st = _fresh_store()
    e1, _ = _mk_exp_ssh(st)
    e2, _ = _mk_exp_ssh(st)
    k1 = _mk_knowledge(st, e1, "перезапуск ssh помогает")
    k2 = _mk_knowledge(st, e2, "перезапуск ssh НЕ помогает")
    knowledge.declare_conflict(st, k1["knowledge_id"], k2["knowledge_id"])
    sug = strategy.suggest(st, {"problem": "ssh.service failed"})
    check("T5a: конфликт → S3 (доп. данные)",
          sug["strategy_id"] == strategy.S3)
    check("T5b: обе ссылки в knowledge_refs",
          k1["knowledge_id"] in sug["knowledge_refs"]
          and k2["knowledge_id"] in sug["knowledge_refs"])
    check("T5c: rationale фиксирует конфликт",
          any(r.get("rule") == "conflict" for r in sug["rationale"]))
    check("T5d: обе записи живы",
          knowledge.read(st, k1["knowledge_id"]) is not None
          and knowledge.read(st, k2["knowledge_id"]) is not None)


def t6_determinism():
    st = _fresh_store()
    eid, _ = _mk_exp_ssh(st)
    _mk_knowledge(st, eid, "перезапуск ssh помогает")
    s1 = strategy.suggest(st, {"problem": "ssh.service failed"})
    s2 = strategy.suggest(st, {"problem": "ssh.service failed"})
    same = s1["strategy_id"] == s2["strategy_id"] and \
        s1["suggestion_id"] == s2["suggestion_id"] and \
        s1["rationale"] == s2["rationale"] and \
        s1["candidate_actions"] == s2["candidate_actions"]
    check("T6: повторный suggest при том же состоянии идентичен", same)


def t7_no_llm():
    st_dir = os.path.join(BASE, "strategy")
    bad = []
    for fn in os.listdir(st_dir):
        if fn.endswith(".py"):
            src = open(os.path.join(st_dir, fn), encoding="utf-8").read()
            if "import llm" in src or "from llm" in src:
                bad.append(fn)
    check("T7: strategy не импортирует llm", not bad)


def main():
    t1_structure()
    t2_recover_chain()
    t3_snapshot_moment()
    t4_rationale_not_knowledge()
    t5_conflict_no_silent()
    t6_determinism()
    t7_no_llm()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ STRATEGY: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
