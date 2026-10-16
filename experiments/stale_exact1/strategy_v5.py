# -*- coding: utf-8 -*-
"""strategy_v5 — experimental branch STALE-EXACT-1 (06.09.2026).

Дизайн: STALE_EXACT1_DESIGN.md (FROZEN). Основная Strategy v0.3 НЕ
меняется. Факторизация механик (только experimental):

- F0: v0.3 как есть (делегирует strategy.suggest; контурный declare
  выключен) — контроль;
- F1: F0 + контур объявляет конфликт после failure-эпизода на
  exact-классе (auto_declare_stale: последний success-exact той же
  (симптом, команда) ↔ новое failure-знание). Выбор = v0.3
  (conflicted → S3);
- F2: F1 + conflicted exact-знания исключаются из S2-выбора:
  recency-пул = неконфликтованные exact; если после исключения
  пуст → S3 (причина conflict);
- F3: F2 + когда конфликт остановил эксплуатацию exact-класса (не
  осталось пригодного exact) → exploration=True (систематический
  перебор контура). Переход обусловлен структурой (конфликт в
  истории), не счётчиком failure.

Запреты: без if-failure-explore; без trust; без N-failures; без
causal model; Knowledge/Update/Evaluation/Executor не меняются.
"""
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from knowledge import knowledge  # noqa: E402
from strategy import strategy as base  # noqa: E402

S1, S2, S3, S5 = base.S1, base.S2, base.S3, base.S5
OUTCOME_RE = re.compile(r"outcome=(\w+)")

MECHS = ("F0", "F1", "F2", "F3")


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


def _outcome_of(rec):
    m = OUTCOME_RE.search(rec.get("context", "") or "")
    return m.group(1) if m else ""


def _cmd_of(store, rec):
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        if exp.get("actions"):
            a = store.read_action(exp["actions"][-1])
            if a and a.get("command"):
                return a["command"]
    return None


def auto_declare_stale(store, new_failure_kid, by="stale-exact-1/v1"):
    """F1: зафиксировать противоречие НЕ-УСПЕШНОГО последствия на
    exact-классе: объявить конфликт нового не-success знания
    (failure ИЛИ partial — в полигоне устаревание даёт partial:
    действие частично меняет мир, но не достигает цели) с
    ПОСЛЕДНИМ success-знанием той же (симптом, команда).
    Возвращает пару (kid_new, kid_success) или None."""
    rec = store.read_knowledge(new_failure_kid)
    if rec is None or _outcome_of(rec) not in ("failure", "partial"):
        return None
    cmd = _cmd_of(store, rec)
    sym = _rec_symptom(store, rec)
    if cmd is None or not sym:
        return None
    last_s = None
    for v in store.read_knowledge_versions_all():
        if v["knowledge_id"] == new_failure_kid:
            continue
        if v["status"] not in ("active", "conflicted"):
            continue
        if _outcome_of(v) != "success":
            continue
        if _cmd_of(store, v) != cmd:
            continue
        if _rec_symptom(store, v) != sym:
            continue
        if last_s is None or v["created_at"] > last_s["created_at"]:
            last_s = v
    if last_s is None:
        return None
    a1 = store.read_knowledge(new_failure_kid)
    if last_s["knowledge_id"] in a1.get("conflicts_with", []):
        return None
    try:
        knowledge.declare_conflict(store, new_failure_kid,
                                   last_s["knowledge_id"],
                                   by=by, note="stale-exact auto-declare")
        return (new_failure_kid, last_s["knowledge_id"])
    except ValueError:
        return None


