# -*- coding: utf-8 -*-
"""Update (Tsarapina, этап 8) — последний инженерный слой.

Минимальная функция (профессор):
    Evaluation → Knowledge operation

Контур: Experience (с observations, actions, result_ref) →
Evaluation outcome → Update → Knowledge-запись.

Experience E17 → Action restart ssh → Result R31 → Evaluation
(success) → Update → Knowledge K42 «restart ssh восстановил ssh при
состоянии inactive».

Правила (FIXED):
- создаёт ТОЛЬКО Knowledge через knowledge.create (с experience_refs
  на полный опыт — с действиями и результатом);
- content формируется ДЕТЕРМИНИРОВАННО из фактов (команда, свойство,
  состояние до/после, вердикт) — НЕ из объяснений модели;
- вердикт failure → знание «НЕ восстановил» (конфликтующие версии
  будут сосуществовать; declare_conflict — RESEARCHABLE, не здесь);
- не меняет Experience/Result/Evaluation;
- не импортирует llm.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge import knowledge  # noqa: E402

SRC = "update/rule:v1"


def _cmd_of(store, exp):
    """Первая команда из действий опыта (для content)."""
    for aid in exp.get("actions", []):
        a = store.read_action(aid)
        if a and a.get("command"):
            return a["command"]
    return None


def _goal_of(store, exp):
    """goal из args первого действия (если есть)."""
    for aid in exp.get("actions", []):
        a = store.read_action(aid)
        if a and (a.get("args") or {}).get("goal"):
            return a["args"]["goal"]
    return None


def _state_delta(res, prop):
    sb = (res or {}).get("state_before", {})
    sa = (res or {}).get("state_after", {})
    if not prop:
        return None, None
    return sb.get(prop), sa.get(prop)


# --- v0.6 (integration gate): acquisition (ACQ-1 A2) ----------------
# applicable_when/applicability_observations пишутся ТОЛЬКО для
# verified-success и ТОЛЬКО при наличии ctx_extra (E) в args действия
# (без E — legacy-знание, поле не пишется; решения FREEZE 07.09).
# Линия знания = (symptom, E, command) — как адрес v0.5 (_addr_cmd_of);
# V в идентичность линии НЕ входит (решение Q1). Пустое поле не
# пишется; failure/noise линию не меняют (D2-семантика).


def _lineage_sym(exp):
    m = re.search(r"symptom=([a-z0-9_ ]+)",
                  (exp.get("problem") or "").lower())
    if not m:
        return frozenset()
    return frozenset(re.findall(r"[a-z0-9]+", m.group(1)))


def _ctx_of_exp(store, exp):
    """E: ctx_extra из args ПОСЛЕДНЕГО действия опыта (как v0.5)."""
    actions = exp.get("actions", [])
    if not actions:
        return None
    a = store.read_action(actions[-1])
    if a and "ctx_extra" in (a.get("args") or {}):
        return a["args"]["ctx_extra"]
    return None


def _envver_of(exp):
    """V: envver-факт наблюдений опыта (subject=tsasvc,
    property=environment_version); None — источник не наблюдался."""
    for o in exp.get("observations", []):
        if (o.get("subject"), o.get("property")) == (
                "tsasvc", "environment_version"):
            return str(o.get("value"))
    return None


def _prior_lineage(store, sym, e_val, cmd):
    """Свежайшая версия каждого знания линии (sym, E, cmd),
    статус active/conflicted, по created_at."""
    latest = {}
    for v in store.read_knowledge_versions_all():
        latest[v["knowledge_id"]] = v
    rows = []
    for v in latest.values():
        if v.get("status") not in ("active", "conflicted"):
            continue
        for eid in v.get("experience_refs", []):
            exp = store.read_experience(eid)
            if exp is None:
                continue
            if (_lineage_sym(exp) == sym
                    and _cmd_of(store, exp) == cmd
                    and _ctx_of_exp(store, exp) == e_val):
                rows.append(v)
                break
    rows.sort(key=lambda r: r.get("created_at", ""))
    return rows


def _acquire(store, exp, cmd):
    """A2-механика (ACQ-1): инвариант по линии verified-success.

    Возвращает (applicable_when, applicability_observations) или
    (None, None) — молчание acquisition."""
    e_val = _ctx_of_exp(store, exp)
    if e_val is None:
        return None, None            # legacy: без E поле не пишется
    sym = _lineage_sym(exp)
    facts = {"E": e_val}
    v_val = _envver_of(exp)
    if v_val is not None:
        facts["V"] = v_val
    prior = _prior_lineage(store, sym, e_val, cmd)
    refs = [eid for eid in (exp.get("experience_id"),) if eid]
    if not prior:
        # честный срез первого verified-success (Q1)
        return (dict(facts) if facts else None), None
    last = prior[-1]
    pcond = last.get("applicable_when") or {}
    pobs = list(last.get("applicability_observations") or [])
    cond = {}
    obs = []
    diverged = set()
    for f, v in facts.items():
        if f in pcond:
            if pcond[f] == v:
                cond[f] = v
            else:
                diverged.add(f)
                obs.append({"signal": f,
                            "values_seen": sorted({pcond[f], v}),
                            "relation": "disagreement",
                            "episode_refs": list(refs)})
        else:
            prev = [o for o in pobs if o.get("signal") == f]
            if prev:
                merged = dict(prev[0])
                merged["episode_refs"] = sorted(
                    set(prev[0].get("episode_refs", [])) | set(refs))
                seen = set(merged.get("values_seen", [])) | {v}
                merged["values_seen"] = sorted(seen)
                obs.append(merged)
                diverged.add(f)
            else:
                cond[f] = v
    # перенос остальных prior-наблюдений (полная история линии)
    for o in pobs:
        if o.get("signal") not in diverged:
            obs.append(o)
    aw = cond if cond else None
    aobs = obs if obs else None
    return aw, aobs


def apply(store, experience_id, outcome, by=None):
    """Создать Knowledge-запись по вердикту Evaluation для опыта.

    Возвращает knowledge-запись (последнюю версию) или None, если
    опыт не содержит действий/результата (обновлять нечего).
    """
    exp = store.read_experience(experience_id)
    if exp is None:
        raise ValueError("experience не найден: %s" % experience_id)
    if not exp.get("actions"):
        return None
    cmd = _cmd_of(store, exp)
    if cmd is None:
        return None
    res = store.read_result(exp.get("result_ref")) if exp.get("result_ref") \
        else None
    goal = _goal_of(store, exp)
    if res is not None and goal:
        prop = goal.get("property")
        before, after = _state_delta(res, prop)
        if outcome == "success":
            content = ("действие %r перевело %s из %r в %r (цель "
                       "достигнута)" % (cmd, prop, before, after))
        else:
            content = ("действие %r НЕ перевело %s в %r: было %r, "
                       "стало %r (цель не достигнута, вердикт %s)"
                       % (cmd, prop, goal.get("value"), before, after,
                          outcome))
    else:
        if outcome == "success":
            content = "действие %r выполнено успешно" % cmd
        else:
            content = ("действие %r: вердикт %s" % (cmd, outcome))
    context = "experience=%s outcome=%s" % (experience_id, outcome)
    aw = aobs = None
    if outcome == "success":
        # v0.6: acquisition (ACQ-1 A2) — только verified-success;
        # failure/noise линию не меняют (D2-семантика)
        aw, aobs = _acquire(store, exp, cmd)
    k = knowledge.create(store, content=content, source=SRC,
                         observer=by or SRC,
                         experience_refs=[experience_id], context=context,
                         transformations=["update/rule:v1"],
                         applicable_when=aw,
                         applicability_observations=aobs)
    return k
