#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — строгий парсер ответов агента (закрытая грамматика §7; ред. 26).

Реализует:
- §7   синтаксис строк (QUESTION/HYPOTHESIS/ACTION/PREDICT/DECISION/VERDICT/
       REJECTED/FINAL/NOTE/NOTES): строгий регистр ключевых слов, «свёртка
       пробелов», обёртки невалидны; лимиты длин (Q ≤200, REJECTED ≤120,
       NOTE ≤300);
- §7.1 прогнозы батареи F1/F3: ровно 9 клеток, без дубликатов и пропусков;
- §7.2 блоки F2 `[DECISION] PREDICT ACTION [DISTINGUISH]`: полная валидация
       ДО исполнения; коды `action_rejected` (`action_invalid` /
       `predict_invalid` / `decision_invalid` / `distinguish_failed`) в
       фиксированном порядке — первой непройденной проверки;
- §7   атомарность NOTE по ответу (ред. 24–26): заметки регистрируются
       только при успешном прохождении ВСЕХ обязательных проверок (а)–(г);
- §7   реестр меток Q/H/P/V: сквозные последовательности, следующая метка —
       «последняя + 1»; отказы «повтор/пропуск/уменьшение/ссылка на
       незарегистрированную» — отдельная категория (НЕ `action_rejected`,
       §7 «Счётчик malformed»).

Границы модуля: разбор и валидация. Исполнение действий (мир), журнал,
аудитор S1–S6 и вызовы модели — отдельные компоненты (следующие блоки).
Модуль детерминирован; сеть не используется; файлы не изменяются.

Реализационные трактовки (зафиксированы в отчёте блока):
Т1. «Свёртка пробелов» — нормализация пробельных последовательностей к
    одному пробелу до сопоставления шаблонам; регистр ключевых слов строгий.
Т2. Нераспознанная строка валит «полный разбор» (а); ACTION/DECISION/PREDICT
    имеют широкий матч, их внутренние нарушения классифицируются кодами
    блока (1–4). Строка ACTION с нарушенным полем DISTINGUISH (битые имена /
    менее 2 различных гипотез) — «строки вне грамматики» → `action_invalid`.
Т3. NOTE вне F2: в F1/F3 — «лишняя строка» (invalid_forecast у вызывающего
    валидатора прогнозов); в прочих фазах не создаёт записи и не валит (а).
Т4. Отказы Q/H/VERDICT не создают записей журнала (закрытый список §11);
    фиксируются результатом валидации (derived/отчёт — на шаге журнала).
Т5. Вердикт на пробу, исполненную в этом же ответе, не проходит: исход
    должен быть раскрыт ДО записи вердикта.
Т6. DISTINGUISH «записаны ранее» — реестр на момент валидации (включая Q/H
    текущего ответа); проверка блоков выполняется после регистраций Q/H/V.
Т7 (N8, дополнение №1 v1.0). `USING V<n>` в блоке F2 допустим только для
    вердикта, зарегистрированного РАНЕЕ: в предыдущих ответах или строкой
    выше в текущем ответе (позиции вердиктов текущего ответа проверяются
    по индексам строк); ссылка на вердикт, объявленный ниже по тексту, —
    `decision_invalid`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from world import Cell

MAX_QUESTION_TEXT = 200
MAX_REJECT_REASON = 120
MAX_NOTE_TEXT = 300

#: Коды `action_rejected` (§7, фиксированный порядок проверок 1→2→3→4).
REASON_ACTION_INVALID = "action_invalid"
REASON_PREDICT_INVALID = "predict_invalid"
REASON_DECISION_INVALID = "decision_invalid"
REASON_DISTINGUISH_FAILED = "distinguish_failed"

#: Категории строк.
KINDS = ("blank", "question", "hypothesis", "action", "predict", "decision",
         "verdict", "rejected", "final", "note", "notes", "unrecognized")


@dataclass(frozen=True)
class ParsedLine:
    """Результат разбора одной строки ответа."""
    index: int                 # 1-based номер строки
    raw: str                   # исходная строка
    norm: str                  # нормализованная строка (свёртка пробелов)
    kind: str                  # одна из KINDS
    data: dict = field(default_factory=dict)
    error: Optional[str] = None  # невалидность, валящая «полный разбор» (а)


def normalize_line(raw: str) -> str:
    """Свёртка пробелов (§7): пробельные последовательности → один пробел."""
    return " ".join(raw.split())


