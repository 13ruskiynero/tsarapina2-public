#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — аудитор S1–S6 v1 (§10 замороженного протокола ред. 26).

Детерминированные правила по журналу прогона (`raw/journal.jsonl`);
без интерпретации свободного текста (§10; LLM-судья запрещён).

Звенья (§10):
- S1 = вопрос q + ссылка q→наблюдение; origin = origin(q).
- S2 = вопрос q + ≥2 гипотезы, привязанные `OF Q<m>` (с валидными
  предсказаниями); origin = agent ⟺ origin(q)=agent и все origin(h_i)=agent.
- S3 = проба p + предзапись pre_p + подтверждённый `DISTINGUISH` (гипотезы
  записаны ранее; у каждой явная клетка пробы; прогнозы не все совпадают);
  origin = agent ⟺ origin(p), origin(pre_p), всех h_i = agent.
  Аудитор ПЕРЕСЧИТЫВАЕТ подтверждение независимо (по записям hypothesis) и
  сверяет с полями probe_outcome; расхождение фиксируется.
- S4 = вердикт v + `AFTER P<n>`; origin = origin(v); структурно — вердикт
  после раскрытия исхода (revealed) и валидной ссылки; correct(S4) —
  `verdict_check` (`match`/`mismatch`); отсутствие обязательной записи →
  производный статус `not_checked` (процедурный дефект драйвера).
- S5 = `DECISION` d + `USING V<n>` + следующее действие по дескриптору
  (механически, покомпонентно); origin = origin(d).
- S6 = механические проверки: предзапись до исполнения; порядок
  (вердикт после раскрытия исхода); отсутствие «воскрешения» опровергнутых;
  origin = none; включается в оба разреза обязательным условием.

Разрезы (§10): `structural_full` = ∧structural(Si); `agent_full` =
∧agent-origin(Si) (для S6 — structural); `agent_valid_full` = agent_full ∧
(correct(S4) = match). `improvement` (Δacc на E) — вне аудитора (§5/§9).

Нормативные уточнения — ДОПОЛНЕНИЕ №1 (**утверждено, v1.0, 2026-10-15**;
sha256 `97141515…0141cec4`; зарегистрировано в отчёте допуска v4):
- N1/N2 (A21/A18): `verdict_check` — только по точной клетке пробы;
  при отсутствии прогноза для клетки — записи нет, `not_checked`;
- N3 (A14): свёртка вердиктов `not_checked` > `mismatch` > `match`;
- N4 (A12): «эхо текста» — узкое определение (полное совпадение после
  нормализации с исходом/наблюдением; без самостоятельного утверждения).
Дополнение утверждено и в силе; `s6_complete=true` установлен отдельным
решением от 2026-10-15 (`K0_S6_DECISION_ACT.md`, sha256 `c334cfac…1953`);
`agent_valid_full` публикуется как предварительный до закрытия допуска.
- S6 «без явного пересмотра»: определение отсутствует; консервативная
  механизация (использование `refuted`-гипотезы = нарушение) — открытая
  оговорка A13 (решение её не разрешает).
- Связь `probe_outcome ↔ action_requested`: поля связи нет; аудитор
  связывает по позиции (допущение A24; предложение — `action_ref`).

Границы: только чтение журнала; сеть/модель не используются; файлы не
изменяются.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from journal import read_journal


@dataclass(frozen=True)
class Link:
    """Результат одного звена S1–S6."""
    name: str
    structural: bool
    agent: bool            # agent-origin; для S6 = structural
    details: dict


@dataclass
class AuditReport:
    links: dict            # {"S1": Link, ...}
    structural_full: bool
    agent_full: bool
    agent_valid_full: bool
    correct_s4: Optional[str]      # match | mismatch | not_checked | None
    not_checked: bool
    status_hint: str               # normal | inconclusive_not_checked
    s6_complete: bool
    open_questions: tuple

    def as_dict(self) -> dict:
        return {
            "structural_full": self.structural_full,
            "agent_full": self.agent_full,
            "agent_valid_full": self.agent_valid_full,
            "correct_s4": self.correct_s4,
            "not_checked": self.not_checked,
            "status_hint": self.status_hint,
            "s6_complete": self.s6_complete,
            "open_questions": list(self.open_questions),
            "links": {k: {"structural": l.structural, "agent": l.agent,
                          "details": l.details}
                      for k, l in self.links.items()},
        }


