# -*- coding: utf-8 -*-
"""Aggregation (Tsarapina, зона 2; AGGREGATION1_DESIGN.md).

Evidence aggregation (уровень B дизайна): поток повторяющихся
проверенных эпизодов → компактное АКТИВНОЕ представление.

Правила (FIXED, из дизайна):
- свидетельства (Experience/Fact/Raw) НЕ изменяются и НЕ удаляются;
- исходные Knowledge superseded (retract): история и provenance
  сохранены; активным остаётся агрегат;
- сигнатура группы: (симптом, первая команда действия, исход) —
  читается детерминированно из знания (context), его опыта и
  action-записи; update/rule:v1-знания;
- конфликт НЕ схлопывается (H-A2): пары агрегированных групп с
  конфликтными исходами получают declare_conflict; конфликтные
  отношения агрегируемых записей с неагрегируемыми переносятся на
  агрегат (S3-защита сохраняется);
- детерминизм (M5): knowledge_id агрегата = sha1(content+refs+
  source) — повторный прогон на том же наборе не создаёт дубликат;
- идемпотентность: второй прогон после первого ничего не делает
  (исходные уже неактивны);
- НЕ делает: storage dedup как результат; semantic aggregation;
  trust; забывание; НЕ меняет Update/R1/Knowledge API (использует
  append_knowledge/retract/declare_conflict);
- не импортирует llm.
"""
import hashlib
import os
import re
import sys
import uuid

from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge import knowledge  # noqa: E402

SRC = "aggregation/evidence:v1"
UPDATE_SRC = "update/rule:v1"
SCHEMA_VERSION = "0.1"
SYMPTOM_RE = re.compile(r"symptom=([a-z0-9_ ]+)", re.I)
OUTCOME_RE = re.compile(r"outcome=(\w+)")


def _latest_all(store):
    """kid -> последняя версия."""
    out = {}
    for v in store.read_knowledge_versions_all():
        out[v["knowledge_id"]] = v
    return out


def _symptom_of_problem(problem):
    m = SYMPTOM_RE.search(problem or "")
    if not m:
        return ""
    return " ".join(sorted(set(re.findall(r"[a-z0-9]+", m.group(1)))))


def _exp_of(store, rec):
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is not None:
            return exp
    return None


def _cmd_of(store, exp):
    for aid in exp.get("actions", []):
        a = store.read_action(aid)
        if a and a.get("command"):
            return a["command"]
    return None


def _sig(store, rec):
    """(symptom, command, outcome) знания — детерминированно."""
    context = rec.get("context", "")
    m = OUTCOME_RE.search(context or "")
    outcome = m.group(1) if m else ""
    exp = _exp_of(store, rec)
    if exp is None:
        return None
    symptom = _symptom_of_problem(exp.get("problem", ""))
    cmd = _cmd_of(store, exp)
    if not symptom or not cmd or not outcome:
        return None
    return (symptom, cmd, outcome)


def _mk_agg_rec(kid, content, refs, outcome=""):
    now = datetime.now().isoformat(timespec="microseconds")
    ctx = "evidence_count=%d" % len(refs)
    if outcome:
        ctx += " outcome=%s" % outcome
    return {
        "schema_version": SCHEMA_VERSION,
        "knowledge_id": kid,
        "version": 1,
        "content": content,
        "source": SRC,
        "observer": "aggregation",
        "confidence": None,
        "status": "active",
        "conflicts_with": [],
        "experience_refs": list(refs),
        "created_at": now,
        "history": [{"at": now, "op": "add", "by": "aggregation",
                     "note": "evidence aggregation (AGGREGATION-1)"}],
        "context": ctx,
    }


def aggregate(store, by=SRC):
    """Выполнить evidence aggregation. Вернуть отчёт."""
    latest = _latest_all(store)
    candidates = [v for v in latest.values()
                  if v["status"] in ("active", "conflicted")
                  and v["source"] == UPDATE_SRC]
    groups = {}
    for rec in candidates:
        sig = _sig(store, rec)
        if sig is None:
            continue
        groups.setdefault(sig, []).append(rec)

    created = []
    superseded = []
    retract_errors = []
    group_agg = {}      # knowledge_id -> aggregate_kid
    agg_kid_by_sig = {}  # sig -> aggregate kid

    for sig, recs in sorted(groups.items()):
        if len(recs) < 2:
            continue
        symptom, cmd, outcome = sig
        refs = sorted({e for r in recs for e in r.get("experience_refs",
                                                       [])})
        content = ("aggregation: symptom=%s действие=%r -> %s "
                   "(свидетельств: %d)" % (symptom, cmd, outcome, len(refs)))
        kid = "K_agg_" + hashlib.sha1(
            (content + "|" + ",".join(refs) + "|" + by).encode()
            ).hexdigest()[:12]
        if store.read_knowledge(kid) is None:
            store.append_knowledge(_mk_agg_rec(kid, content, refs,
                                               outcome))
        created.append(kid)
        agg_kid_by_sig[sig] = kid
        for r in recs:
            rid = r["knowledge_id"]
            cur = _latest_all(store)[rid]
            if cur["status"] in ("active", "conflicted"):
                try:
                    knowledge.retract(store, rid, by=by,
                                      note="superseded by %s" % kid)
                except ValueError as exc:
                    retract_errors.append((rid, str(exc)[:120]))
            superseded.append(rid)
            group_agg[rid] = kid

    # перенос конфликтов (H-A2, S3-сохранение)
    transferred = []
    for rid, agg_kid in sorted(group_agg.items()):
        src = latest.get(rid, {})
        for y in src.get("conflicts_with", []):
            if y in group_agg:
                other_agg = group_agg[y]
                if other_agg == agg_kid:
                    continue
                try:
                    a1 = store.read_knowledge(agg_kid)
                    a2 = store.read_knowledge(other_agg)
                    if a1 is None or a2 is None:
                        continue
                    if other_agg not in a1.get("conflicts_with", []):
                        knowledge.declare_conflict(
                            store, agg_kid, other_agg, by=by,
                            note="conflict transferred (aggregation)")
                        transferred.append((agg_kid, other_agg))
                except ValueError:
                    pass
            else:
                yv = _latest_all(store).get(y)
                if yv is None or yv["status"] not in ("active",
                                                      "conflicted"):
                    continue
                a1 = store.read_knowledge(agg_kid)
                if a1 is None:
                    continue
                if y not in a1.get("conflicts_with", []):
                    try:
                        knowledge.declare_conflict(store, agg_kid, y,
                                                   by=by,
                                                   note="conflict "
                                                        "transferred")
                        transferred.append((agg_kid, y))
                    except ValueError:
                        pass

    latest_after = _latest_all(store)
    active_after = [v for v in latest_after.values()
                    if v["status"] in ("active", "conflicted")]
    refs_after = {e for v in active_after
                  for e in v.get("experience_refs", [])}
    return {
        "created": created,
        "superseded": superseded,
        "retract_errors": retract_errors,
        "conflicts_transferred": transferred,
        "groups_aggregated": len(created),
        "active_before": len(candidates),
        "active_after": len(active_after),
        "coverage_refs_after": len(refs_after),
        "evidence_after": sum(len(v.get("experience_refs", []))
                              for v in active_after),
    }