_PROBE_RE = re.compile(r"probe (O[1-4]) T=([0-2]) H=([0-2])")


def parse_action_body(body: str) -> dict:
    """Разбор дескриптора действия по общей форме (§7):
    `probe <клетка> | repeat | reset`. Возвращает kind/cell/desc_error."""
    m = _PROBE_RE.fullmatch(body)
    if m:
        return {"kind": "probe",
                "cell": Cell(m.group(1), int(m.group(2)), int(m.group(3))),
                "desc_error": None}
    if body == "repeat":
        return {"kind": "repeat", "cell": None, "desc_error": None}
    if body == "reset":
        return {"kind": "reset", "cell": None, "desc_error": None}
    return {"kind": None, "cell": None, "desc_error": "descriptor_invalid"}


def desc_text(kind: Optional[str], cell: Optional[Cell]) -> Optional[str]:
    """Нормализованный дескриптор для полей `requested`/журнала."""
    if kind == "probe" and cell is not None:
        return f"probe {cell.as_text()}"
    if kind in ("repeat", "reset"):
        return kind
    return None


_H_RE = r"H[1-9][0-9]*"
_Q_RE = r"Q[1-9][0-9]*"
_P_RE = r"P[1-9][0-9]*"
_V_RE = r"V[1-9][0-9]*"


def parse_line(raw: str, index: int = 0, phase: Optional[str] = None) -> ParsedLine:
    """Разбор одной строки (строгая грамматика §7). См. трактовки Т1–Т3."""
    s = normalize_line(raw)
    if not s:
        return ParsedLine(index, raw, s, "blank", {})

    # QUESTION Q<n>: <текст ≤200> REF: <trial_id>
    m = re.fullmatch(rf"QUESTION ({_Q_RE}): (.+) REF: (\S+)", s)
    if m:
        text = m.group(2)
        err = "text_too_long" if len(text) > MAX_QUESTION_TEXT else None
        return ParsedLine(index, raw, s, "question",
                          {"n": int(m.group(1)[1:]), "text": text, "ref": m.group(3)}, err)

    # HYPOTHESIS H<n> OF Q<m>: <текст> PREDICT: <клетка> = <исход>
    m = re.fullmatch(rf"HYPOTHESIS ({_H_RE}) OF ({_Q_RE}): (.+?) PREDICT: "
                     r"(O[1-4]) T=([0-2]) H=([0-2]) = (present|disappeared)", s)
    if m:
        return ParsedLine(index, raw, s, "hypothesis",
                          {"n": int(m.group(1)[1:]), "q": int(m.group(2)[1:]),
                           "text": m.group(3),
                           "cell": Cell(m.group(4), int(m.group(5)), int(m.group(6))),
                           "prediction": m.group(7)})

    # ACTION: <дескриптор> [DISTINGUISH: H<i>,H<j>]
    m = re.fullmatch(r"ACTION: (.+?)(?: DISTINGUISH: (.+))?", s)
    if m:
        body = m.group(1)
        d = parse_action_body(body)
        dist_raw = m.group(2)
        dist_nums: Optional[list] = None
        dist_err: Optional[str] = None
        if dist_raw is not None:
            parts = [p.strip() for p in dist_raw.split(",")]
            ok_names = all(re.fullmatch(_H_RE, p) for p in parts)
            if ok_names:
                nums = [int(p[1:]) for p in parts]
                if len(nums) < 2 or len(set(nums)) < 2:
                    dist_err = "bad_distinguish_list"
                else:
                    dist_nums = nums
            else:
                dist_err = "bad_distinguish_list"
        data = {"body": body, "action_kind": d["kind"], "cell": d["cell"],
                "desc_error": d["desc_error"], "distinguish": dist_nums,
                "distinguish_error": dist_err}
        return ParsedLine(index, raw, s, "action", data)

    # REJECTED: H<n> REASON: <текст ≤120>
    m = re.fullmatch(rf"REJECTED: ({_H_RE}) REASON: (.+)", s)
    if m:
        reason = m.group(2)
        err = "reason_too_long" if len(reason) > MAX_REJECT_REASON else None
        return ParsedLine(index, raw, s, "rejected",
                          {"h": int(m.group(1)[1:]), "reason": reason}, err)

    # VERDICT: H<n> <supported|refuted> AFTER P<n>  (широкий матч; см. Т2)
    m = re.fullmatch(r"VERDICT: (.+)", s)
    if m:
        body = m.group(1)
        vm = re.fullmatch(rf"({_H_RE}) (supported|refuted) AFTER ({_P_RE})", body)
        if vm:
            data = {"h": int(vm.group(1)[1:]), "resolution": vm.group(2),
                    "after_p": int(vm.group(3)[1:]), "malformed": False}
        else:
            data = {"malformed": True, "body": body}
        return ParsedLine(index, raw, s, "verdict", data)

    # DECISION: <дескриптор> USING V<n>  (широкий матч; см. Т2)
    m = re.fullmatch(r"DECISION: (.+)", s)
    if m:
        body = m.group(1)
        if " USING " in body:
            desc_part, ref_part = body.split(" USING ", 1)
            vm = re.fullmatch(_V_RE, ref_part)
            using_v = int(ref_part[1:]) if vm else None
            using_error = None if vm else "bad_using_ref"
        else:
            desc_part, using_v, using_error = body, None, "missing_using"
        d = parse_action_body(desc_part)
        data = {"descriptor": desc_part, "desc_error": d["desc_error"],
                "action_kind": d["kind"], "cell": d["cell"],
                "using_v": using_v, "using_error": using_error}
        return ParsedLine(index, raw, s, "decision", data)

    # FINAL: <текст>
    m = re.fullmatch(r"FINAL: (.+)", s)
    if m:
        return ParsedLine(index, raw, s, "final", {"text": m.group(1)})

    # NOTES: <свободный текст> (не журналируется, не зачёт; §7)
    m = re.fullmatch(r"NOTES: (.+)", s)
    if m:
        return ParsedLine(index, raw, s, "notes", {"text": m.group(1)})

    # NOTE: <текст ≤300> (только F2; см. Т3)
    m = re.fullmatch(r"NOTE: (.+)", s)
    if m:
        text = m.group(1)
        err = "text_too_long" if len(text) > MAX_NOTE_TEXT else None
        data = {"text": text, "phase": phase}
        if phase in ("F1", "F3"):
            data["fatal_phase"] = True      # «лишняя строка» → invalid_forecast
        elif phase is not None and phase != "F2":
            data["not_allowed"] = True      # запись не создаётся; (а) не валит
        return ParsedLine(index, raw, s, "note", data, err)

    # PREDICT: <клетка> = <исход> (широкий матч; см. Т2)
    m = re.fullmatch(r"PREDICT: (.*)", s)
    if m:
        body = m.group(1)
        pm = re.fullmatch(r"(O[1-4]) T=([0-2]) H=([0-2]) = (present|disappeared)", body)
        if pm:
            data = {"cell": Cell(pm.group(1), int(pm.group(2)), int(pm.group(3))),
                    "outcome": pm.group(4), "error": None}
        else:
            data = {"cell": None, "outcome": None, "error": "bad_predict"}
        return ParsedLine(index, raw, s, "predict", data)

    return ParsedLine(index, raw, s, "unrecognized", {})