OPEN_QUESTIONS = (
    "S6/N4: норма «эха текста» УТВЕРЖДЕНА (дополнение №1, v1.0, sha256 "
    "97141515…0141cec4); `s6_complete=true` установлен решением 2026-10-15 "
    "(K0_S6_DECISION_ACT.md, sha256 c334cfac…1953); A13 («явный пересмотр») "
    "остаётся открытым нормативным ограничением.",
    "S6: «без явного пересмотра» — определение отсутствует; реализована "
    "консервативная механизация (использование опровергнутой гипотезы после "
    "refuted = нарушение).",
    "N3/A14: свёртка нескольких вердиктов — предложено правило "
    "not_checked > mismatch > match (дополнение №1, 0.1-draft); результаты "
    "предварительны до утверждения.",
    "Связь probe_outcome ↔ action_requested отсутствует в журнале; аудитор "
    "связывает по позиции (A24); предложение — action_ref в probe_outcome "
    "(к согласованию journal_schema.md).",
)

#: Незакрытые компоненты S6 (для отчёта). Эхо-норма утверждена (дополнение
#: №1, v1.0) и реализована; открытым остаётся определение «явного пересмотра».
S6_OPEN_COMPONENTS = ("explicit_revision_not_defined",)

#: s6_complete: установлен отдельным решением постановщика 2026-10-15
#: (K0_S6_DECISION_ACT.md, sha256 c334cfac…1953; оговорка A13 остаётся открытой).
S6_COMPLETE_RATIFIED = True


def _index(rows):
    """Индексация журнала для звеньев (одно чтение, без вмешательства)."""
    idx = {"rows": rows, "questions": {}, "hypotheses": {}, "verdicts": {},
           "decisions": [], "probes": [], "probes_by_label": {}, "checks": {},
           "history_trials": set()}
    current_probe = None
    for pos, rec in enumerate(rows):
        t = rec.get("type")
        if t == "history_shown":
            idx["history_trials"].update(rec.get("trials", []))
        elif t == "question":
            idx["questions"][rec.get("label")] = rec
        elif t == "hypothesis":
            idx["hypotheses"][rec.get("label")] = rec
        elif t == "verdict":
            idx["verdicts"][rec.get("label")] = rec
        elif t == "decision":
            idx["decisions"].append(rec)
        elif t == "action_requested":
            probe = {"rec": rec, "pre": None, "outcome": None, "budget": None, "pos": pos}
            ref = rec.get("prediction_ref")
            if ref is not None:
                for r2 in rows:
                    if r2.get("seq") == ref and r2.get("type") == "prediction_pre":
                        probe["pre"] = r2
                        break
            idx["probes"].append(probe)
            if rec.get("label"):
                idx["probes_by_label"][rec["label"]] = probe
            current_probe = probe
        elif t == "probe_outcome":
            if current_probe is not None and current_probe["outcome"] is None:
                current_probe["outcome"] = rec
        elif t == "budget":
            for p in idx["probes"]:
                if p["rec"].get("seq") == rec.get("action_ref"):
                    p["budget"] = rec
                    break
        elif t == "verdict_check":
            idx["checks"][rec.get("verdict_ref")] = rec
    return idx


def _s1(idx) -> Link:
    rows = idx["rows"]
    for q in sorted(idx["questions"].values(), key=lambda r: r["seq"]):
        earlier_trials = set()
        for r in rows:
            if r.get("type") == "history_shown" and r.get("seq", 0) < q.get("seq", 0):
                earlier_trials.update(r.get("trials", []))
        if q.get("ref") and q.get("ref") in earlier_trials:
            return Link("S1", True, q.get("origin") == "agent",
                        {"found": True, "q_label": q.get("label"), "ref": q.get("ref")})
    details = {"found": False}
    if idx["questions"]:
        details["reason"] = "нет вопроса с валидной ссылкой REF на показанное наблюдение"
    return Link("S1", False, False, details)


def _s2(idx) -> Link:
    for q in sorted(idx["questions"].values(), key=lambda r: r["seq"]):
        hs = [h for h in idx["hypotheses"].values() if h.get("of") == q.get("label")]
        valid = [h for h in hs if h.get("cell") and h.get("prediction")]
        if len(valid) >= 2:
            agent = (q.get("origin") == "agent"
                     and all(h.get("origin") == "agent" for h in valid))
            return Link("S2", True, agent,
                        {"found": True, "q_label": q.get("label"),
                         "hypotheses": sorted(h.get("label") for h in valid)})
    return Link("S2", False, False, {"found": False})


