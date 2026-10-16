# -*- coding: utf-8 -*-
"""Strategy (Tsarapina, этап 5; до LLM-адаптера).

Strategy получает: текущую задачу + доступное Knowledge (+ опыты за
ними). Возвращает suggestion: candidate actions + rationale +
knowledge_refs + knowledge_snapshot (что было доступно НА МОМЕНТ
решения — запечатано версиями).

Правила (FIXED):
- rationale НЕ становится знанием автоматически: suggest() ничего
  не пишет в knowledge/experience;
- suggestion детерминирован: suggestion_id = hash(task + выбранная
  стратегия + refs + версии snapshot) — повторный suggest при том же
  состоянии даёт тот же suggestion;
- стратегии первой версии: S1 проверить (диагностика), S2 повторить
  известное исправление (из опыта знания), S3 собрать доп. данные
  (конфликт), S4 откатить последнее действие, S5 запросить план у
  процессора (LLM — позже; сейчас помечает llm_request);
- конфликт не разрешается молча: при конфликте релевантных знаний →
  S3 + rationale с обеими ссылками;
- LLM здесь НЕ хозяин памяти: процессор предложения подключается
  позже (этап 5b/4).

 RESEARCHABLE (не решать): взвешивание знаний, обучение выбору
 стратегий, стоимость стратегии, конкуренция стратегий.

Версия 0.6 (07.09.2026, integration gate v0.6): applicable_when-
адресация (ACQ-1): знание с полем applicable_when проверяется по
текущим наблюдениям; legacy-путь v0.5 сохранён.

Ветка AA-1 (10.09.2026, experiments/applicability_addressing1):
A1 = no-failure-action — failure-знания (outcome != "success")
исключаются из S2-пула ВЫБОРА строго ДО цикла matching (утверждено
профессором; дизайн AA-1 FROZEN). Это КОПИЯ strategy.py v0.6.x с
ЕДИНСТВЕННОЙ этой правкой; файл слоя strategy/strategy.py НЕ
изменяется. Все прочие функции — байт-в-байт как в слое.

Версия 0.3 (06.09.2026, integration gate): contextual exploitation
+ insufficiency routing. Эксплуатация — при symptom-exact знании;
при симптоме без exact — ОДНА broad-гипотеза (hypothesis=True),
при её не-success в эпизоде — exploration=True (систематический
поиск контура). Кандидат знания — действие, чьё последствие
зафиксировано (последнее действие опыта). Trust не вводится;
конфликт → S3; знание нового класса — только из проверенного
последствия. См. INTEGRATION_V03_REPORT.md.
"""
import hashlib
import json
import re
import time

OBSERVE_SENSORS = ["service:ssh", "ports", "process:sshd", "disk",
                   "memory", "load", "log:ssh"]

S1 = "S1"   # проверить (стандартная диагностика)
S2 = "S2"   # повторить известное исправление
S3 = "S3"   # собрать дополнительные данные
S4 = "S4"   # откатить последнее действие
S5 = "S5"   # запросить план у процессора (LLM)


def _tokens(text):
    """Нормализованные токены для детерминированного матчинга."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _symptom_of(text):
    """Симптом из problem-строки: symptom=a b -> frozenset({'a','b'})."""
    m = re.search(r"symptom=([a-z0-9_ ]+)", (text or "").lower())
    if not m:
        return frozenset()
    return frozenset(re.findall(r"[a-z0-9]+", m.group(1)))


def _rec_symptom(store, rec):
    """Симптом знания — по первому опыту, у которого он есть."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        s = _symptom_of(exp.get("problem", ""))
        if s:
            return s
    return frozenset()


def _ctx_extra_of(store, rec):
    """Контекст проверки знания (v0.4, CA-1): последнее действие
    опыта → args.ctx_extra; None, если не зафиксирован (старое
    знание — legacy addressing, без искусственного контекста)."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        actions = exp.get("actions", [])
        if not actions:
            continue
        a = store.read_action(actions[-1])
        if a and "ctx_extra" in (a.get("args") or {}):
            return a["args"]["ctx_extra"]
    return None


def _addr_cmd_of(store, rec):
    """Адрес знания: (симптом-set, ctx, команда) — из последнего
    действия опыта (v0.5, TE-1)."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        sym = _symptom_of(exp.get("problem", ""))
        actions = exp.get("actions", [])
        if not actions:
            return None
        a = store.read_action(actions[-1])
        if a is None:
            return None
        ctx = (a.get("args") or {}).get("ctx_extra")
        return (frozenset(sym), ctx, a.get("command"))
    return None


def _e2_history(store, sym, ctx, cmd):
    """История знаний того же (адрес, команда), свежайшие первыми."""
    rows = []
    for v in store.read_knowledge_versions_all():
        key = _addr_cmd_of(store, v)
        if key is None:
            continue
        s, c, cm = key
        if s == sym and c == ctx and cm == cmd:
            rows.append(v)
    rows.sort(key=lambda v: v.get("created_at", ""), reverse=True)
    return rows


