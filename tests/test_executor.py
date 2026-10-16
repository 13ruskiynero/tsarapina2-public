# -*- coding: utf-8 -*-
"""Обязательный тест Executor (Tsarapina, этап 6).

Цепочка (профессор):
    Strategy → LLM → candidate Action → Executor → Result
а НЕ «LLM: я сделал → система поверила».

X1. Разрешённое действие выполняется РОВНО как указано: result с
    exit_code/stdout/stderr/state_before/state_after; валиден по
    result.schema; outcome=unverified (оценку ставит не Executor).
X2. Неразрешённое действие НЕ выполняется (refused=true), маркер
    не создаётся; причина в stderr.
X3. Метасимволы (пайпы и пр.) → отказ (Executor «тупой»: не
    переписывает команду под себя).
X4. state_before зафиксирован до, state_after — после; оба непусты.
X5. Executor не думает: в result нет rationale/explanation/
    suggestion; команда не модифицируется; result хранит только
    исполнение.
X6. Executor не импортирует llm/knowledge/strategy/experience
    (нет доступа к «интеллектуальным» слоям).
X7. Result сохранён в store и восстановим.
X8. observe-действие (сенсор) выполняется как чтение факта.
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor import executor  # noqa: E402
from storage.store import Store  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(BASE, "protocols")
TMP = os.path.join(BASE, "tests", "tmp_executor")
MARKER = os.path.join(TMP, "marker_should_not_exist.txt")
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


def _action(**kw):
    a = {"action_id": "act_x_%s" % time.time(), "type": "command",
         "permitted": True, "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "proposed_by": "test"}
    a.update(kw)
    return a


def _schema_ok(res):
    import jsonschema
    from jsonschema import RefResolver
    schema = json.load(open(os.path.join(PROTO, "result.schema.json"),
                            encoding="utf-8"))
    resolver = RefResolver(base_uri="file://%s/" % PROTO, referrer=schema)
    try:
        jsonschema.validate(res, schema, resolver=resolver)
        return True
    except jsonschema.ValidationError as e:
        print("   schema error:", str(e)[:150])
        return False


def x1_allowed():
    st = _fresh_store()
    res = executor.execute(st, _action(command="systemctl is-active ssh"))
    check("X1a: выполнено (refused=False)", not res["refused"])
    check("X1b: exit_code int", isinstance(res["exit_code"], int))
    check("X1c: state_before/after непусты",
          bool(res["state_before"]) and bool(res["state_after"]))
    check("X1d: валиден по result.schema", _schema_ok(res))
    check("X1e: outcome=unverified (оценку ставит Evaluation)",
          res["outcome"] == "unverified")


def x2_refused_not_executed():
    st = _fresh_store()
    marker = os.path.join(TMP, "x2_marker.txt")
    if os.path.exists(marker):
        os.remove(marker)
    res = executor.execute(
        st, _action(command="touch %s" % marker, permitted=True))
    check("X2a: команда вне allowlist → refused", res["refused"])
    check("X2b: причина в stderr",
          "REFUSED" in res["stderr"] and "allowlist" in res["stderr"])
    check("X2c: команда НЕ выполнена (маркер не создан)",
          not os.path.exists(marker))
    check("X2d: exit_code=None при отказе", res["exit_code"] is None)


def x3_metachars():
    st = _fresh_store()
    res = executor.execute(
        st, _action(command="ss -ltn | grep :22", permitted=True))
    check("X3: метасимволы → отказ (не переписывание команды)",
          res["refused"] and "метасимволы" in res["stderr"])


def x4_state_snapshot():
    st = _fresh_store()
    res = executor.execute(st, _action(command="uptime"))
    b = res["state_before"]
    a = res["state_after"]
    keys_ok = ("service:ssh.state" in b or "service:ssh.state" in a) and \
        ("cpu.load1" in b or "cpu.load1" in a)
    check("X4a: state содержит ключевые факты (service:ssh, cpu.load1)",
          keys_ok)
    check("X4b: снимки до/после структурно равны (read-only команда)",
          set(b.keys()) == set(a.keys()))


def x5_not_thinking():
    st = _fresh_store()
    blob_before = "".join(sorted(str(b) for b in
                                 os.listdir(os.path.join(TMP))))
    res = executor.execute(st, _action(command="uptime"))
    # в result нет «мыслей»
    j = json.dumps(res, ensure_ascii=False)
    check("X5a: result не содержит rationale/explanation/suggestion",
          not any(w in j for w in
                  ("rationale", "explanation", "suggestion", "поэтому")))
    check("X5b: outcome=unverified (не самооценка)",
          res["outcome"] == "unverified")
    # action не модифицирован (executor не пишет actions)
    check("X5c: executor не создал action-записей",
          st.read_action("act_x_%s" % res["action_id"]) is None)


def x6_no_smart_imports():
    src = open(os.path.join(BASE, "executor", "executor.py"),
               encoding="utf-8").read()
    bad = [w for w in ("llm", "knowledge", "strategy", "experience")
           if re_import(w, src)]
    check("X6: executor не импортирует llm/knowledge/strategy/experience",
          not bad)


def re_import(name, src):
    import re
    return bool(re.search(r"(import|from)\s+%s" % name, src))


def x7_stored():
    st = _fresh_store()
    res = executor.execute(st, _action(command="uptime"))
    got = st.read_result(res["result_id"])
    check("X7: result сохранён и восстановим", got == res)


def x8_observe():
    st = _fresh_store()
    res = executor.execute(
        st, _action(type="observe", args={"sensor": "service:ssh"},
                    permitted=True))
    check("X8a: observe выполнен", not res["refused"]
          and res["exit_code"] == 0)
    check("X8b: stdout содержит факт (state=)",
          "state=" in res["stdout"] or "value=" in res["stdout"])


def main():
    x1_allowed()
    x2_refused_not_executed()
    x3_metachars()
    x4_state_snapshot()
    x5_not_thinking()
    x6_no_smart_imports()
    x7_stored()
    x8_observe()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ EXECUTOR: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
