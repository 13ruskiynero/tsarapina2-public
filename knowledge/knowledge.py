# -*- coding: utf-8 -*-
"""Knowledge (Tsarapina, этап 3).

Правила (FIXED):
- Knowledge живёт ВНЕ весов LLM;
- provenance обязателен: Knowledge → Experience → Fact → Raw;
- версии НЕ уничтожаются: CONFLICT сохраняет обе записи;
- RETRACT ≠ DELETE (запись остаётся, статус меняется, история
  сохраняется, provenance не исчезает);
- RESTORE ≠ новая реальность: новая версия поверх retracted,
  прошлое не переписывается;
- append-only: прямого update нет; каждая операция — НОВАЯ версия
  (knowledge_id стабилен, version нарастает);
- confidence НЕ вычисляется (RESEARCHABLE): хранится только если
  источник сообщил; иначе None (не «0.5»).

RESEARCHABLE (не решать на этапе 3): вычисление confidence/trust,
пороги подтверждения, агрегация Experience→Knowledge, обобщение,
перенос.
"""
import time
import uuid

SCHEMA_VERSION = "0.3"   # 0.2 (v0.6 integration gate): applicable_when
# и applicability_observations — приобретённая структура применимости
# (ACQ-1 A2). Семантика: applicable_when = устойчивое условие
# (наблюдаемые факты); applicability_observations = наблюдения
# расхождений (НЕ знание о значении сигнала — запись неопределённости).
# 0.3 (v0.6.x applicability-lineage integration, L1–L6): знание несёт
# lineage_generation (поколение линии; learn-путь с E; legacy — None);
# observation-записи новых знаний несут source из закрытого enum
# {"verified success", "verified failure"}; failure-знания могут нести
# recorder-наблюдения (a) V-change / (b) outcome_disagreement — только
# evidence, никогда applicable_when. Legacy-чтение (записи 0.2/0.1):
# source отсутствует → success-derived; lineage_generation отсутствует
# → legacy/unknown. Append-only: старые записи не переписываются.

VALID_OPS = ("add", "retract", "restore", "conflict", "update",
             "trust_change")
_RETRACTABLE = ("active", "conflicted", "restored")


def _now():
    # микросекунды: секундная гранулярность создавала tie в выборе
    # «самого свежего» знания (max по created_at) при быстрых
    # последовательных записях (артефакт, исправлен для LONGITUDINAL-1)
    from datetime import datetime
    return datetime.now().isoformat(timespec="microseconds")


def _hist(op, by, note=None):
    h = {"at": _now(), "op": op}
    if by is not None:
        h["by"] = by
    if note is not None:
        h["note"] = note
    return h


def _version_of(kid, v):
    return "%s#v%d" % (kid, v)


def _check_experience_refs(store, exp_refs):
    """Источник обязателен (K6): каждый experience_ref должен
    существовать в хранилище."""
    if not exp_refs:
        raise ValueError("Knowledge без источника (experience_refs) "
                         "запрещено")
    for eid in exp_refs:
        if store.read_experience(eid) is None:
            raise ValueError("experience_ref не существует: %s" % eid)


def create(store, content, source, observer, experience_refs,
           context=None, confidence=None, note=None,
           transformations=None, applicable_when=None,
           applicability_observations=None, lineage_generation=None):
    """ADD: создать знание (v1, status=active).

    applicable_when: dict {факт: значение} — устойчивое условие
    применимости (ACQ-1); applicability_observations: list расхождений
    [{signal, values_seen, relation, source, episode_refs}]. Оба поля
    optional; отсутствие поля = legacy-знание (v0.5-путь адресации).
    lineage_generation (v0.6.x, L6): поколение линии (1 + число
    предшествующих verified-success членов линии); None у вызовов вне
    learn-lineage (legacy/unknown). Append-only: запись не
    переписывается."""
    _check_experience_refs(store, experience_refs)
    kid = "K_%s" % uuid.uuid4().hex[:10]
    rec = {
        "schema_version": SCHEMA_VERSION,
        "knowledge_id": kid,
        "version": 1,
        "content": content,
        "source": source,
        "observer": observer,
        "confidence": confidence,   # None = неизвестно (не вычисляем)
        "status": "active",
        "conflicts_with": [],
        "experience_refs": list(experience_refs),
        "created_at": _now(),
        "history": [_hist("add", observer, note)],
    }
    if context is not None:
        rec["context"] = context
    if transformations:
        rec["transformations"] = list(transformations)
    if applicable_when is not None:
        rec["applicable_when"] = dict(applicable_when)
    if applicability_observations is not None:
        rec["applicability_observations"] = \
            list(applicability_observations)
    if lineage_generation is not None:
        rec["lineage_generation"] = lineage_generation
    store.append_knowledge(rec)
    return rec


