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
import json
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
#
# --- v0.6.x (applicability-lineage integration, L1–L6; FROZEN 07.09):
# L1: _prior_lineage = полная релевантная история линии (включая
#   failure-знания), НЕ «последняя запись»;
# L2: pivot для applicable_when = последний field-bearing
#   verified-success член линии (не prior[-1]);
# L3: failure остаётся в lineage; его observations переносятся в obs
#   нового знания (никогда в aw); native recorder (a)/(b) для
#   не-success исходов: может добавлять evidence, НЕ может создавать
#   или изменять applicable_when;
# L4: source — закрытый enum {"verified success", "verified failure"};
# L6: lineage_generation = 1 + число предшествующих verified-success
#   членов линии (None для legacy-пути без E).
SOURCE_SUCCESS = "verified success"
SOURCE_FAILURE = "verified failure"
_OBS_SOURCES = (SOURCE_SUCCESS, SOURCE_FAILURE)  # закрытый enum (L4)


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


def _outcome_of(v):
    """Вердикт создания знания: из context записи ("outcome=...")."""
    m = re.search(r"outcome=(\w+)", v.get("context") or "")
    return m.group(1) if m else None


def _signature(o):
    """Сигнатура observation-записи БЕЗ episode_refs (для дедупликации
    слиянием: повторный (b) расширяет provenance, не дублируя запись)."""
    return json.dumps({k: v for k, v in sorted(o.items())
                       if k != "episode_refs"},
                      ensure_ascii=False, sort_keys=True)


def _lineage_generation(store, exp):
    """L6: поколение линии для нового знания = 1 + число
    предшествующих verified-success членов линии (sym, E, cmd).
    None для legacy-пути (без E) — legacy/unknown, не сочиняется."""
    e_val = _ctx_of_exp(store, exp)
    if e_val is None:
        return None
    sym = _lineage_sym(exp)
    cmd = _cmd_of(store, exp)
    if cmd is None:
        return None
    rows = _prior_lineage(store, sym, e_val, cmd)
    n_success = sum(1 for r in rows if (_outcome_of(r) or "") == "success")
    return n_success + 1


def _failure_observations(store, exp, outcome):
    """L3 native recorder (v0.6.x): failure-наблюдения для не-success
    исхода. (a) V-change — envver эпизода вне значений V, виденных
    success-ами линии; (b) outcome_disagreement — вектор полностью
    совпал с aw последнего field-bearing знания. Только evidence в
    observations; applicable_when recorder НЕ создаёт и НЕ меняет.
    Молчит (None), если нет success-базы (failure до первого
    verified-success — честно пуст, LP-1/2)."""
    e_val = _ctx_of_exp(store, exp)
    if e_val is None:
        return None
    v_now = _envver_of(exp)
    if v_now is None:
        return None
    sym = _lineage_sym(exp)
    cmd = _cmd_of(store, exp)
    if cmd is None:
        return None
    refs = [eid for eid in (exp.get("experience_id"),) if eid]
    rows = _prior_lineage(store, sym, e_val, cmd)
    succ = [r for r in rows if (_outcome_of(r) or "") == "success"]
    seen = set()
    for r in succ:
        aw = r.get("applicable_when") or {}
        if "V" in aw:
            seen.add(str(aw["V"]))
        for o in (r.get("applicability_observations") or []):
            if o.get("signal") == "V":
                seen.update(str(x) for x in (o.get("values_seen") or []))
    if seen and v_now not in seen:
        # (a) V-change (D1-негатив): attributable signal
        return [{"signal": "V",
                 "values_seen": sorted(seen | {v_now}),
                 "relation": "disagreement",
                 "source": SOURCE_FAILURE,
                 "episode_refs": refs}]
    fb = [r for r in succ if r.get("applicable_when") is not None]
    if fb:
        aw = fb[-1].get("applicable_when") or {}
        vec = {"E": e_val}
        if v_now is not None:
            vec["V"] = v_now
        if aw and all(vec.get(k) == v for k, v in aw.items()):
            # (b) outcome_disagreement (D2): вектор совпал с условием,
            # исход не успешен — сигнала-расхождения нет
            return [{"relation": "outcome_disagreement",
                     "condition": dict(aw),
                     "verdict": outcome or "",
                     "source": SOURCE_FAILURE,
                     "episode_refs": refs}]
    return None