def parse_response(text: str, phase: Optional[str] = None) -> list:
    """Разбор всего ответа; фаза влияет на правила NOTE (Т3)."""
    return [parse_line(raw, index=i, phase=phase)
            for i, raw in enumerate(text.splitlines(), 1)]


# --- Реестр меток (§7: сквозные последовательности, следующая = последняя+1) ---

@dataclass
class LabelRegistry:
    last: dict
    questions: dict
    hypotheses: dict
    probes: dict
    verdicts: dict

    @classmethod
    def new(cls) -> "LabelRegistry":
        return cls({"Q": 0, "H": 0, "P": 0, "V": 0}, {}, {}, {}, {})

    def propose(self, series: str, n: int):
        """Проверка номера метки: только «последняя + 1»."""
        want = self.last[series] + 1
        if n == want:
            return True, None
        if n <= self.last[series]:
            return False, f"повтор или уменьшение номера (последняя {series}{self.last[series]})"
        return False, f"пропуск номера (ожидается {series}{want})"

    def register_question(self, n: int, text: str, ref: str, origin: str = "agent"):
        ok, why = self.propose("Q", n)
        if not ok:
            return False, why
        self.questions[n] = {"text": text, "ref": ref, "origin": origin}
        self.last["Q"] = n
        return True, None

    def register_hypothesis(self, n: int, q: int, text: str, cell: Cell,
                            prediction: str, origin: str = "agent"):
        ok, why = self.propose("H", n)
        if not ok:
            return False, why
        self.hypotheses[n] = {"q": q, "text": text, "cell": cell,
                              "prediction": prediction, "origin": origin}
        self.last["H"] = n
        return True, None

    def has_q(self, n: int) -> bool:
        return n in self.questions

    def has_h(self, n: int) -> bool:
        return n in self.hypotheses

    def has_p(self, n: int) -> bool:
        return n in self.probes

    def has_v(self, n: int) -> bool:
        return n in self.verdicts

    def commit_probe(self, cell: Cell, outcome: str, revealed: bool) -> int:
        """Механическое присвоение `P<n>` при исполнении пробы (§7)."""
        self.last["P"] += 1
        n = self.last["P"]
        self.probes[n] = {"cell": cell, "outcome": outcome, "revealed": revealed}
        return n

    def commit_verdict(self, h: int, resolution: str, after_p: int) -> int:
        """Механическое присвоение `V<n>` при записи вердикта (§7)."""
        self.last["V"] += 1
        n = self.last["V"]
        self.verdicts[n] = {"h": h, "resolution": resolution, "after_p": after_p}
        return n


