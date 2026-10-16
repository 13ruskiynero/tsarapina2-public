# -*- coding: utf-8 -*-
"""Обязательный тест Knowledge (Tsarapina, этап 3).

Главный вопрос (профессор):
> Можно ли получить Knowledge из Experience так, чтобы для каждой
> записи можно было восстановить её происхождение, а противоположные
> версии не уничтожали друг друга?

K1. Provenance roundtrip: Knowledge → Experience → Fact → Raw.
K2. Conflict preservation: два противоречащих знания — ОБА остаются.
K3. Retract: запись осталась; статус изменился; история сохранилась;
    provenance не исчез.
K4. Restore: K1 → RETRACT → RESTORE; история показывает обе операции.
K5. Append-only: попытка изменить старую запись напрямую провалится.
K6. No provenance: Knowledge без источника — создание провалится.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experience import experience  # noqa: E402
from knowledge import knowledge  # noqa: E402
from observer import observer  # noqa: E402
from storage.store import Store  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(BASE, "protocols")
TMP = os.path.join(BASE, "tests", "tmp_knowledge")
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


def _mk_experience(st, problem="ssh.service unavailable"):
    facts = observer.collect(st)
    exp = experience.build(problem=problem, observations=facts,
                           machine="test")
    experience.save(st, exp)
    return exp["experience_id"]


def _schema_ok(rec):
    import jsonschema
    from jsonschema import RefResolver
    schema = json.load(open(os.path.join(PROTO, "knowledge.schema.json"),
                            encoding="utf-8"))
    resolver = RefResolver(base_uri="file://%s/" % PROTO, referrer=schema)
    try:
        jsonschema.validate(rec, schema, resolver=resolver)
        return True
    except jsonschema.ValidationError as e:
        print("   schema error:", str(e)[:200])
        return False


def k1_roundtrip():
    st = _fresh_store()
    eid = _mk_experience(st)
    k = knowledge.create(st, content="ssh.service был недоступен и "
                         "восстановлен перезапуском",
                         source="aggregation/test", observer="operator",
                         experience_refs=[eid])
    check("K1a: запись валидна по knowledge.schema", _schema_ok(k))
    chain = knowledge.provenance_walk(st, k["knowledge_id"])
    exps = chain["experiences"]
    ok_exp = len(exps) == 1 and exps[0]["experience_id"] == eid
    facts = exps[0]["facts"] if exps else []
    ok_facts = len(facts) == 9 and all(f["raw_text"] is not None
                                       for f in facts)
    check("K1b: Knowledge → Experience восстановлена (%d опыт)" % len(exps),
          ok_exp)
    check("K1c: Experience → Fact → Raw восстановлены (%d фактов, "
          "raw непуст)" % len(facts), ok_facts)
    if facts:
        d = [f for f in facts if f["fact"]["subject"] == "disk"]
        check("K1d: raw df восстановим (содержит '/')",
              bool(d) and "/" in (d[0]["raw_text"] or ""))


def k2_conflict():
    st = _fresh_store()
    e1 = _mk_experience(st, problem="ssh.service state=inactive")
    e2 = _mk_experience(st, problem="ssh.service state=active")
    k1 = knowledge.create(st, content="SSH = inactive", source="obs",
                          observer="observer", experience_refs=[e1])
    k2 = knowledge.create(st, content="SSH = active", source="obs",
                          observer="observer", experience_refs=[e2])
    knowledge.declare_conflict(st, k1["knowledge_id"], k2["knowledge_id"])
    a1 = knowledge.read(st, k1["knowledge_id"])
    a2 = knowledge.read(st, k2["knowledge_id"])
    check("K2a: обе записи существуют (не уничтожены)",
          a1 is not None and a2 is not None)
    check("K2b: обе помечены conflicted",
          a1["status"] == "conflicted" and a2["status"] == "conflicted")
    check("K2c: взаимные ссылки конфликта",
          k2["knowledge_id"] in a1["conflicts_with"]
          and k1["knowledge_id"] in a2["conflicts_with"])
    # версии: v1 (active) обеих остались в истории
    v1 = knowledge.versions(st, k1["knowledge_id"])
    v2 = knowledge.versions(st, k2["knowledge_id"])
    check("K2d: история хранит обе версии каждой записи",
          len(v1) == 2 and v1[0]["status"] == "active"
          and len(v2) == 2 and v2[0]["status"] == "active")


def k3_retract():
    st = _fresh_store()
    eid = _mk_experience(st)
    k = knowledge.create(st, content="X помогает", source="exp",
                         observer="eval", experience_refs=[eid],
                         confidence=0.8)
    kid = k["knowledge_id"]
    r = knowledge.retract(st, kid, by="operator", note="X был ошибкой")
    check("K3a: запись осталась (последняя версия = retracted)",
          r["status"] == "retracted")
    check("K3b: версия выросла (v1→v2)", r["version"] == 2)
    hist = [h["op"] for h in r["history"]]
    check("K3c: история сохранила add+retract", hist == ["add", "retract"])
    check("K3d: provenance не исчез (experience_refs целы)",
          r["experience_refs"] == [eid])
    v1 = knowledge.versions(st, kid)[0]
    check("K3e: исходная v1 не изменена (active, content цел)",
          v1["status"] == "active" and v1["content"] == "X помогает")


def k4_restore():
    st = _fresh_store()
    eid = _mk_experience(st)
    k = knowledge.create(st, content="Y верно", source="exp",
                         observer="eval", experience_refs=[eid])
    kid = k["knowledge_id"]
    knowledge.retract(st, kid, by="operator", note="отзыв")
    r2 = knowledge.restore(st, kid, by="operator", note="восстановлено")
    check("K4a: после restore статус active", r2["status"] == "active")
    check("K4b: версия v3", r2["version"] == 3)
    hist = [h["op"] for h in r2["history"]]
    check("K4c: история показывает add+retract+restore",
          hist == ["add", "retract", "restore"])
    check("K4d: прошлое не переписано (3 версии целы)",
          len(knowledge.versions(st, kid)) == 3)


def k5_append_only():
    st = _fresh_store()
    eid = _mk_experience(st)
    k = knowledge.create(st, content="Z", source="exp", observer="op",
                         experience_refs=[eid])
    # прямая «правка»: та же версия с другим content — дубликат
    tampered = dict(k)
    tampered["content"] = "Z ИСПРАВЛЕНО задним числом"
    ok = st.append_knowledge(tampered)
    check("K5a: повторная запись той же версии отклонена", not ok)
    back = knowledge.read(st, k["knowledge_id"])
    check("K5b: старая запись не изменилась (content цел)",
          back["content"] == "Z" and back["version"] == 1)
    # в Store нет update-пути для knowledge — проверяем API-поверхность
    has_update = any(m.startswith("update") for m in dir(st))
    check("K5c: у хранилища нет update-пути для knowledge", not has_update)


def k6_no_provenance():
    st = _fresh_store()
    try:
        knowledge.create(st, content="Я знаю X", source="", observer="llm",
                         experience_refs=[])
        check("K6a: создание без источника провалилось", False)
    except ValueError:
        check("K6a: создание без источника провалилось", True)
    # ссылка на несуществующий опыт — тоже провал
    try:
        knowledge.create(st, content="X", source="exp", observer="op",
                         experience_refs=["exp_NONEXISTENT"])
        check("K6b: ссылка на несуществующий опыт провалилась", False)
    except ValueError:
        check("K6b: ссылка на несуществующий опыт провалилась", True)


def main():
    k1_roundtrip()
    k2_conflict()
    k3_retract()
    k4_restore()
    k5_append_only()
    k6_no_provenance()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ KNOWLEDGE: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