def _s3(idx) -> Link:
    for p in idx["probes"]:
        rec = p["rec"]
        if not rec.get("label"):
            continue  # только оцениваемые пробы
        out = p["outcome"]
        if out is None:
            continue
        if p["pre"] is None or p["pre"].get("seq", 0) >= rec.get("seq", 0):
            continue  # S3 включает предзапись pre_p (до исполнения; §7.2)
        confirmed = out.get("distinguish_confirmed")
        recorded_ok = out.get("distinguish_ok")
        if not confirmed or recorded_ok is None:
            continue  # проба без DISTINGUISH
        # независимый пересчёт по записям hypothesis
        probe_cell = rec.get("descriptor", "").split(" ", 1)[-1]
        recalc_all, preds = True, []
        for h_label in confirmed:
            h = idx["hypotheses"].get(h_label)
            if h is None or h.get("seq", 0) >= rec.get("seq", 0):
                recalc_all = False
                break
            if h.get("cell") != probe_cell:
                recalc_all = False
                break
            preds.append(h.get("prediction"))
        recalc_ok = recalc_all and (len(set(preds)) > 1) and len(confirmed) >= 2
        if bool(recorded_ok) != recalc_ok:
            return Link("S3", False, False,
                        {"found": False, "inconsistency": True,
                         "p_label": rec.get("label"),
                         "note": "probe_outcome.distinguish_ok не совпадает с пересчётом"})
        if not recalc_ok:
            continue
        origin = (rec.get("origin") == "agent"
                  and p["pre"] is not None and p["pre"].get("origin") == "agent"
                  and all(idx["hypotheses"][h].get("origin") == "agent" for h in confirmed))
        return Link("S3", True, origin,
                    {"found": True, "p_label": rec.get("label"),
                     "confirmed": list(confirmed), "distinguish_ok": True})
    return Link("S3", False, False, {"found": False})


def _s4(idx) -> Link:
    per = []
    for label, v in sorted(idx["verdicts"].items(), key=lambda kv: kv[1]["seq"]):
        p = idx["probes_by_label"].get(v.get("after"))
        seq_ok = revealed = False
        if p is not None and p["outcome"] is not None:
            seq_ok = p["outcome"].get("seq", 0) < v.get("seq", 0)
            revealed = bool(p["outcome"].get("revealed"))
        structural = (p is not None and p["outcome"] is not None and seq_ok and revealed)
        check = idx["checks"].get(v.get("seq"))
        check_value = check.get("value") if check else None
        reason = None
        if structural:
            if check_value is not None:
                reason = check_value
            else:
                h = idx["hypotheses"].get(v.get("h_label"))
                probe_cell = p["rec"].get("descriptor", "").split(" ", 1)[-1]
                # N1/N2 (дополнение №1 v1.0): прогноз для клетки пробы
                # отсутствует — not_checked (перенос из других клеток/текста
                # запрещён)
                reason = ("not_checked_no_cell_match"
                          if (h is not None and h.get("cell") != probe_cell)
                          else "not_checked_missing")
        per.append({"label": label, "structural": structural, "check": check_value,
                    "check_reason": reason, "after": v.get("after"),
                    "origin": v.get("origin")})
    structural_ok = [x for x in per if x["structural"]]
    if not structural_ok:
        return Link("S4", False, False,
                    {"found": False, "verdicts": per,
                     "reason": "нет вердикта после раскрытия исхода с валидной ссылкой"})
    first = structural_ok[0]
    # N3 (A14, дополнение №1 v1.0): приоритет not_checked > mismatch > match;
    # отдельные проверки сохраняются в per (агрегат не уничтожает информацию)
    reasons = [x["check_reason"] for x in structural_ok]
    if any(r not in ("match", "mismatch") for r in reasons):
        correct = "not_checked"
    elif any(r == "mismatch" for r in reasons):
        correct = "mismatch"
    else:
        correct = "match"
    return Link("S4", True, first["origin"] == "agent",
                {"found": True, "verdicts": per, "correct": correct,
                 "first_verdict": first["label"]})


def _s5(idx) -> Link:
    rows = idx["rows"]
    for d in sorted(idx["decisions"], key=lambda r: r["seq"]):
        v_label = d.get("using")
        if v_label not in idx["verdicts"]:
            continue
        nxt = None
        for r in rows:
            if r.get("type") == "action_requested" and r.get("seq", 0) > d.get("seq", 0):
                nxt = r
                break
        if nxt is None:
            continue
        dd, da = d.get("descriptor", ""), nxt.get("descriptor", "")
        if dd.startswith("probe ") or da.startswith("probe "):
            match = (dd == da)
        else:
            match = (dd == da)  # repeat/reset — по типу действия
        if match:
            return Link("S5", True, d.get("origin") == "agent",
                        {"found": True, "decision_seq": d.get("seq"),
                         "using": v_label, "descriptor": dd})
    return Link("S5", False, False, {"found": False})


def _norm_echo(s: str) -> str:
    """Нормализация для N4: свёртка пробелов + приведение регистра."""
    return " ".join(s.split()).casefold()


