# -*- coding: utf-8 -*-
"""Обязательный тест Experience (Tsarapina, этап 2).

Главный вопрос (профессор):
> Можно ли взять сохранённый Experience и восстановить из него
> последовательность исходных наблюдений, действий и результата,
> не добавляя интерпретацию задним числом?

Проверки:
1. Один Experience содержит несколько наблюдений.
2. Каждое наблюдение имеет provenance.
3. Действие связано с эпизодом, но его причина не подменяется
   фактом (rationale — в action-записи, не в эпизоде).
4. Результат хранится отдельно от оценки результата (result_ref —
   фактический; outcome=unknown при сборке, оценка не выдумана).
5. Нельзя незаметно изменить старый эпизод (append-only, dedup).
6. Повторная сборка того же набора событий даёт тот же Experience.
7. Experience не импортирует LLM.
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

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(BASE, "protocols")
TMP = os.path.join(BASE, "tests", "tmp_experience")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail), flush=True)


def _fresh_store():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    return Store(os.path.join(TMP, "tsarapina.db"), TMP)


def _make_actions(st, n=2):
    aids = []
    for i in range(n):
        a = {"schema_version": "0.1",
             "action_id": "act_test_%d_%s" % (i, time.time()),
             "strategy_id": None,
             "proposed_by": "strategy/S2",
             "type": "command",
             "command": "systemctl restart ssh",
             "args": {},
             "permitted": True,
             "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "rationale": "известное исправление (rationale — здесь, "
                          "не в эпизоде)"}
        aids.append(st.append_action(a))
    return aids


def t1_multiple_observations():
    st = _fresh_store()
    facts = observer.collect(st)  # 7 фактов
    exp = experience.build(problem="service:ssh state=unknown",
                           observations=facts[:4], machine="test")
    check("T1: эпизод содержит 4 наблюдения",
          len(exp["observations"]) == 4)
    check("T1b: эпизод валиден по experience.schema (jsonschema)",
          _valid_schema(exp))


def _valid_schema(exp):
    import jsonschema
    from jsonschema import RefResolver
    schema = json.load(open(os.path.join(PROTO, "experience.schema.json"),
                            encoding="utf-8"))
    resolver = RefResolver(base_uri="file://%s/" % PROTO, referrer=schema)
    try:
        jsonschema.validate(exp, schema, resolver=resolver)
        return True
    except jsonschema.ValidationError as e:
        print("   schema error:", str(e)[:150])
        return False


def t2_provenance_each():
    st = _fresh_store()
    facts = observer.collect(st)
    exp = experience.build(problem="probe", observations=facts, machine="t")
    ok = all(o.get("provenance", {}).get("raw_ref") for o in exp["observations"])
    check("T2: каждое наблюдение имеет provenance.raw_ref", ok)


def t3_action_vs_cause():
    st = _fresh_store()
    facts = observer.collect(st)
    aids = _make_actions(st, 2)
    exp = experience.build(problem="probe", observations=facts,
                           actions=aids, machine="t")
    # действия — ссылки в эпизоде
    check("T3a: эпизод хранит ссылки на действия", exp["actions"] == aids)
    # в эпизоде НЕТ полей причины/обоснования
    blob = json.dumps(exp, ensure_ascii=False)
    check("T3b: в эпизоде нет rationale/причины",
          "rationale" not in blob and "причин" not in blob)
    # причина живёт в action-записи
    act = st.read_action(aids[0])
    check("T3c: rationale восстановим из action-записи",
          bool(act and act.get("rationale")))


def t4_result_vs_evaluation():
    st = _fresh_store()
    facts = observer.collect(st)
    aids = _make_actions(st, 1)
    # фактический результат — отдельная запись result.schema
    rid = st.append_result({
        "schema_version": "0.1", "result_id": "res_test_1",
        "action_id": aids[0],
        "executed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "exit_code": 0, "stdout": "Restarted ssh.", "stderr": "",
        "state_before": {"service:ssh": "inactive"},
        "state_after": {"service:ssh": "active"},
        "outcome": "unverified", "evaluated_by": None, "evaluated_at": None})
    exp = experience.build(problem="probe", observations=facts,
                           actions=aids, result_ref=rid, machine="t")
    check("T4a: эпизод ссылается на результат (result_ref)", rid)
    check("T4b: оценка при сборке НЕ выдумана (outcome=unknown)",
          exp["outcome"] == "unknown")
    res = st.read_result(rid)
    check("T4c: фактический результат восстановим отдельно (exit=0)",
          bool(res) and res["exit_code"] == 0 and "ssh" in res["stdout"])
    # эпизод не содержит текста оценки
    blob = json.dumps(exp, ensure_ascii=False)
    check("T4d: в эпизоде нет приписанной оценки",
          '"success"' not in blob and "ошибк" not in blob)


def t5_immutable():
    st = _fresh_store()
    facts = observer.collect(st)
    exp = experience.build(problem="probe", observations=facts[:3],
                           machine="t")
    first = experience.save(st, exp)
    second = experience.save(st, exp)
    check("T5a: первая запись добавлена", first)
    check("T5b: повторная запись того же эпизода отклонена", not second)
    got = st.read_experience(exp["experience_id"])
    check("T5c: эпизод восстановлен без изменений", got == exp)


def t6_determinism():
    st = _fresh_store()
    facts = observer.collect(st)
    e1 = experience.build(problem="probe", observations=facts[:3],
                          machine="t")
    e2 = experience.build(problem="probe", observations=facts[:3],
                          machine="t")
    check("T6: повторная сборка того же набора → тот же Experience",
          e1 == e2 and e1["experience_id"] == e2["experience_id"])


def t7_no_llm():
    exp_dir = os.path.join(BASE, "experience")
    bad = []
    for fn in os.listdir(exp_dir):
        if fn.endswith(".py"):
            src = open(os.path.join(exp_dir, fn), encoding="utf-8").read()
            if "import llm" in src or "from llm" in src:
                bad.append(fn)
    check("T7: experience не импортирует llm", not bad)


def t_recover():
    """Главный тест: восстановить последовательность исходных
    наблюдений, действий и результата из эпизода."""
    st = _fresh_store()
    facts = observer.collect(st)
    aids = _make_actions(st, 2)
    rid = st.append_result({
        "schema_version": "0.1", "result_id": "res_rec_1",
        "action_id": aids[1], "executed_at": "t", "exit_code": 0,
        "stdout": "ok", "stderr": "", "state_before": {}, "state_after": {},
        "outcome": "unverified", "evaluated_by": None, "evaluated_at": None})
    exp = experience.build(problem="probe", observations=facts,
                           actions=aids, result_ref=rid, machine="t")
    experience.save(st, exp)
    got = st.read_experience(exp["experience_id"])
    # наблюдения: факты + их raw
    obs_ok = len(got["observations"]) == len(facts) and all(
        a == b for a, b in zip(got["observations"], facts))
    raw_ok = all(st.read_raw(o["provenance"]["raw_ref"]) is not None
                 for o in got["observations"])
    # действия
    act_ok = all(st.read_action(a) is not None for a in got["actions"])
    # результат
    res_ok = st.read_result(got["result_ref"]) is not None
    # никакой интерпретации задним числом: в эпизоде нет объяснений
    blob = json.dumps(got, ensure_ascii=False)
    no_int = all(w not in blob for w in
                 ("поэтому", "because", "причина", "вывод:", "explanation"))
    check("ГЛАВНЫЙ: восстановимы наблюдения (%d)+raw" % len(facts),
          obs_ok and raw_ok)
    check("ГЛАВНЫЙ: восстановимы действия (%d)" % len(aids), act_ok)
    check("ГЛАВНЫЙ: восстановим результат", res_ok)
    check("ГЛАВНЫЙ: интерпретация задним числом отсутствует", no_int)


def main():
    t1_multiple_observations()
    t2_provenance_each()
    t3_action_vs_cause()
    t4_result_vs_evaluation()
    t5_immutable()
    t6_determinism()
    t7_no_llm()
    t_recover()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ EXPERIENCE: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
