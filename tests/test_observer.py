# -*- coding: utf-8 -*-
"""Обязательный тест Observer (Tsarapina, этап 1).

Вопрос теста (заморожен профессором):
> Можно ли по записи Observer восстановить исходное наблюдение и
> отличить его от любой последующей интерпретации? Если нет,
> Observer не прошёл.

Тесты:
T1 roundtrip: факт, прочитанный из store, идентичен записанному.
T2 факт ≠ интерпретация: интерпретации пишутся отдельным потоком и
   никогда не появляются среди фактов; по fact+raw_ref восстанавли-
   вается исходное наблюдение.
T3 append-only: raw неизменяемы (повторная запись = новый id;
   старый raw не редактируется).
T4 schema: каждый факт валиден против fact.schema (+ provenance).
T5 нет LLM: модуль observer не импортирует llm (детерминированность).
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(BASE, "protocols")
TMP = os.path.join(BASE, "tests", "tmp_observer")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail), flush=True)


def _fresh_store():
    if os.path.exists(TMP):
        shutil.rmtree(TMP)
    os.makedirs(TMP)
    return Store(os.path.join(TMP, "tsarapina.db"), TMP)


def t1_roundtrip():
    st = _fresh_store()
    facts = observer.collect(st)
    assert facts, "collect вернул пусто"
    back = st.read_facts()
    ok = len(back) == len(facts) and all(a == b for a, b in zip(facts, back))
    check("T1 roundtrip: запись == чтение (%d фактов)" % len(facts), ok)


def t2_fact_vs_interpretation():
    st = _fresh_store()
    facts = observer.collect(st)
    # интерпретация — отдельный поток
    st.append_interpretation({"text": "диска достаточно",
                              "based_on": facts[0]["provenance"]["raw_ref"]})
    back = st.read_facts()
    types = set(f.get("type") for f in back)
    check("T2a: среди фактов только type=fact", types == {"fact"})
    # восстановление исходного наблюдения: fact + raw_ref
    ok_raw = True
    for f in facts:
        rid = f["provenance"]["raw_ref"]
        raw = st.read_raw(rid)
        if raw is None:
            ok_raw = False
            break
    check("T2b: по каждому fact+raw_ref восстанавливается raw", ok_raw)
    # факт disk: raw df содержит строку с '/'; восстановимо наблюдение
    disk = [f for f in facts if f["subject"] == "disk"]
    if disk:
        raw = st.read_raw(disk[0]["provenance"]["raw_ref"])
        check("T2c: raw df восстановим и непуст",
              bool(raw) and "/" in raw)
    else:
        check("T2c: сенсор disk присутствует", False)


def t3_append_only():
    st = _fresh_store()
    r1 = st.append_raw("test", "alpha")
    r2 = st.append_raw("test", "beta")
    check("T3a: повторная запись даёт новый id", r1 != r2)
    check("T3b: старый raw неизменен", st.read_raw(r1) == "alpha")
    # у raw нет update-пути в Store API: проверяем, что JSONL не растёт
    # вставкой в середину (append-only по построению) — фиксируем длины
    n1 = sum(1 for _ in open(st.raw_jsonl, encoding="utf-8"))
    st.append_raw("test", "gamma")
    n2 = sum(1 for _ in open(st.raw_jsonl, encoding="utf-8"))
    check("T3c: raw.jsonl только растёт (append)", n2 == n1 + 1)


def t4_schema():
    st = _fresh_store()
    facts = observer.collect(st)
    import jsonschema
    from jsonschema import RefResolver
    schema = json.load(open(os.path.join(PROTO, "fact.schema.json"),
                            encoding="utf-8"))
    resolver = RefResolver(base_uri="file://%s/" % PROTO, referrer=schema)
    errs = []
    for f in facts:
        try:
            jsonschema.validate(f, schema, resolver=resolver)
        except jsonschema.ValidationError as e:
            errs.append(str(e)[:120])
    check("T4: все %d фактов валидны по fact.schema" % len(facts),
          not errs, "; ".join(errs[:2]))


def t5_no_llm():
    obs_dir = os.path.join(BASE, "observer")
    bad = []
    for fn in os.listdir(obs_dir):
        if fn.endswith(".py"):
            src = open(os.path.join(obs_dir, fn), encoding="utf-8").read()
            if "import llm" in src or "from llm" in src:
                bad.append(fn)
    check("T5: observer не импортирует llm", not bad)


def main():
    t1_roundtrip()
    t2_fact_vs_interpretation()
    t3_append_only()
    t4_schema()
    t5_no_llm()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ OBSERVER: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