# --- Блоки F2 (§7.2) ---------------------------------------------------------

@dataclass(frozen=True)
class BlockResult:
    lines: tuple
    ok: bool
    plan: Optional[dict] = None
    reason: Optional[str] = None                 # код action_rejected
    requested: Optional[str] = None              # нормализованный дескриптор
    distinguish_confirmed: Optional[tuple] = None
    distinguish_ok: Optional[bool] = None


def collect_windows(parsed: list) -> list:
    """Окна блоков F2: последовательности строк [DECISION][PREDICT][ACTION].
    Строки NOTE и пустые — прозрачны (§7.2; пустые — Т1); прочие — границы."""
    windows, cur = [], []
    for line in parsed:
        if line.kind in ("blank", "note"):
            continue
        if line.kind in ("decision", "predict", "action"):
            cur.append(line)
        else:
            if cur:
                windows.append(cur)
                cur = []
    if cur:
        windows.append(cur)
    return windows


def validate_window(window: list, registry: LabelRegistry,
                    last_probe_cell: Optional[Cell] = None,
                    verdict_positions: Optional[dict] = None) -> BlockResult:
    """Полная валидация одного окна F2 ДО исполнения (§7.2).
    Коды — первая непройденная проверка в порядке 1→2→3→4 (§7).
    `verdict_positions` — {номер вердикта: индекс строки} для вердиктов,
    зарегистрированных в ТЕКУЩЕМ ответе (N8 v1.0, п.7)."""
    idxs = tuple(l.index for l in window)
    decs = [l for l in window if l.kind == "decision"]
    preds = [l for l in window if l.kind == "predict"]
    acts = [l for l in window if l.kind == "action"]

    # п.1: action_invalid (композиция блока / дескриптор)
    if not acts:
        if preds:
            return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                               requested=None)
        if decs:
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=None)
        return BlockResult(idxs, True, plan=None)
    if len(acts) > 1:
        a0 = acts[0]
        return BlockResult(idxs, False, reason=REASON_ACTION_INVALID,
                           requested=desc_text(a0.data.get("action_kind"),
                                               a0.data.get("cell")))
    a = acts[0]
    if a.data.get("desc_error"):
        return BlockResult(idxs, False, reason=REASON_ACTION_INVALID, requested=None)
    req = desc_text(a.data["action_kind"], a.data.get("cell"))
    if a.data.get("distinguish_error"):
        return BlockResult(idxs, False, reason=REASON_ACTION_INVALID, requested=req)
    if a.data["action_kind"] == "reset" and a.data.get("distinguish") is not None:
        return BlockResult(idxs, False, reason=REASON_ACTION_INVALID, requested=req)
    if len(decs) > 1:
        return BlockResult(idxs, False, reason=REASON_ACTION_INVALID, requested=req)
    kind = a.data["action_kind"]
    acell = a.data.get("cell")

    # п.2: predict_invalid
    if kind in ("probe", "repeat"):
        if not preds or len(preds) > 1:
            return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                               requested=req)
        p = preds[0]
        if p.data.get("error"):
            return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                               requested=req)
        if kind == "repeat":
            if last_probe_cell is None:
                return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                                   requested=req)
            if p.data["cell"] != last_probe_cell:
                return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                                   requested=req)
        else:
            if p.data["cell"] != acell:
                return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                                   requested=req)
    else:  # reset
        if preds:
            return BlockResult(idxs, False, reason=REASON_PREDICT_INVALID,
                               requested=req)

    # п.3: decision_invalid
    dec_norm = None
    using_v = None
    if decs:
        d = decs[0]
        if d.data.get("desc_error") is not None:
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=req)
        if d.data.get("using_v") is None:
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=req)
        if not registry.has_v(d.data["using_v"]):
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=req)
        if verdict_positions is not None:
            vpos = verdict_positions.get(d.data["using_v"])
            if vpos is not None and vpos > d.index:   # N8 v1.0, п.7: только «ранее записанный»
                return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                                   requested=req)
        if d.data["action_kind"] != kind:
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=req)
        if kind == "probe" and d.data.get("cell") != acell:
            return BlockResult(idxs, False, reason=REASON_DECISION_INVALID,
                               requested=req)
        dec_norm = desc_text(d.data["action_kind"], d.data.get("cell"))
        using_v = d.data["using_v"]

    # п.4: distinguish_failed
    dst = a.data.get("distinguish")
    dst_info = None
    if dst is not None:
        confirmed, pred_values = [], []
        for hn in dst:
            hrec = registry.hypotheses.get(hn)
            if hrec is None:
                continue
            if hrec["cell"] != acell:
                continue
            confirmed.append(hn)
            pred_values.append(hrec["prediction"])
        all_ok = (len(confirmed) == len(dst))
        differ = (len(set(pred_values)) > 1)
        if not (all_ok and differ):
            return BlockResult(idxs, False, reason=REASON_DISTINGUISH_FAILED,
                               requested=req,
                               distinguish_confirmed=tuple(f"H{n}" for n in confirmed),
                               distinguish_ok=False)
        dst_info = {"list": list(dst), "confirmed": [f"H{n}" for n in confirmed],
                    "ok": True}

    # ok
    prediction = None
    if kind in ("probe", "repeat"):
        prediction = {"cell": preds[0].data["cell"], "outcome": preds[0].data["outcome"]}
    plan = {"action": kind, "cell": acell, "prediction": prediction,
            "decision": dec_norm, "using_v": using_v, "distinguish": dst_info}
    return BlockResult(idxs, True, plan=plan)