def _latest(store, kid):
    rec = store.read_knowledge(kid)
    if rec is None:
        raise ValueError("Knowledge не найдено: %s" % kid)
    return rec


def _next(store, prev, status, op, by, note, conflicts_with=None):
    nxt = dict(prev)
    nxt["version"] = prev["version"] + 1
    nxt["status"] = status
    nxt["conflicts_with"] = list(
        conflicts_with if conflicts_with is not None
        else prev.get("conflicts_with", []))
    nxt["history"] = list(prev["history"]) + [_hist(op, by, note)]
    store.append_knowledge(nxt)
    return nxt


def retract(store, kid, by="operator", note=None):
    """RETRACT: новая версия со status=retracted. Запись остаётся;
    статус меняется; история сохраняется; provenance не исчезает."""
    prev = _latest(store, kid)
    if prev["status"] == "retracted":
        raise ValueError("Knowledge уже retracted: %s" % kid)
    if prev["status"] not in _RETRACTABLE:
        raise ValueError("Нельзя retract из статуса %s: %s"
                         % (prev["status"], kid))
    return _next(store, prev, "retracted", "retract", by, note)


def restore(store, kid, by="operator", note=None):
    """RESTORE: новая версия со status=active поверх retracted."""
    prev = _latest(store, kid)
    if prev["status"] != "retracted":
        raise ValueError("RESTORE возможен только из retracted: %s" % kid)
    return _next(store, prev, "active", "restore", by, note)


def declare_conflict(store, kid1, kid2, by="operator", note=None):
    """CONFLICT: обе записи получают новые версии со status=conflicted
    и взаимными ссылками. Ни одна не уничтожается."""
    p1 = _latest(store, kid1)
    p2 = _latest(store, kid2)
    if p1["knowledge_id"] == p2["knowledge_id"]:
        raise ValueError("Конфликт с самим собой")
    n1 = _next(store, p1, "conflicted", "conflict", by,
               note or "conflict with %s" % kid2,
               conflicts_with=p1.get("conflicts_with", []) + [kid2])
    n2 = _next(store, p2, "conflicted", "conflict", by,
               note or "conflict with %s" % kid1,
               conflicts_with=p2.get("conflicts_with", []) + [kid1])
    return n1, n2


def read(store, kid):
    """Актуальная (последняя) версия записи."""
    return _latest(store, kid)


def versions(store, kid):
    return store.read_knowledge_versions(kid)


def provenance_walk(store, kid):
    """Полная цепочка происхождения:
    Knowledge → Experience → Fact → Raw (для каждого experience_ref)."""
    rec = _latest(store, kid)
    chain = {"knowledge_id": rec["knowledge_id"],
             "content": rec["content"],
             "applicable_when": rec.get("applicable_when"),
             "applicability_observations": rec.get(
                 "applicability_observations"),
             "experiences": []}
    for eid in rec["experience_refs"]:
        exp = store.read_experience(eid)
        if exp is None:
            chain["experiences"].append({"experience_id": eid,
                                         "error": "missing"})
            continue
        facts = []
        for f in exp["observations"]:
            rid = f.get("provenance", {}).get("raw_ref")
            facts.append({
                "fact": {"subject": f.get("subject"),
                         "property": f.get("property"),
                         "value": f.get("value"),
                         "source": f.get("source")},
                "raw_ref": rid,
                "raw_text": store.read_raw(rid) if rid else None,
            })
        chain["experiences"].append({
            "experience_id": eid,
            "problem": exp.get("problem"),
            "outcome": exp.get("outcome"),
            "facts": facts,
        })
    return chain
