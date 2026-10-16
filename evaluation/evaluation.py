# -*- coding: utf-8 -*-
"""Evaluation (Tsarapina, этап 7).

ЖЁСТКОЕ ПРАВИЛО (профессор):
> Evaluation не оценивает модель. Она оценивает соответствие
> результата цели действия.

- оценивает ПО ФАКТАМ state_before/state_after (+ exit_code, refused),
  НЕ по stdout-«настроению» и НЕ по словам модели;
- почти механическая, БЕЗ LLM;
- НЕ меняет Result (result остаётся outcome=unverified; вердикт —
  отдельная evaluation-запись: история не переписывается);
- НЕ придумывает причину успеха;
- НЕ создаёт Knowledge напрямую (это делает Update);
- недостаточно данных → unknown (не failure, не «наверное
  получилось»).

Различения (словарь outcome):
- success      — цель достигнута по фактам state_after;
- failure      — цель НЕ достигнута, состояние не изменилось
                 (действие выполнено, но не помогло);
- partial      — код и факты расходятся / изменение неполное;
- no_change    — действие выполнено, состояние не изменилось
                 (цель не задана — диагностика);
- not_executed — действие не выполнилось (ошибка запуска);
- refused      — действие отклонено политикой Executor'а;
- unknown      — данных недостаточно (свойство цели нет в снимках).

goal — ожидание действия: {"property": "service:ssh.state",
"value": "active"} (кладётся в action.args.goal создателем действия).
"""
import hashlib
import json
import time

OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
OUTCOME_PARTIAL = "partial"
OUTCOME_NO_CHANGE = "no_change"
OUTCOME_NOT_EXECUTED = "not_executed"
OUTCOME_REFUSED = "refused"
OUTCOME_UNKNOWN = "unknown"

RULE = "evaluation/rule:v1"


def verdict(res, goal=None):
    """Вычислить вердикт по фактам result'а. Чистая функция."""
    # 1. отклонено политикой
    if res.get("refused"):
        return OUTCOME_REFUSED
    # 2. не выполнилось (нет кода — ошибка запуска/разбора)
    if res.get("exit_code") is None:
        return OUTCOME_NOT_EXECUTED
    rc = res["exit_code"]
    sb = res.get("state_before", {})
    sa = res.get("state_after", {})

    # 3. цель задана
    if goal and goal.get("property"):
        prop = goal["property"]
        want = goal.get("value")
        before = sb.get(prop)
        after = sa.get(prop)
        if after is None:
            return OUTCOME_UNKNOWN  # свойства нет в снимках
        if after == want:
            if rc != 0:
                return OUTCOME_PARTIAL  # код говорит иначе, факты — да
            return OUTCOME_SUCCESS
        # цель не достигнута
        if before == after:
            return OUTCOME_FAILURE  # ничего не изменилось
        if rc != 0:
            return OUTCOME_FAILURE
        return OUTCOME_PARTIAL  # изменилось, но не к цели

    # 4. цели нет (диагностика): цель = получить данные
    if rc == 0:
        if res.get("stdout") or res.get("stderr"):
            return OUTCOME_SUCCESS  # действие выполнено, данные есть
        return OUTCOME_UNKNOWN
    # rc != 0 без цели: выполнено с ошибкой
    return OUTCOME_FAILURE


def evaluate(store, result_id, goal=None, by=None):
    """Оценить result по его фактам. Result НЕ изменяется;
    вердикт сохраняется отдельной evaluation-записью."""
    res = store.read_result(result_id)
    if res is None:
        raise ValueError("result не найден: %s" % result_id)
    out = verdict(res, goal)
    ev_id = "eval_" + hashlib.sha1(
        ("%s|%s|%s" % (result_id, json.dumps(goal, sort_keys=True,
                                             ensure_ascii=False), out))
        .encode("utf-8")).hexdigest()[:12]
    ev = {
        "schema_version": "0.1",
        "evaluation_id": ev_id,
        "result_id": result_id,
        "action_id": res.get("action_id"),
        "goal": goal,
        "outcome": out,
        "evaluated_by": by or RULE,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "basis": {
            "exit_code": res.get("exit_code"),
            "refused": res.get("refused", False),
            "state_before": res.get("state_before", {}),
            "state_after": res.get("state_after", {}),
        },
    }
    store.append_evaluation(ev)
    return ev