# --- F1/F3: прогнозы батареи (§7.1) ------------------------------------------

@dataclass(frozen=True)
class ForecastResult:
    ok: bool
    predictions: dict      # Cell -> outcome
    problems: tuple
    bad_raw: tuple = ()    # v33: (index, raw) строки, привязанные к problems


def validate_forecast(parsed: list, battery_cells) -> ForecastResult:
    """Валидация ответа F1/F3 (§7.1): ровно 9 прогнозов по клеткам батареи;
    дубликат/пропуск/лишняя или невалидная строка → invalid_forecast."""
    battery = set(battery_cells)
    problems, preds, bad_raw, line_of = [], {}, [], {}
    for l in parsed:
        if l.kind == "blank":
            continue
        if l.kind != "predict":
            problems.append(f"строка {l.index}: лишняя конструкция ({l.kind})")
            bad_raw.append((l.index, l.raw))
            continue
        if l.data.get("error"):
            problems.append(f"строка {l.index}: невалидный PREDICT")
            bad_raw.append((l.index, l.raw))
            continue
        c = l.data["cell"]
        if c in preds:
            problems.append(f"строка {l.index}: дубликат клетки {c.as_text()}")
            bad_raw.append((l.index, l.raw))
            continue
        preds[c] = l.data["outcome"]
        line_of[c] = (l.index, l.raw)
    for c in sorted(battery - set(preds)):
        problems.append(f"пропуск клетки {c.as_text()}")
    for c in sorted(set(preds) - battery):
        problems.append(f"лишняя клетка {c.as_text()}")
        bad_raw.append(line_of[c])
    ok = (not problems) and (len(preds) == len(battery))
    return ForecastResult(ok=ok, predictions=preds, problems=tuple(problems),
                          bad_raw=tuple(bad_raw))


# --- F2: полная валидация ответа (проверки (а)–(г), §7; атомарность NOTE) ----

@dataclass
class F2Validation:
    parsed: list
    full_parse_ok: bool
    blocks: list
    qh_failures: list
    verdict_failures: list
    mode_violations: list
    notes: list                # [(index, text)] — к регистрации (или пусто)
    plans: list                # планы исполнения ok-блоков
    verdicts_committed: list   # [(line_index, n)] — вердикты, зарегистрированные валидатором


