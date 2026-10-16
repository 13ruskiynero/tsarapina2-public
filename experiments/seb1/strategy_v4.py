# -*- coding: utf-8 -*-
"""strategy_v4 — экспериментальная ветка SEB-1 (Strategy/Exploration
Boundary). Дизайн: SEB1_DESIGN.md (frozen). Основная Strategy v0.2
(R1) НЕ меняется.

Механики-гипотезы (мех — строка):
- M0: v0.2-поведение (контроль);
- M1: local repeat ban — в рамках эпизода действие, давшее
  проверенный не-success на этом симптоме, не предлагается
  повторно; исчерпание кандидатов → S1 (наблюдение);
- M2: exact gate — если задача несёт симптом и exact-пул ПУСТ:
  broad-знания не эксплуатируются: (а) ОДНА гипотеза (свежайшее
  broad-знание, hypothesis=True); (б) после её не-success →
  exploration=True (систематический перебор выполняет контур);
  знание создаётся только из проверенного последствия; exact-
  классы не затронуты;
- M3: M1 + M2.

Маршрутизация M2 — НЕ обобщение: право искать, а не право знать,
что искать. Без trust-чисел; conflicted-пары → S3 (зона 3-защита
не ломается).
"""
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from strategy import strategy as base  # noqa: E402

S1, S2, S3, S5 = base.S1, base.S2, base.S3, base.S5
OUTCOME_RE = re.compile(r"outcome=(\w+)")


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


def _cmd_of(store, rec):
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        for aid in exp.get("actions", []):
            a = store.read_action(aid)
            if a and a.get("command"):
                return a["command"]
    return None


