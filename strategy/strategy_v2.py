# -*- coding: utf-8 -*-
"""Strategy v2 (RELEVANCE-1, экспериментальная ветка).

Отдельный модуль: рабочий strategy.py (19/19) НЕ тронут. Тот же
формат suggestion; изменён только выбор знания в S2-ветке через
детерминированные фильтры (флаги):
- R1 symptom-match: знания, чей симптом (symptom=... опыта) ТОЧНО
  совпадает с симптомом задачи, имеют приоритет; иначе — широкий
  fallback (как v1);
- R2 no-failure-action: знания «НЕ перевело» не выбираются как
  источник S2 (сами знания, conflict, provenance НЕ трогаются —
  семантика Knowledge не меняется);
- R3 класс-с-max-успехами: при нескольких классах-претендентах —
  класс с наибольшим числом успешных знаний; внутри — recency
  (version, created_at).

S3-ветка (конфликт) и S1 (нет знания) — БЕЗ изменений.
"""
import hashlib
import json
import re
import time

from strategy import strategy as base

S1, S2, S3 = base.S1, base.S2, base.S3


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


def _is_failure(rec):
    return "НЕ перевело" in rec.get("content", "")


def _select(store, rel, task_sym, flags):
    """Детерминированный выбор знания для S2 по флагам."""
    r1, r2, r3 = flags.get("r1"), flags.get("r2"), flags.get("r3")
    cands = list(rel)
    if r1 and task_sym:
        exact = [r for r in cands if _rec_symptom(store, r) == task_sym]
        if exact:
            cands = exact
    if r2:
        cands = [r for r in cands if not _is_failure(r)]
    if r3 and len(cands) > 1:
        classes = {}
        for r in cands:
            sym = _rec_symptom(store, r)
            key = tuple(sorted(sym)) or ("unknown",)
            classes.setdefault(key, []).append(r)
        best_key = max(classes, key=lambda k: len(classes[k]))
        cands = classes[best_key]
    if not cands:
        return None
    cands.sort(key=lambda r: (r["version"], r["created_at"]))
    return cands[-1]


def suggest(store, task, flags=None, by="strategy/relevance1",
            save=True):
    """То же, что strategy.suggest, но выбор S2 через _select."""
    flags = flags or {"r1": True, "r2": True, "r3": True}
    problem = task.get("problem", "")
    toks = base._tokens(problem)
    task_sym = _symptom_of(problem)

    snapshot = base._snapshot(store)
    rel = []
    for s in snapshot:
        rec = store.read_knowledge(s["knowledge_id"])
        if rec is None:
            continue
        if base._relevant(store, rec, toks):
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
        chosen = _select(store, rel, task_sym, flags)
        if chosen is None:
            strategy_id = S1
            candidate_actions = base._observe_actions()
            rationale.append({"rule": "no_applicable_knowledge",
                              "note": "релевантные знания есть, но "
                                      "неприменимы как исправление "
                                      "(неудачи); сначала наблюдения"})
        else:
            strategy_id = S2
            knowledge_refs = [chosen["knowledge_id"]]
            for eid in chosen.get("experience_refs", []):
                exp = store.read_experience(eid)
                if exp is None:
                    continue
                experience_refs.append(eid)
                acts = base._actions_from_experience(store, eid)
                if acts:
                    candidate_actions.extend(acts)
                rationale.append({
                    "rule": "known_fix",
                    "knowledge_id": chosen["knowledge_id"],
                    "knowledge_version": chosen["version"],
                    "experience_id": eid,
                    "note": "знание связывает опыт %s с этим классом "
                            "задачи; повторяю действия опыта" % eid,
                    "flags": {k: bool(v) for k, v in flags.items()}})
            if not candidate_actions:
                candidate_actions = base._observe_actions()
                rationale.append({"rule": "no_actions_in_experience",
                                  "note": "в опыте знания не было "
                                          "действий"})
    else:
        strategy_id = S1
        candidate_actions = base._observe_actions()
        rationale.append({"rule": "no_relevant_knowledge",
                          "note": "нет знания по этому классу задачи; "
                                  "сначала наблюдения"})

    key = json.dumps({
        "task": problem, "strategy": strategy_id,
        "flags": {k: bool(v) for k, v in sorted(flags.items())},
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
        "llm_request": strategy_id == base.S5,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if save:
        store.append_suggestion(sug)
    return sug