def validate_f2(text_or_parsed, registry: LabelRegistry, known_trials,
                mode: str = "K0-M3", last_probe_cell: Optional[Cell] = None) -> F2Validation:
    """Полная валидация ответа F2:
    (а) полный разбор; (б) нет action_rejected; (в) нет отказов Q/H и VERDICT;
    (г) нет mode_violation. NOTE регистрируются только если (а)–(г) пройдены.
    """
    parsed = (parse_response(text_or_parsed, phase="F2")
              if isinstance(text_or_parsed, str) else text_or_parsed)
    full_parse_ok = not any(l.kind == "unrecognized" or l.error for l in parsed)

    qh_failures, verdict_failures, mode_violations = [], [], []
    verdicts_committed = []
    verdict_positions = {}   # N8 v1.0, п.7: позиции вердиктов текущего ответа

    # Порядок строк: регистрации Q/H и вердиктов (ссылочная валидация).
    for l in parsed:
        if l.kind == "question":
            if mode == "K1b":
                mode_violations.append({"index": l.index, "kind": "question"})
                continue
            if l.error:
                continue
            if l.data["ref"] not in known_trials:
                qh_failures.append({"index": l.index, "kind": "question",
                                    "n": l.data["n"],
                                    "reason": f"REF на неизвестное наблюдение: {l.data['ref']}"})
                continue
            ok, why = registry.register_question(l.data["n"], l.data["text"], l.data["ref"])
            if not ok:
                qh_failures.append({"index": l.index, "kind": "question",
                                    "n": l.data["n"], "reason": why})
        elif l.kind == "hypothesis":
            if mode == "K1b":
                mode_violations.append({"index": l.index, "kind": "hypothesis"})
                continue
            if not registry.has_q(l.data["q"]):
                qh_failures.append({"index": l.index, "kind": "hypothesis",
                                    "n": l.data["n"],
                                    "reason": f"ссылка OF Q{l.data['q']} на незарегистрированный вопрос"})
                continue
            ok, why = registry.register_hypothesis(l.data["n"], l.data["q"],
                                                   l.data["text"], l.data["cell"],
                                                   l.data["prediction"])
            if not ok:
                qh_failures.append({"index": l.index, "kind": "hypothesis",
                                    "n": l.data["n"], "reason": why})
        elif l.kind == "verdict":
            if mode == "K1b":
                mode_violations.append({"index": l.index, "kind": "verdict"})
                continue
            if l.data.get("malformed"):
                verdict_failures.append({"index": l.index, "reason": "невалидная форма VERDICT"})
                continue
            h, p = l.data["h"], l.data["after_p"]
            if not registry.has_h(h):
                verdict_failures.append({"index": l.index,
                                         "reason": f"AFTER-ссылка: гипотеза H{h} не зарегистрирована"})
                continue
            if not registry.has_p(p):
                verdict_failures.append({"index": l.index,
                                         "reason": f"AFTER-ссылка: проба P{p} не исполнена"})
                continue
            if not registry.probes[p]["revealed"]:
                verdict_failures.append({"index": l.index,
                                         "reason": f"исход пробы P{p} не раскрыт агенту до записи вердикта"})
                continue
            n = registry.commit_verdict(h, l.data["resolution"], p)
            verdicts_committed.append((l.index, n))
            verdict_positions[n] = l.index
        elif l.kind == "decision" and mode == "K1b":
            mode_violations.append({"index": l.index, "kind": "decision"})

    # Блоки действий (б) — после регистраций Q/H/V (Т6).
    blocks = [validate_window(w, registry, last_probe_cell, verdict_positions)
              for w in collect_windows(parsed)]

    blocked = (not full_parse_ok
               or any(not b.ok for b in blocks)
               or bool(qh_failures)
               or bool(verdict_failures)
               or bool(mode_violations))
    notes = [] if blocked else [(l.index, l.data["text"])
                                for l in parsed if l.kind == "note"]
    plans = [b.plan for b in blocks if b.ok and b.plan]
    return F2Validation(parsed=parsed, full_parse_ok=full_parse_ok, blocks=blocks,
                        qh_failures=qh_failures, verdict_failures=verdict_failures,
                        mode_violations=mode_violations, notes=notes, plans=plans,
                        verdicts_committed=verdicts_committed)
