# -*- coding: utf-8 -*-
"""strategy_v3 — экспериментальная ветка ЗОНЫ 3 (TRUST-1).

Дизайн: experiments/TRUST1_DESIGN.md (frozen). Основная Strategy
v0.2 (strategy.py, R1) НЕ меняется: v3 повторяет её путь выбора и
модифицирует его механиками T2/T3 (флаги mech). T1 (auto-conflict)
— процедура auto_conflict(), вызываемая контуром ПОСЛЕ создания
проверенного знания (не внутри Knowledge API).

Механики:
- T1 auto-conflict: новый проверенный исход (симптом, команда),
  противоречащий последнему проверенному исходу той же
  (симптом, команда) → declare_conflict (история фиксирует
  противоречие; версии целы);
- T2 no-failure-action: знания «НЕ перевело» (outcome=failure) не
  участвуют в recency-гонке S2 как кандидаты действия;
- T3 evidence-rule: выбор действия по объёму проверенных
  свидетельств на (симптом, действие): действенно, если s>0 и
  (f==0 или s>f); приоритет большему числу свидетельств;
  если действенных нет — S3 (недостаточно основания);
  conflicted-пары НЕ блокируют сами по себе: они учитываются через
  s/f-счёт (конфликт = есть и s, и f — в истории).

Никаких trust-чисел: счётчики s/f — факты (проверенные эпизоды),
не «доверие». confidence остаётся None.
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
EVIDENCE_RE = re.compile(r"evidence_count=(\d+)")


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
        for aid in exp.get("actions", []):
            a = store.read_action(aid)
            if a and a.get("command"):
                return a["command"]
    return None


def _evidence(rec):
    """Число проверенных свидетельств знания (refs; агрегат — N)."""
    m = EVIDENCE_RE.search(rec.get("context", "") or "")
    if m:
        return int(m.group(1))
    return len(rec.get("experience_refs", []) or [])


def auto_conflict(store, new_kid, by="auto-conflict:v1"):
    """T1: зафиксировать противоречие нового проверенного исхода с
    последним проверенным исходом той же (симптом, команда)."""
    rec = store.read_knowledge(new_kid)
    if rec is None:
        return None
    out = _outcome_of(rec)
    if out not in ("success", "failure"):
        return None
    cmd = _cmd_of(store, rec)
    sym = _rec_symptom(store, rec)
    if cmd is None or not sym:
        return None
    opp = {"success": "failure", "failure": "success"}[out]
    last = None
    for v in store.read_knowledge_versions_all():
        if v["knowledge_id"] == new_kid:
            continue
        if v["status"] not in ("active", "conflicted"):
            continue
        if _outcome_of(v) != opp:
            continue
        if _cmd_of(store, v) != cmd:
            continue
        if _rec_symptom(store, v) != sym:
            continue
        if last is None or v["created_at"] > last["created_at"]:
            last = v
    if last is None:
        return None
    a1 = store.read_knowledge(new_kid)
    if last["knowledge_id"] in a1.get("conflicts_with", []):
        return None
    try:
        knowledge.declare_conflict(store, new_kid, last["knowledge_id"],
                                   by=by, note="auto-conflict (T1)")
        return (new_kid, last["knowledge_id"])
    except ValueError:
        return None


def suggest_v3(store, task, mech="", by="strategy_v3/deterministic",
               save=True):
    """mech: "" (контроль = v0.2), "T1", "T1+T2", "T1+T2+T3".
    T1 здесь не меняет выбор (это процедура auto_conflict в
    контуре); выбор меняют T2 (failure-исключение) и T3
    (evidence-правило действия)."""
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

    use_t2 = "T2" in mech
    use_t3 = "T3" in mech

    if pool and not (conflicted_pairs and not use_t3):
        if use_t3:
            counts = {}
            for r in pool:
                cmd = _cmd_of(store, r)
                if cmd is None:
                    continue
                out = _outcome_of(r)
                if out not in ("success", "failure"):
                    continue  # неизвестный исход — не свидетельство
                d = counts.setdefault(cmd, {"s": 0, "f": 0})
                d[out[0]] += _evidence(r)
            actionable = [c for c, d in counts.items()
                          if d["s"] > 0 and (d["f"] == 0 or d["s"] > d["f"])]
            if not actionable:
                strategy_id = S3
                candidate_actions = base._observe_actions()
                knowledge_refs = sorted({r["knowledge_id"] for r in pool})
                rationale.append({
                    "rule": "insufficient_evidence",
                    "note": "нет действия с перевесом проверенных "
                            "свидетельств (s>0 и (f=0 или s>f))",
                    "counts": counts})
            else:
                best_cmd = None
                best_key = None
                for cmd in actionable:
                    d = counts[cmd]
                    latest = ""
                    for r in pool:
                        if _cmd_of(store, r) == cmd \
                                and _outcome_of(r) == "success" \
                                and r["created_at"] > latest:
                            latest = r["created_at"]
                    key = (d["s"], -d["f"], latest)
                    if best_key is None or key > best_key:
                        best_key = key
                        best_cmd = cmd
                strategy_id = S2
                chosen_recs = [r for r in pool
                               if _cmd_of(store, r) == best_cmd
                               and _outcome_of(r) == "success"]
                chosen_recs.sort(key=lambda r: r["created_at"])
                chosen = chosen_recs[-1]
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
                    "rule": "known_fix_evidence",
                    "knowledge_id": chosen["knowledge_id"],
                    "cmd": best_cmd,
                    "counts": counts[best_cmd],
                    "relevance": "symptom-exact" if exact else "broad"})
        else:
            cands = list(pool)
            if use_t2:
                cands = [r for r in cands if _outcome_of(r) != "failure"]
            if not cands:
                strategy_id = S3
                candidate_actions = base._observe_actions()
                knowledge_refs = sorted({r["knowledge_id"] for r in pool})
                rationale.append({
                    "rule": "only_failure_knowledge",
                    "note": "все релевантные знания — о неудачах; "
                            "нет основания для действия (T2)"})
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
                    acts = base._actions_from_experience(store, eid)
                    if acts:
                        candidate_actions.extend(acts)
                rationale.append({
                    "rule": "known_fix",
                    "knowledge_id": chosen["knowledge_id"],
                    "note": "повтор действий опыта знания",
                    "relevance": "symptom-exact" if exact else "broad"})
        if not candidate_actions:
            candidate_actions = base._observe_actions()
    elif conflicted_pairs:
        strategy_id = S3
        candidate_actions = base._observe_actions()
        knowledge_refs = sorted({p for pair in conflicted_pairs
                                 for p in pair})
        for a, b in conflicted_pairs:
            rationale.append({"rule": "conflict",
                              "knowledge_refs": [a, b],
                              "note": "знания противоречат друг другу"})
        for kid in knowledge_refs:
            rec = store.read_knowledge(kid)
            if rec:
                experience_refs += rec.get("experience_refs", [])
    else:
        strategy_id = S1
        candidate_actions = base._observe_actions()
        rationale.append({"rule": "no_relevant_knowledge",
                          "note": "нет знания по этому классу задачи"})

    key = json.dumps({
        "task": problem, "strategy": strategy_id, "mech": mech,
        "knowledge_refs": sorted(set(knowledge_refs)),
        "snapshot": [(s["knowledge_id"], s["version"]) for s in snapshot],
    }, ensure_ascii=False, sort_keys=True)
    sug_id = "sug3_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
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
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if save:
        store.append_suggestion(sug)
    return sug
