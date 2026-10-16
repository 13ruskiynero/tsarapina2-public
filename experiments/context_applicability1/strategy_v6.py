# -*- coding: utf-8 -*-
"""strategy_v6 — experimental ветка CONTEXT-APPLICABILITY-1 (06.09).

Дизайн: CONTEXT_APPLICABILITY1_DESIGN.md (FROZEN). Основная Strategy
v0.3 (strategy.py) НЕ меняется. v6 = полный маршрут v0.3 с ОДНОЙ
модификацией — контекстная адресация в S2-эксплуатации exact-пула:

  (symptom, current_context) → eligible Knowledge → S2

- ctx знания: по цепочке knowledge → опыт → ПОСЛЕДНЕЕ действие →
  args.ctx_extra (условие, при котором последствие проверялось);
  знание с ctx=None НЕ фильтруется (совместимость со старыми
  знаниями: пригодно всегда);
- ctx_now передаётся параметром (читает драйвер через envfact-
  сенсор); ctx_now=None → фильтр выключен (поведение v0.3);
- eligible = exact-знания с ctx(r)==ctx_now (+ ctx=None); recency
  ТОЛЬКО внутри eligible (tie-break);
- exact есть, но eligible пуст → S3-стоп (rule: context_mismatch),
  НЕ exploration (цена: новый learn; stale-recovery здесь НЕ
  проверяется);
- все остальные ветки (conflict → S3; exact-пусто → SEB routing:
  broad-гипотеза/exploration; S1) — поведение v0.3 без изменений.

Без trust; без recency как основного; без вывода ctx из результата
(ctx — наблюдаемый факт среды, фиксируется при проверке действия);
без изменения Knowledge/Update/Experience API.
"""
import hashlib
import json
import re
import time

from strategy import strategy as base  # noqa: E402

S1, S2, S3, S4, S5 = base.S1, base.S2, base.S3, base.S4, base.S5


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _symptom_of(text):
    m = re.search(r"symptom=([a-z0-9_ ]+)", (text or "").lower())
    if not m:
        return frozenset()
    return frozenset(re.findall(r"[a-z0-9]+", m.group(1)))


def _rec_symptom(store, rec):
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        s = _symptom_of(exp.get("problem", ""))
        if s:
            return s
    return frozenset()


def _relevant(store, rec, task_tokens):
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        if _tokens(exp.get("problem", "")) & task_tokens:
            return True
    return False


def _snapshot(store):
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


def _ctx_extra_of(store, rec):
    """Контекст проверки знания: последнее действие опыта → args.
    ctx_extra (None, если не зафиксирован)."""
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


def _ctx_of(rec):
    m = re.search(r"outcome=(\w+)", rec.get("context", "") or "")
    return m.group(1) if m else ""


def suggest(store, task, by="strategy_v6/deterministic", save=True,
            banned_commands=None, ctx_now=None):
    """CA-1: v0.3 + контекстная адресация exact-пула."""
    problem = task.get("problem", "")
    task_tokens = _tokens(problem)
    banned = set(banned_commands or [])
    snapshot = _snapshot(store)

    rel = []
    for s in snapshot:
        rec = store.read_knowledge(s["knowledge_id"])
        if rec is None:
            continue
        if _relevant(store, rec, task_tokens):
            rel.append(rec)

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

    if conflicted_pairs:
        strategy_id = S3
        candidate_actions = base._observe_actions()
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
            # INSUFFICIENCY ROUTING (v0.3, без изменений)
            hyp = None
            if not banned:
                broad_cands = [r for r in rel if _ctx_of(r) != "failure"]
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
                            base._last_candidate_action(store, eid))
                        rationale.append({
                            "rule": "broad_hypothesis",
                            "knowledge_id": hyp["knowledge_id"],
                            "knowledge_version": hyp["version"],
                            "experience_id": eid,
                            "note": "exact-знание о симптоме отсутствует: "
                                    "одна проверка broad-гипотезы, НЕ "
                                    "эксплуатация"})
            if hyp is None and strategy_id is None:
                strategy_id = S1
                exploration = True
                candidate_actions = base._observe_actions()
                knowledge_refs = sorted({r["knowledge_id"] for r in rel})
                rationale.append({
                    "rule": "insufficiency_exploration",
                    "note": "точного знания о симптоме нет, broad-"
                            "гипотеза не подтвердилась: уступить "
                            "систематическому поиску (перебор)"})
        else:
            # S2-эксплуатация: CA-1 контекстная адресация exact-пула
            pool = exact if exact else rel
            if exact and ctx_now is not None:
                # eligible: знания, проверенные при ctx == ctx_now,
                # плюс знания без зафиксированного ctx (старые)
                eligible = []
                for r in pool:
                    c = _ctx_extra_of(store, r)
                    if c is None or c == ctx_now:
                        eligible.append(r)
                if eligible:
                    pool = eligible
                    context_filter_used = True
                else:
                    # exact есть, но пригодных нет → S3-стоп
                    strategy_id = S3
                    candidate_actions = base._observe_actions()
                    knowledge_refs = sorted({r["knowledge_id"]
                                             for r in exact})
                    for r in exact:
                        c = _ctx_extra_of(store, r)
                        rationale.append({
                            "rule": "context_mismatch",
                            "knowledge_id": r["knowledge_id"],
                            "ctx_knowledge": c,
                            "ctx_now": ctx_now,
                            "note": "exact-знание проверено при ctx=%s, "
                                    "текущий ctx=%s: вне контекста "
                                    "проверки; не применять вслепую "
                                    "(S3; цена — новый learn)" % (c,
                                                                   ctx_now)})
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
                        base._last_candidate_action(store, eid))
                    rationale.append({
                        "rule": "known_fix_context" if
                        context_filter_used else "known_fix",
                        "knowledge_id": chosen["knowledge_id"],
                        "knowledge_version": chosen["version"],
                        "experience_id": eid,
                        "ctx_knowledge": _ctx_extra_of(store, chosen),
                        "ctx_now": ctx_now,
                        "note": "знание связывает опыт %s с этим классом "
                                "задачи; действие, чьё последствие "
                                "зафиксировано при ctx=%s"
                                % (eid, ctx_now),
                        "relevance": "symptom-exact" if exact else "broad"})
        if not candidate_actions and strategy_id in (S2,):
            candidate_actions = base._observe_actions()
            if not rationale or rationale[-1].get("rule") != "broad_hypothesis":
                rationale.append({"rule": "no_actions_in_experience",
                                  "note": "в опыте знания не было действий"})
    else:
        strategy_id = S1
        candidate_actions = base._observe_actions()
        rationale.append({"rule": "no_relevant_knowledge",
                          "note": "нет знания по этому классу задачи; "
                                  "сначала наблюдения"})

    key = json.dumps({
        "task": problem, "strategy": strategy_id,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "ctx_now": ctx_now,
        "snapshot": [(s["knowledge_id"], s["version"]) for s in snapshot],
    }, ensure_ascii=False, sort_keys=True)
    sug_id = "sug6_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

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
        "strategy_version": "0.3+CA1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if save:
        store.append_suggestion(sug)
    return sug