def _prior_lineage(store, sym, e_val, cmd):
    """L1 (v0.6.x): полная релевантная история acquisition линии
    (sym, E, cmd) — свежайшая версия каждого знания линии, статус
    active/conflicted, по created_at, ВКЛЮЧАЯ failure-знания. НЕ
    «последняя запись»: перечисление служит acquisition (L2-pivot) и
    recorder'у (L3)."""
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
    """A2-механика (ACQ-1) + L2/L3 (v0.6.x).

    L2: pivot = последний field-bearing verified-success член линии;
    если field-bearing членов нет (пустой prior ИЛИ prior только из
    failure-знаний) — честный срез первого verified-success (Q1/K1-
    норма; LP-1: reopen ≡ honest при отсутствии fb-структуры).
    L3: failure-derived observations членов линии (не только pivot)
    переносятся в observations нового знания КАК ЕСТЬ (с source),
    если их signal не вошёл в condition; НИКОГДА в applicable_when;
    дедупликация слиянием episode_refs по сигнатуре.

    Возвращает (applicable_when, applicability_observations) или
    (None, None) — молчание acquisition (legacy-путь без E)."""
    e_val = _ctx_of_exp(store, exp)
    if e_val is None:
        return None, None            # legacy: без E поле не пишется
    sym = _lineage_sym(exp)
    facts = {"E": e_val}
    v_val = _envver_of(exp)
    if v_val is not None:
        facts["V"] = v_val
    prior = _prior_lineage(store, sym, e_val, cmd)
    fb = [r for r in prior if r.get("applicable_when") is not None]
    refs = [eid for eid in (exp.get("experience_id"),) if eid]
    if not fb:
        # L2: нет field-bearing структуры — честный срез (Q1/K1-норма)
        return (dict(facts) if facts else None), None
    last = fb[-1]
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
                            "source": SOURCE_SUCCESS,
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
    # L3: failure-derived observations членов линии (все failure-знания
    # в prior, не только pivot); никогда в aw; dedup слиянием refs
    existing = [_signature(o) for o in obs]
    for r in prior:
        if (_outcome_of(r) or "") == "success":
            continue
        for o in (r.get("applicability_observations") or []):
            if o.get("signal") is not None and o["signal"] in cond:
                continue
            s = _signature(o)
            if s in existing:
                for eo in obs:
                    if _signature(eo) == s:
                        eo["episode_refs"] = sorted(
                            set(eo.get("episode_refs", []))
                            | set(o.get("episode_refs", [])))
                continue
            obs.append(dict(o))
            existing.append(s)
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
    gen = None
    if outcome == "success":
        # acquisition (ACQ-1 A2) по L2/L3 — только verified-success;
        # failure/noise линию-условие не меняют (D2-семантика)
        aw, aobs = _acquire(store, exp, cmd)
        gen = _lineage_generation(store, exp)
    else:
        # v0.6.x (L3): native recorder (a)/(b) — только evidence в
        # observations; applicable_when не создаётся и не меняется
        fobs = _failure_observations(store, exp, outcome)
        if fobs:
            aobs = fobs
        gen = _lineage_generation(store, exp)
    k = knowledge.create(store, content=content, source=SRC,
                         observer=by or SRC,
                         experience_refs=[experience_id], context=context,
                         transformations=["update/rule:v1"],
                         applicable_when=aw,
                         applicability_observations=aobs,
                         lineage_generation=gen)
    return k