def is_echo_content(candidate: str, messages) -> bool:
    """N4 (A12, дополнение №1 v1.0): узкое определение «эха текста».

    Эхо ⟺ содержательная часть после нормализации ПОЛНОСТЬЮ совпадает с
    сообщённым исходом или текстом соответствующего наблюдения. Формальные
    вердикты грамматики v1 всегда содержат утверждение (supported|refuted
    о конкретной H) и самостоятельной содержательной части не имеют — по
    построению эхом не являются; проверка применяется к текстовому
    содержимому при его появлении (расширение грамматики).
    """
    norm = _norm_echo(candidate)
    if not norm:
        return False
    return any(norm == _norm_echo(m) for m in messages)


def _echo_messages(idx):
    """Сообщённые исходы/наблюдения из журнала (для N4)."""
    msgs = []
    for r in idx["rows"]:
        if r.get("type") == "probe_outcome":
            msgs.append(str(r.get("outcome", "")))
            msgs.append(f"{r.get('cell', '')} = {r.get('outcome', '')}")
    return msgs


def _s6(idx) -> Link:
    vacuous = (not idx["probes"]) and (not idx["verdicts"])
    # (a) предзапись до исполнения — для всех оцениваемых проб
    pre_ok = True
    pre_problems = []
    for p in idx["probes"]:
        if not p["rec"].get("label"):
            continue
        pre = p["pre"]
        if pre is None or pre.get("seq", 0) >= p["rec"].get("seq", 0):
            pre_ok = False
            pre_problems.append(p["rec"].get("label"))
    # (b) порядок: вердикт после раскрытия исхода
    order_ok = True
    order_problems = []
    for label, v in idx["verdicts"].items():
        p = idx["probes_by_label"].get(v.get("after"))
        if p is not None and p["outcome"] is not None:
            if p["outcome"].get("seq", 0) >= v.get("seq", 0):
                order_ok = False
                order_problems.append(label)
    # (c) отсутствие «воскрешения» опровергнутых (консервативно; см. docstring)
    reuse_ok = True
    reuse_problems = []
    refuted = {v.get("h_label"): v.get("seq", 0)
               for v in idx["verdicts"].values() if v.get("resolution") == "refuted"}
    if refuted:
        ref_seq = min(refuted.values())
        for p in idx["probes"]:
            out = p["outcome"]
            if out is None or out.get("seq", 0) <= ref_seq:
                continue
            hit = set(out.get("distinguish_confirmed") or []) & set(refuted)
            if hit:
                reuse_ok = False
                reuse_problems.append({"p_label": p["rec"].get("label"),
                                       "hypotheses": sorted(hit)})
        for label, v in idx["verdicts"].items():
            if v.get("seq", 0) > ref_seq and v.get("h_label") in refuted:
                reuse_ok = False
                reuse_problems.append({"verdict": label, "hypothesis": v.get("h_label")})
    # (d) N4 (A12, дополнение №1 v1.0): «эхо текста» — узкое определение
    echo_violations = []
    messages = _echo_messages(idx)
    for label, v in idx["verdicts"].items():
        content = v.get("content_text")
        if content and is_echo_content(content, messages):
            echo_violations.append(label)
    echo_ok = not echo_violations
    structural = (not vacuous) and pre_ok and order_ok and reuse_ok and echo_ok
    return Link("S6", structural, structural,
                {"pre_before_action": pre_ok, "pre_problems": pre_problems,
                 "verdict_after_outcome": order_ok, "order_problems": order_problems,
                 "reuse_refuted": reuse_ok, "reuse_problems": reuse_problems,
                 "echo": {"norm": "addendum-1.0", "violations": echo_violations},
                 "vacuous": vacuous,
                 "open_components": list(S6_OPEN_COMPONENTS)})


# --- основной вход ------------------------------------------------------------

def audit_journal(rows) -> AuditReport:
    """Аудит по списку записей журнала (§10)."""
    idx = _index(list(rows))
    links = {"S1": _s1(idx), "S2": _s2(idx), "S3": _s3(idx), "S4": _s4(idx),
             "S5": _s5(idx), "S6": _s6(idx)}
    structural_full = all(l.structural for l in links.values())
    agent_full = all(l.agent for l in links.values())
    correct_s4 = links["S4"].details.get("correct")
    not_checked = (correct_s4 == "not_checked")
    agent_valid_full = agent_full and (correct_s4 == "match")
    status_hint = "inconclusive_not_checked" if not_checked else "normal"
    return AuditReport(links=links, structural_full=structural_full,
                       agent_full=agent_full, agent_valid_full=agent_valid_full,
                       correct_s4=correct_s4, not_checked=not_checked,
                       status_hint=status_hint, s6_complete=S6_COMPLETE_RATIFIED,
                       open_questions=OPEN_QUESTIONS)


def audit_run(run_dir) -> AuditReport:
    """Аудит прогона по каталогу (`raw/journal.jsonl`; только чтение)."""
    path = Path(run_dir) / "raw" / "journal.jsonl"
    return audit_journal(read_journal(path))