def _rec_cmd(store, rec):
    """Команда-КАНДИДАТ знания: последнее действие первого опыта
    (то, чей исход зафиксирован). Для banned-фильтра M1 — должна
    совпадать с кандидатом S2."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        if exp.get("actions"):
            a = store.read_action(exp["actions"][-1])
            if a and a.get("command"):
                return a["command"]
    return None


def _outcome_of(rec):
    m = OUTCOME_RE.search(rec.get("context", "") or "")
    return m.group(1) if m else ""


def _last_action_cmd(store, eid):
    """Действие, чей result_ref зафиксирован знанием: ПОСЛЕДНЕЕ
    действие опыта (update фиксирует последствие последнего
    действия; опыт exploration содержит много действий — кандидат
    знания = только то, чей исход проверен)."""
    exp = store.read_experience(eid)
    if exp and exp.get("actions"):
        a = store.read_action(exp["actions"][-1])
        if a and a.get("type") == "command" and a.get("command"):
            return [{"type": "command", "command": a["command"]}]
    return []


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


def suggest_v4(store, task, mech="M0", banned_commands=None, by="strategy_v4",
               save=True):
    """banned_commands: команды, уже давшие не-success в этом
    эпизоде (для M1/M3). Возвращает sug с полями hypothesis,
    exploration."""
    banned = set(banned_commands or [])
    problem = task.get("problem", "")
    task_tokens = _tokens(problem)
    snapshot = _snapshot(store)

    rel = []
    for s in snapshot:
        rec = store.read_knowledge(s["knowledge_id"])
        if rec is None:
            continue
        if _relevant(store, rec, task_tokens):
            rel.append(rec)

    task_sym = _symptom_of(problem)
    pool = rel
    exact = []
    if task_sym:
        exact = [r for r in rel if _rec_symptom(store, r) == task_sym]
        if exact:
            pool = exact

    rel_ids = [r["knowledge_id"] for r in rel]
    conflicted_pairs = []
    for r in rel:
        for c in r.get("conflicts_with", []):
            if c in rel_ids and c > r["knowledge_id"]:
                conflicted_pairs.append((r["knowledge_id"], c))

    candidate_actions = []
    knowledge_refs = []
    experience_refs = []
    rationale = []
    strategy_id = None
    hypothesis = False
    exploration = False

    use_m1 = mech in ("M1", "M3")
    use_m2 = mech in ("M2", "M3")

    # conflicted → S3 (зона 3-защита; во всех механиках)
    if conflicted_pairs and not (use_m2 and not exact):
        strategy_id = S3
        candidate_actions = base._observe_actions()
        knowledge_refs = sorted({p for pair in conflicted_pairs
                                 for p in pair})
        for a, b in conflicted_pairs:
            rationale.append({"rule": "conflict",
                              "knowledge_refs": [a, b]})
        for kid in knowledge_refs:
            rec = store.read_knowledge(kid)
            if rec:
                experience_refs += rec.get("experience_refs", [])
    elif not pool:
        strategy_id = S1
        candidate_actions = base._observe_actions()
        rationale.append({"rule": "no_relevant_knowledge"})
    else:
        # M2: exact-пуст → broad только как ОДНА гипотеза
        if use_m2 and task_sym and not exact:
            if not banned:
                broad_cands = [r for r in rel if _outcome_of(r) != "failure"]
                broad_cands.sort(key=lambda r: (r["version"],
                                                r["created_at"]))
                hyp = None
                for r in reversed(broad_cands):
                    cmd = _cmd_of(store, r)
                    if cmd is not None:
                        hyp = r
                        break
            else:
                hyp = None
            if hyp is not None:
                # гипотеза: ОДНА проверка broad-действия (banned пуст)
                strategy_id = S2
                hypothesis = True
                knowledge_refs = [hyp["knowledge_id"]]
                for eid in hyp.get("experience_refs", []):
                    exp = store.read_experience(eid)
                    if exp is None:
                        continue
                    experience_refs.append(eid)
                    candidate_actions.extend(_last_action_cmd(store, eid))
                rationale.append({
                    "rule": "broad_hypothesis",
                    "knowledge_id": hyp["knowledge_id"],
                    "note": "exact-пуст: ОДНА проверка broad-гипотезы; "
                            "не эксплуатация"})
            else:
                # гипотеза уже проверена и не успешна → exploration
                strategy_id = S1
                exploration = True
                candidate_actions = base._observe_actions()
                knowledge_refs = sorted({r["knowledge_id"] for r in rel})
                rationale.append({
                    "rule": "exploration",
                    "note": "точного знания нет, broad-гипотеза не "
                            "подтвердилась: открыт систематический "
                            "поиск (перебор разрешённых команд)"})
        else:
            cands = list(pool)
            if use_m1:
                cands = [r for r in cands
                         if _rec_cmd(store, r) not in banned]
                if not cands:
                    strategy_id = S1
                    candidate_actions = base._observe_actions()
                    knowledge_refs = sorted({r["knowledge_id"]
                                             for r in pool})
                    rationale.append({
                        "rule": "repeat_ban_exhausted",
                        "note": "все релевантные действия уже проверены "
                                "в этом эпизоде с не-success (M1)"})
                else:
                    cands.sort(key=lambda r: (r["version"],
                                              r["created_at"]))
                    chosen = cands[-1]
                    strategy_id = S2
                    knowledge_refs = [chosen["knowledge_id"]]
                    for eid in chosen.get("experience_refs", []):
                        exp = store.read_experience(eid)
                        if exp is None:
                            continue
                        experience_refs.append(eid)
                        candidate_actions.extend(
                            _last_action_cmd(store, eid))
                    rationale.append({
                        "rule": "known_fix",
                        "knowledge_id": chosen["knowledge_id"],
                        "relevance": "symptom-exact" if exact
                        else "broad"})
            else:
                cands.sort(key=lambda r: (r["version"], r["created_at"]))
                chosen = cands[-1]
                strategy_id = S2
                knowledge_refs = [chosen["knowledge_id"]]
                for eid in chosen.get("experience_refs", []):
                    exp = store.read_experience(eid)
                    if exp is None:
                        continue
                    experience_refs.append(eid)
                    candidate_actions.extend(
                        _last_action_cmd(store, eid))
                rationale.append({
                    "rule": "known_fix",
                    "knowledge_id": chosen["knowledge_id"],
                    "relevance": "symptom-exact" if exact else "broad"})
        if not candidate_actions and strategy_id == S2:
            candidate_actions = base._observe_actions()

    key = json.dumps({
        "task": problem, "strategy": strategy_id, "mech": mech,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "banned": sorted(banned),
        "snapshot": [(s["knowledge_id"], s["version"]) for s in snapshot],
    }, ensure_ascii=False, sort_keys=True)
    sug_id = "sug4_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
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
        "mech": mech,
        "hypothesis": hypothesis,
        "exploration": exploration,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if save:
        store.append_suggestion(sug)
    return sug