def suggest_v5(store, task, mech="F0", banned_commands=None,
               by="strategy_v5/deterministic", save=True):
    """Стратегия по механике F0..F3 (STALE-EXACT-1)."""
    if mech not in MECHS:
        raise ValueError("mech must be in %s" % (MECHS,))
    if mech in ("F0", "F1"):
        sug = base.suggest(store, task, by=by, save=save,
                           banned_commands=banned_commands)
        sug["mech"] = mech
        return sug

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
    exact = []
    if task_sym:
        exact = [r for r in rel if _rec_symptom(store, r) == task_sym]

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
    conflict_stop = False

    def _ctx_of(rec):
        m = re.search(r"outcome=(\w+)", rec.get("context", "") or "")
        return m.group(1) if m else ""

    # F2/F3: конфликтованные exact исключаются из S2-выбора
    conflicted_kids = {p for pair in conflicted_pairs for p in pair}
    exact_usable = [r for r in exact if r["knowledge_id"]
                    not in conflicted_kids]

    if task_sym and exact and not exact_usable:
        # весь exact-пул сконфликтован: эксплуатация остановлена
        strategy_id = S3
        conflict_stop = True
        candidate_actions = base._observe_actions()
        knowledge_refs = sorted({r["knowledge_id"] for r in exact})
        for a, b in conflicted_pairs:
            if a in [r["knowledge_id"] for r in exact] or \
                    b in [r["knowledge_id"] for r in exact]:
                rationale.append({"rule": "conflict",
                                  "knowledge_refs": [a, b],
                                  "note": "exact-знания класса "
                                          "сконфликтованы (stale?): "
                                          "эксплуатация остановлена"})
        if mech == "F3":
            exploration = True
            rationale.append({
                "rule": "conflict_exploration",
                "note": "conflict остановил эксплуатацию: уступить "
                        "систематическому поиску (право искать)"})
    elif conflicted_pairs and not (task_sym and exact):
        # конфликт вне exact (broad): v0.3-поведение S3
        strategy_id = S3
        candidate_actions = base._observe_actions()
        knowledge_refs = sorted({p for pair in conflicted_pairs
                                 for p in pair})
        for a, b in conflicted_pairs:
            rationale.append({"rule": "conflict",
                              "knowledge_refs": [a, b]})
    elif task_sym and not exact:
        # v0.3 routing: exact нет → гипотеза/exploration (как SEB)
        hyp = None
        if not banned:
            broad_cands = [r for r in rel if _ctx_of(r) != "failure"]
            broad_cands.sort(key=lambda r: (r["version"], r["created_at"]))
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
                        "note": "exact-знание отсутствует: одна проверка "
                                "broad-гипотезы"})
        if hyp is None and strategy_id is None:
            strategy_id = S1
            exploration = True
            candidate_actions = base._observe_actions()
            knowledge_refs = sorted({r["knowledge_id"] for r in rel})
            rationale.append({"rule": "insufficiency_exploration"})
    else:
        # exact есть и usable: S2-эксплуатация (recency usable-пул)
        pool = exact_usable if (task_sym and exact) else rel
        pool.sort(key=lambda r: (r["version"], r["created_at"]))
        chosen = pool[-1]
        strategy_id = S2
        knowledge_refs = [chosen["knowledge_id"]]
        for eid in chosen.get("experience_refs", []):
            exp = store.read_experience(eid)
            if exp is None:
                continue
            experience_refs.append(eid)
            candidate_actions.extend(base._last_candidate_action(store, eid))
            rationale.append({
                "rule": "known_fix",
                "knowledge_id": chosen["knowledge_id"],
                "note": "действие знания, чьё последствие зафиксировано",
                "relevance": "symptom-exact" if (task_sym and exact)
                else "broad"})
        if not candidate_actions:
            candidate_actions = base._observe_actions()

    key = json.dumps({
        "task": problem, "strategy": strategy_id, "mech": mech,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "banned": sorted(banned),
        "snapshot": [(s["knowledge_id"], s["version"]) for s in snapshot],
    }, ensure_ascii=False, sort_keys=True)
    sug_id = "sug5_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
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
        "conflict_stop": conflict_stop,
        "mech": mech,
        "strategy_version": "0.3+SEB",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if save:
        store.append_suggestion(sug)
    return sug