def _non_success(out):
    return out in ("failure", "partial")


def _relevant(store, rec, task_tokens):
    """Знание релевантно задаче, если problem хотя бы одного его
    опыта пересекается с токенами задачи (≥1 общий токен)."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        pt = _tokens(exp.get("problem", ""))
        if pt & task_tokens:
            return True
    return False


def _snapshot(store):
    """Все записи knowledge с их ПОСЛЕДНИМИ версиями на момент
    решения (status active/conflicted). Запечатывается в suggestion."""
    kids = set()
    for ver in store.read_knowledge_versions_all():
        kids.add(ver["knowledge_id"])
    out = []
    for kid in sorted(kids):
        latest = store.read_knowledge(kid)
        if latest is None:
            continue
        if latest.get("status") in ("active", "conflicted"):
            out.append({"knowledge_id": kid, "version": latest["version"],
                        "status": latest["status"],
                        "content": latest["content"]})
    return out


def _observe_actions():
    return [{"type": "observe", "sensor": s} for s in OBSERVE_SENSORS]


def _last_candidate_action(store, eid):
    """Кандидат знания = действие, чьё последствие зафиксировано:
    ПОСЛЕДНЕЕ действие опыта (update фиксирует исход последнего
    действия; опыт exploration содержит много действий — знание
    относится только к последнему). Замена v0.2-извлечения «все
    действия опыта» (скрытый multi-action дефект, найден в SEB-1;
    для одно-действенных опытов поведение не меняется)."""
    exp = store.read_experience(eid)
    if exp is None:
        return []
    actions = exp.get("actions", [])
    if not actions:
        return []
    aid = actions[-1]
    a = store.read_action(aid)
    if a is None or a.get("type") != "command" or not a.get("command"):
        return []
    return [{"type": "command", "command": a["command"],
             "action_ref": aid, "experience_ref": eid}]


_AA1_OUTCOME_RE = re.compile(r"outcome=(\w+)")


def _aa1_outcome_is_success(rec):
    """AA-1/A1: outcome знания из context записи ('success' иначе
    failure/partial/None)."""
    m = _AA1_OUTCOME_RE.search(rec.get("context") or "")
    return bool(m and m.group(1) == "success")


def suggest(store, task, by="strategy/deterministic", save=True,
            banned_commands=None, ctx_now=None, obs_now=None):
    """Сформировать предложение для задачи task={'problem': str}.

    v0.6 (integration gate, ACQ-1): applicable_when-адресация.
    Знание с полем applicable_when проверяется по текущим наблюдениям
    obs_now={факт: значение} (E — ctx_now; расширяемо); поле
    отсутствует → legacy-путь v0.5 (ctx из args действия). obs_now=None
    → наблюдения = {"E": ctx_now}. Непроверяемое условие → знание не
    применяется (S3), legacy-семантика сохранена.

    Strategy v0.4 — contextual exploitation + insufficiency routing
    + applicability addressing (CA-1, integration gate v0.4):
    - (symptom, context) — адрес exact-знания: при ctx_now и знаниях
      с ctx_extra (условие проверки) S2-пул = exact с ctx==ctx_now
      или без ctx (legacy); recency — только tie-break;
    - exact есть, пригодных нет → S3 (context_mismatch; цена —
      новый learn; НЕ exploration);
    - знания без ctx не отбрасываются и не получают искусственный
      контекст (legacy addressing v0.3);
    (интеграция M2/SEB-1 по integration gate):
    - задача с симптомом, exact-знание ЕСТЬ → S2-эксплуатация
      (recency в exact-пуле; шум/повторы обрабатываются зоной-3:
      recency, конфликт → S3);
    - задача с симптомом, exact-знания НЕТ (broad-релевантность):
      broad-знание НЕ эксплуатируется: ОДНА гипотеза (свежайшее
      non-failure broad-знание, hypothesis=True; banned_commands
      пуст) → при её не-success в эпизоде (banned_commands непуст) →
      exploration=True (передаёт управление систематическому поиску
      контура; право искать, НЕ право знать, что искать);
    - кандидат знания = действие, чьё последствие зафиксировано
      (последнее действие опыта; multi-action fix);
    - conflicted → S3 (зона 3 не ломается); trust не появляется;
      маршрутизация не создаёт знания и не меняет Knowledge/Update.

    Возвращает suggestion (и сохраняет в store, если save)."""
    problem = task.get("problem", "")
    task_tokens = _tokens(problem)
    banned = set(banned_commands or [])

    # 1. доступное знание на момент решения
    snapshot = _snapshot(store)

    # 2. релевантные знания (по токенам problem их опытов)
    rel = []
    for s in snapshot:
        rec = store.read_knowledge(s["knowledge_id"])
        if rec is None:
            continue
        if _relevant(store, rec, task_tokens):
            rel.append(rec)

    # 3. конфликты среди релевантных
    rel_ids = [r["knowledge_id"] for r in rel]
    conflicted_pairs = []
    for r in rel:
        for c in r.get("conflicts_with", []):
            if c in rel_ids and c > r["knowledge_id"]:
                conflicted_pairs.append((r["knowledge_id"], c))

    rationale = []
    candidate_actions = []
    strategy_id = None
    knowledge_refs = []
    experience_refs = []
    hypothesis = False
    exploration = False
    context_filter_used = False
    ctx_mismatch = False

    def _ctx_of(rec):
        """Исход знания из context ('outcome=...')."""
        m = re.search(r"outcome=(\w+)", rec.get("context", "") or "")
        return m.group(1) if m else ""

    if conflicted_pairs:
        # конфликт не разрешаем молча → S3
        strategy_id = S3
        candidate_actions = _observe_actions()
        knowledge_refs = sorted({p for pair in conflicted_pairs
                                 for p in pair})
        for a, b in conflicted_pairs:
            rationale.append({"rule": "conflict",
                              "knowledge_refs": [a, b],
                              "note": "знания противоречат друг другу; "
                                      "нужны дополнительные данные"})
        for kid in knowledge_refs:
            rec = store.read_knowledge(kid)
            if rec:
                experience_refs += rec.get("experience_refs", [])
    elif rel:
        task_sym = _symptom_of(problem)
        exact = []
        if task_sym:
            exact = [r for r in rel if _rec_symptom(store, r) == task_sym]

        if task_sym and not exact:
            # INSUFFICIENCY ROUTING (M2): точного знания о симптоме нет
            hyp = None
            if not banned:
                # ОДНА broad-гипотеза: свежайшее non-failure знание
                broad_cands = [r for r in rel
                               if _ctx_of(r) != "failure"]
                broad_cands.sort(key=lambda r: (r["version"],
                                                r["created_at"]))
                hyp = broad_cands[-1] if broad_cands else None
                if hyp is not None:
                    strategy_id = S2
                    hypothesis = True
                    knowledge_refs = [hyp["knowledge_id"]]
                    for eid in hyp.get("experience_refs", []):
                        exp = store.read_experience(eid)
                        if exp is None:
                            continue
                        experience_refs.append(eid)
                        candidate_actions.extend(
                            _last_candidate_action(store, eid))
                        rationale.append({
                            "rule": "broad_hypothesis",
                            "knowledge_id": hyp["knowledge_id"],
                            "knowledge_version": hyp["version"],
                            "experience_id": eid,
                            "note": "exact-знание о симптоме отсутствует: "
                                    "одна проверка broad-гипотезы, НЕ "
                                    "эксплуатация"})
            if hyp is None and strategy_id is None:
                # гипотеза уже проверена/невозможна → exploration
                strategy_id = S1
                exploration = True
                candidate_actions = _observe_actions()
                knowledge_refs = sorted({r["knowledge_id"] for r in rel})
                rationale.append({
                    "rule": "insufficiency_exploration",
                    "note": "точного знания о симптоме нет, broad-"
                            "гипотеза не подтвердилась: уступить "
                            "систематическому поиску (перебор)"})
        else:
            # S2-эксплуатация: recency в exact-пуле (или broad,
            # если симптома нет вовсе); v0.4 (CA-1): контекстная
            # адресация exact-пула; v0.6: applicable_when-адресация
            # (ACQ-1): знание с полем проверяется по наблюдениям;
            # legacy-знания без поля — ctx-путь v0.5
            pool = exact if exact else rel
            # AA-1/A1 (no-failure-action; FROZEN 10.09.2026): фильтр
            # строго ДО цикла matching — failure-derived knowledge НЕ
            # попадает в тот же selection path.
            pool = [r for r in pool if _aa1_outcome_is_success(r)]
            has_aw = any(r.get("applicable_when") is not None
                         for r in pool)
            obs = obs_now if obs_now is not None else (
                {"E": ctx_now} if ctx_now is not None else None)
            if exact and (ctx_now is not None or has_aw):
                n_pool = len(pool)

                def _match(r):
                    aw = r.get("applicable_when")
                    if aw is not None:
                        if obs is None:
                            return False   # поле есть, наблюдений нет
                        return all(obs.get(k) == v
                                   for k, v in aw.items())
                    c = _ctx_extra_of(store, r)
                    return c is None or c == ctx_now

                eligible = [r for r in pool if _match(r)]
                if eligible:
                    pool = eligible
                    # флаг: фильтр реально ОТСЕЯЛ кандидатов
                    # (иначе — legacy-знания без ctx: filter inactive)
                    context_filter_used = len(eligible) < n_pool
                else:
                    # exact есть, пригодных по условиям нет → S3
                    strategy_id = S3
                    ctx_mismatch = True
                    candidate_actions = _observe_actions()
                    knowledge_refs = sorted({r["knowledge_id"]
                                             for r in exact})
                    for r in exact:
                        c = _ctx_extra_of(store, r)
                        aw = r.get("applicable_when")
                        if aw is not None:
                            why = ("applicable_when=%s, наблюдения=%s"
                                   % (aw, obs))
                        else:
                            why = ("проверено при ctx=%s, текущий ctx=%s"
                                   % (c, ctx_now))
                        rationale.append({
                            "rule": "context_mismatch",
                            "knowledge_id": r["knowledge_id"],
                            "ctx_knowledge": c,
                            "ctx_now": ctx_now,
                            "applicable_when": aw,
                            "note": "exact-знание вне условий "
                                    "применимости: %s; не применять "
                                    "вслепую (S3; цена — новый learn)"
                                    % why})
                    for kid in knowledge_refs:
                        rec = store.read_knowledge(kid)
                        if rec:
                            experience_refs += rec.get("experience_refs",
                                                       [])
            if strategy_id is None:
                pool.sort(key=lambda r: (r["version"], r["created_at"]))
                chosen = pool[-1]
                strategy_id = S2
                knowledge_refs = [chosen["knowledge_id"]]
                for eid in chosen.get("experience_refs", []):
                    exp = store.read_experience(eid)
                    if exp is None:
                        continue
                    experience_refs.append(eid)
                    candidate_actions.extend(
                        _last_candidate_action(store, eid))
                    rationale.append({
                        "rule": "known_fix",
                        "knowledge_id": chosen["knowledge_id"],
                        "knowledge_version": chosen["version"],
                        "experience_id": eid,
                        "note": "знание связывает опыт %s с этим классом "
                                "задачи; повторяю действие, чьё последствие "
                                "зафиксировано" % eid,
                        "relevance": "symptom-exact" if exact
                        else "broad"})
        # если в опыте не было действий — диагностика
        if not candidate_actions and strategy_id in (S2,):
            candidate_actions = _observe_actions()
            if not rationale or rationale[-1].get("rule") != "broad_hypothesis":
                rationale.append({"rule": "no_actions_in_experience",
                                  "note": "в опыте знания не было действий"})
    else:
        # нет релевантного знания → S1 диагностика
        strategy_id = S1
        candidate_actions = _observe_actions()
        rationale.append({"rule": "no_relevant_knowledge",
                          "note": "нет знания по этому классу задачи; "
                                  "сначала наблюдения"})

    # детерминированный id по состоянию решения
    key = json.dumps({
        "task": problem, "strategy": strategy_id,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "snapshot": [(s["knowledge_id"], s["version"]) for s in snapshot],
    }, ensure_ascii=False, sort_keys=True)
    sug_id = "sug_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

    sug = {
        "schema_version": "0.1",
        "suggestion_id": sug_id,
        "task": {"problem": problem},
        "strategy_id": strategy_id,
        "candidate_actions": candidate_actions,
        "rationale": rationale,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "knowledge_snapshot": snapshot,
        "experience_refs": sorted(set(experience_refs)),
        "by": by,
        "llm": None,
        "llm_request": strategy_id == S5,
        "hypothesis": hypothesis,
        "exploration": exploration,
        "ctx_now": ctx_now,
        "context_filter_used": context_filter_used,
        "ctx_mismatch": ctx_mismatch,
        "strategy_version": "0.6",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # v0.5: transition event E2 (TE-1) — пост-обработка на S2-
    # эксплуатации: второй ПОСЛЕДОВАТЕЛЬНЫЙ non-success того же
    # (адрес, команда) → право на exploration (событие НЕ объявляет
    # знание устаревшим; выбор не меняется, key не зависит от event)
    if strategy_id == S2 and candidate_actions and knowledge_refs:
        rec0 = store.read_knowledge(knowledge_refs[0])
        key_ac = _addr_cmd_of(store, rec0) if rec0 else None
        if key_ac is not None:
            sym, ctx, cmd = key_ac
            hist = _e2_history(store, sym, ctx, cmd)
            if len(hist) >= 2 and _non_success(_ctx_of(hist[0])) \
                    and _non_success(_ctx_of(hist[1])):
                sug["exploration"] = True
                sug["event"] = "E2_TRANSITION"
                sug["strategy_version"] = "0.6"
                sug["rationale"] = rationale + [{
                    "rule": "e2_transition",
                    "note": "второй последовательный non-success того же "
                            "(адрес, команда): накопленного события "
                            "достаточно для перехода exact → exploration"}]
    if save:
        store.append_suggestion(sug)
    return sug
