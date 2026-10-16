# -*- coding: utf-8 -*-
"""strategy_v7 — experimental branch TRANSITION-EVENT-1 (06.09.2026).

Дизайн: TRANSITION_EVENT1_DESIGN.md (FROZEN). База: основная
Strategy v0.4 — НЕ изменяется. v7 = v0.4 + переход по СОБЫТИЮ E2:

E2(addr, cmd): 2-й ПОСЛЕДОВАТЕЛЬНЫЙ non-success эпизода с тем же
(адрес: symptom+ctx; та же команда exact-знания). Событие
СТРУКТУРНОЕ (адресно-командная история), не глобальный счётчик:
не-success других команд/адресов счёт не пополняет; success по
(addr, cmd) сбрасывает последовательность.

non-success = outcome в (failure, partial). История берётся из
Knowledge: знания update/rule (1 знание на эпизод) того же
(addr, cmd), отсортированные по created_at desc: если два
последних — non-success → событие.

При событии: suggestion получает exploration=True (контур исполняет
SEB-перебор); вне события выбор = v0.4 полностью.
"""
import hashlib
import json
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from strategy import strategy as base  # noqa: E402

S1, S2, S3, S5 = base.S1, base.S2, base.S3, base.S5
OUTCOME_RE = re.compile(r"outcome=(\w+)")


def _symptom_of(text):
    m = re.search(r"symptom=([a-z0-9_ ]+)", (text or "").lower())
    if not m:
        return frozenset()
    return frozenset(re.findall(r"[a-z0-9]+", m.group(1)))


def _outcome_of(rec):
    m = OUTCOME_RE.search(rec.get("context", "") or "")
    return m.group(1) if m else ""


def _non_success(out):
    return out in ("failure", "partial")


def _addr_cmd_of(store, rec):
    """(symptom-set, ctx, command) знания — из опыта/действий."""
    for eid in rec.get("experience_refs", []):
        exp = store.read_experience(eid)
        if exp is None:
            continue
        sym = _symptom_of(exp.get("problem", ""))
        actions = exp.get("actions", [])
        if not actions:
            return None
        a = store.read_action(actions[-1])
        if a is None:
            return None
        ctx = (a.get("args") or {}).get("ctx_extra")
        return (frozenset(sym), ctx, a.get("command"))
    return None


def _history(store, addr, cmd, exclude_kid=None):
    """Знания (addr, cmd) по времени; [последняя..первая]."""
    rows = []
    for v in store.read_knowledge_versions_all():
        if exclude_kid and v["knowledge_id"] == exclude_kid:
            continue
        key = _addr_cmd_of(store, v)
        if key is None:
            continue
        sym, ctx, c = key
        if sym == addr[0] and ctx == addr[1] and c == cmd:
            rows.append(v)
    rows.sort(key=lambda v: v.get("created_at", ""), reverse=True)
    return rows


def e2_event(store, addr, cmd):
    """Событие E2: два последних знания (addr, cmd) — non-success."""
    hist = _history(store, addr, cmd)
    if len(hist) < 2:
        return False
    return _non_success(_outcome_of(hist[0])) and \
        _non_success(_outcome_of(hist[1]))


def suggest_v7(store, task, ctx_now=None, banned_commands=None,
               by="strategy_v7/deterministic", save=True):
    """v0.4 + переход по событию E2 (только experimental)."""
    problem = task.get("problem", "")
    task_sym = _symptom_of(problem)
    addr = (task_sym, ctx_now)
    sug = base.suggest(store, task, by=by, save=save,
                       banned_commands=banned_commands,
                       ctx_now=ctx_now)
    event = False
    # событие проверяется только на S2-эксплуатации exact-знания
    if sug["strategy_id"] == S2 and sug.get("candidate_actions"):
        cand = sug["candidate_actions"][0].get("command")
        kid = sug["knowledge_refs"][0] if sug["knowledge_refs"] else None
        rec = store.read_knowledge(kid) if kid else None
        key = _addr_cmd_of(store, rec) if rec else None
        if key is not None:
            event = e2_event(store, (key[0], key[1]), key[2])
            if event:
                cand = key[2]
        elif cand:
            event = e2_event(store, addr, cand)
    if event:
        sug["exploration"] = True
        sug["event"] = "E2_TRANSITION"
        sug["strategy_version"] = "0.4+E2"
        sug["rationale"] = list(sug["rationale"]) + [{
            "rule": "e2_transition",
            "note": "второй последовательный non-success того же "
                    "(адрес, команда): переход exact → исследование"}]
    return sug
