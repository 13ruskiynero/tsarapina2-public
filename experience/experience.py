# -*- coding: utf-8 -*-
"""Experience (Tsarapina, этап 2).

ЗАПРЕТ: Experience НЕ объясняет событие — он его СОБИРАЕТ.
«Сервер был перегружен, поэтому...» — интерпретация, ей здесь не
место. Experience = журнал: problem-триггер (пересказ факта, не
объяснение), observations[] (факты с provenance), actions[] (ссылки),
result_ref (фактический результат — ссылка), outcome (оценка;
заполняется Evaluation'ом позже, при сборке = unknown).

Детерминизм: experience_id = sha1(problem + отсортированные refs
наблюдений/действий + started_at + machine) → повторная сборка того
же набора даёт тот же эпизод; append_experience не перезаписывает.
"""
import hashlib
import json
import time

SCHEMA_VERSION = "0.1"


def _refs_key(refs):
    return json.dumps(sorted(set(refs)), ensure_ascii=False)


def build(problem, observations, actions=None, result_ref=None,
          machine=None, started_at=None, ended_at=None, notes=None,
          outcome="unknown"):
    """Собрать эпизод из набора событий. Ничего не объясняет:
    problem — пересказ триггер-факта (subject property=value);
    observations — факты (каждый с provenance); actions — ссылки;
    result_ref — ссылка на result-запись; outcome — НЕ заполняется
    при сборке (unknown), оценка — позже, Evaluation'ом."""
    obs = list(observations)
    acts = list(actions or [])
    started_at = started_at or time.strftime("%Y-%m-%dT%H:%M:%S")
    orefs = [o["provenance"]["raw_ref"] for o in obs
             if o.get("provenance", {}).get("raw_ref")]
    key = "%s|%s|%s|%s|%s" % (problem, _refs_key(orefs),
                              _refs_key(acts), started_at or "", machine or "")
    exp_id = "exp_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    exp = {
        "schema_version": SCHEMA_VERSION,
        "experience_id": exp_id,
        "problem": problem,
        "started_at": started_at,
        "observations": obs,
        "actions": acts,
        "outcome": outcome,
    }
    # None-поля не включаются (schema: type string; null недопустим)
    if ended_at is not None:
        exp["ended_at"] = ended_at
    if machine is not None:
        exp["machine"] = machine
    if result_ref is not None:
        exp["result_ref"] = result_ref
    if notes is not None:
        exp["notes"] = notes
    return exp


def save(store, exp):
    """Сохранить эпизод (append-only, dedup). True — добавлен."""
    return store.append_experience(exp)
