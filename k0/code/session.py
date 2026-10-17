#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — сессия/оркестратор v1 (§6/§12 замороженного протокола ред. 26).

Прогон K0-M1 одной сессии:
- F1: история наблюдений (показана агенту) + 9 прогнозов батареи
  (до 3 попыток; 1+2 повтора — тот же промпт; v33: начиная со 2-й попытки —
  блок [ОТКАЗ F1] с перечнем невалидных строк; исчерпание → invalid_final);
- F2: цикл действий (бюджет 16): каждый ход — полный разбор ответа (§7),
  валидация блоков ДО исполнения (§7.2), записи §11 в порядке строк;
- F3: новые 9 прогнозов без обратной связи (те же правила повторов);
- F4: FINAL (до 3 попыток; отсутствие не влияет на вердикт, фиксируется);
- F5: аудит S1–S6 (§10) + derived (e_set, forecasts, metrics, audit).

Стоп-критерии (§12): STOP-файл оператора — немедленная остановка сессии
(после срабатывания ни одно последующее действие агента не исполняется);
«бюджет исчерпан» и «K достигнут (проб не осталось)» — нормальное
завершение F2; ошибки — нарушение инварианта: сессия переходит в FAILED и
не продолжается (журнал не «ремонтируется» молча).

Границы v1: агент — внешний callable `respond(phase, ctx, attempt) -> str`
(в прогоне — канал модели; в синтетике — скрипт). Вызовы модели и сети
внутри сессии ЗАПРЕЩЕНЫ и не выполняются. Режим — только K0-M1;
K1b-оркестрация (водимые драйвером Q/H/V/D) — следующий этап.

Известные открытые пункты (см. ASSUMPTIONS.md; поведение/оценку не
подменяют, вынесены на подтверждение):
- «K достигнут (проб не осталось)» — трактуется как |E| = 0 (A18);
- ошибки/остановки (STOP, invalid_final, предохранитель F2) — прогон
  класса INCONCLUSIVE, окончательный вердикт — за разбором постановщиком
  (A17/A19); сессия публикует статус и stop_reason;
- невалидный F2-ответ (не прошедший полный разбор) не исполняется и не
  журналируется; сессия продолжает цикл, предохранитель — не более
  `max_invalid_f2` подряд (A20; предохранитель синтетики, к нормам не
  относится);
- `verdict_check` (match/mismatch): ожидаемый resolution — «supported» ⟺
  прогноз гипотезы равен исходу пробы; сверка — механическая (A21);
- несколько блоков в одном F2-ответе исполняются по порядку (стоп-критерии
  проверяются перед каждым блоком); синтетические тесты используют один
  блок на ход (норма неопределена — A22);
- K1b-оркестрация не реализована (A23).

Стоп-критерии F2 проверяются: перед каждым запросом к агенту, сразу после
ответа (до исполнения) и перед каждым блоком; «после срабатывания стопа
никакие последующие действия агента не исполняются» — гарантировано
отсутствием запросов после HALT.
"""
from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

from world import Cell, World, accuracy, load_battery, load_history, o1_pass
from parser import (LabelRegistry, collect_windows, parse_response,
                    validate_f2, validate_forecast)
from journal import Journal, stop_requested, write_derived_once
from auditor import AuditReport, audit_run
from calls import CallLog, file_sha, render_context, write_passport_once
from channel import ChannelError, classify_error

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"

#: Параметры вызова. v27 (2026-10-16): num_predict 96→256 — единственное
#: изменение относительно T0 §3 (см. акт K0_PROTOCOL_v27_ACT.md).
T0_PARAMS = {"model": "gemma4-e4b-heretic:q4km", "temperature": 0, "seed": 1729,
             "think": False, "num_predict": 256, "num_ctx": 4096, "keep_alive": "30m"}

PHASES = ("F1", "F2", "F3", "F4", "F5")

# v30: сообщения агенту об отказах F2 (контракт валидации НЕ меняется; hint — только текст)
REJECTION_HINTS = {
    "predict_invalid": "нужна отдельная строка PREDICT перед ACTION с прогнозом исхода этой же клетки",
    "action_invalid": "проверь форму строки действия (probe/repeat/reset)",
    "decision_invalid": "DECISION указывает на существующий записанный вердикт V<n> и тот же дескриптор действия",
    "prediction_inconsistent": "прогноз в PREDICT должен быть present или disappeared",
}
QH_HINTS = {
    "dup": "уже зарегистрировано — повторно регистрировать не нужно; используй существующие метки и продолжай работу (следующий шаг — действие)",
    "skip": "нумерация должна идти по порядку без пропуска",
    "ref": "в REF укажи существующий trial_id из наблюдений истории",
    "noq": "сначала зарегистрируй сам вопрос (строка QUESTION), затем гипотезу OF Q<n>",
    "other": "проверь формат регистрации и ссылки между метками",
}


def qh_hint(kind: str, reason: str) -> str:
    """v30: подсказка агенту для отказа регистрации Q/H."""
    r = reason or ""
    if ("повтор или уменьшение" in r) or ("уже" in r):
        return QH_HINTS["dup"]
    if "пропуск номера" in r:
        return QH_HINTS["skip"]
    if ("неизвестн" in r) or ("REF" in r):
        return QH_HINTS["ref"]
    if "не зарегистрирован" in r:
        return QH_HINTS["noq"]
    return QH_HINTS["other"]

STOP_FILE_REASON = "STOP-файл оператора"
REASON_BUDGET = "бюджет исчерпан"
REASON_K = "K достигнут (проб не осталось)"


class SessionError(Exception):
    """Нарушение инварианта сессии: продолжение запрещено."""


class SessionHalt(Exception):
    """Контролируемая остановка сессии (STOP-файл / fail-прогон / предохранитель)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AgentContext:
    """Данные, доступные агенту в данной фазе (только явные источники).

    `history` — показанные наблюдения среды; `observations` — раскрытые
    агентом пробы (клетка, исход); батарея и исходы её нетронутых клеток
    в контекст НИКОГДА не включаются.
    """
    phase: str
    history: tuple
    observations: tuple = ()
    rejections: tuple = ()
    budget_remaining: int = 16
    last_probe: Optional[str] = None
    notes: tuple = ()
    battery: tuple = ()      # перечень клеток батареи (F1/F3; без исходов)
    last_labels: tuple = (0, 0, 0, 0)   # (Q, H, P, V) — §7 «эхо меток»
    hypotheses: tuple = ()   # v32: зарегистрированные гипотезы — ({"n","cell","prediction"}, …)
    f1_rejection: tuple = ()   # v33: причина отказа F1 (для попытки ≥2)
    verdict_step: tuple = ()   # v34: (H, P, клетка, прогноз, исход) — ждёт вердикта
    decision_step: tuple = ()  # v35: (V, H, P, клетка, прогноз, исход, res) — ждёт решения


@dataclass
class SessionResult:
    run_dir: str
    status: str                    # completed | halted | failed
    stop_reason: Optional[str]
    audit: Optional[AuditReport]
    metrics: Optional[dict]
    final_present: bool
    respond_calls: int


class Session:
    """Прогон K0-M1 (одна серия/сид), строго по §6/§12."""

    MAX_INVALID_F2_DEFAULT = 10
    LOOP_FUSE_K = 3                # v30: K подряд итераций без прогресса в F2
    CONTEXT_WARN_THRESHOLD = 3900   # предупреждение при приближении к C1

    def __init__(self, run_dir, respond: Callable, seed: int = 101,
                 mode: str = "K0-M3", battery: Optional[Sequence[Cell]] = None,
                 max_invalid_f2: int = MAX_INVALID_F2_DEFAULT,
                 max_calls: int = 30, max_seconds: float = 2700.0,
                 max_total_tokens: int = 100_000, max_prompt_tokens: int = 4000,
                 require_token_counts: bool = False):
        if mode != "K0-M3":
            raise SessionError(f"режим {mode!r} не реализован в session v1 (только K0-M3)")
        self.run_dir = Path(run_dir)
        self.respond = respond
        self.seed = seed
        self.mode = mode
        self.max_invalid_f2 = max_invalid_f2
        self.cells = (list(battery) if battery is not None
                      else [item.cell for item in load_battery(ARTIFACTS / "heldout_battery.json")])
        self.state = "INIT"        # INIT → RUNNING → DONE | HALTED | FAILED
        self.phase = "F1"
        self.stop_reason: Optional[str] = None
        self.last_response: Optional[str] = None      # v30: предохранитель цикла
        self.last_progress: Optional[int] = None      # v30 ред.2: seq−malformed
        self.loop_streak = 0                          # v30
        self.decisions = 0                            # v35
        self.journal: Optional[Journal] = None
        self.world: Optional[World] = None
        self.registry: Optional[LabelRegistry] = None
        self.calls = None
        self.malformed = 0
        self.rejection_audit = []       # N6 (дополнение №1 v1.0): отказы Q/H/V
        self._rejections_written = False
        self.history: tuple = ()
        self.known_trials: set = set()
        self.f1_pred: dict = {}
        self.f3_pred: dict = {}
        self.f1_status: Optional[str] = None
        self.f1_rejection: tuple = ()   # v33: причина отказа F1 для повтора
        self.f3_status: Optional[str] = None
        self.observations: list = []      # [(Cell, outcome)] — раскрытые пробы
        self.rejections: list = []        # [{"requested", "reason"}]
        self.notes: list = []             # M1: зарегистрированные NOTE (порядок seq)
        self.invalid_f2 = 0
        self.final_present = False
        self.respond_calls = 0
        self.max_calls = max_calls
        self.max_seconds = max_seconds
        self.max_total_tokens = max_total_tokens
        self.max_prompt_tokens = max_prompt_tokens
        self.require_token_counts = require_token_counts
        self.total_tokens = 0
        self.started_at: Optional[float] = None
        self.context_approx: list = []
        self.context_warns: list = []
        self.sent_contexts: list = []     # диагностика: переданные контексты
        self.audit_report: Optional[AuditReport] = None
        self.metrics: Optional[dict] = None
        self._forecasts_written = False

    # --- внешний интерфейс ----------------------------------------------------

    def run(self) -> SessionResult:
        """Полный прогон сессии. Повторный запуск запрещён (INIT → один раз)."""
        if self.state != "INIT":
            raise SessionError(f"сессия не в состоянии INIT (state={self.state})")
        self.state = "RUNNING"
        self.started_at = time.monotonic()
        try:
            self._open()
            self._f1()
            self._f2()
            self._f3()
            self._f4()
            self._f5()
        except SessionHalt as h:
            self.stop_reason = h.reason
            if self.journal is not None:
                self.journal.stop(h.reason)
            self._write_rejections()
            write_passport_once(self.run_dir, self._passport_payload("halted"))
            self.state = "HALTED"
            self._close_journal()
            return self._result("halted")
        except Exception as e:
            self.state = "FAILED"
            self._close_journal()
            if isinstance(e, SessionError):
                raise
            raise SessionError(f"нарушение инварианта сессии: {e!r}") from e
        self.state = "DONE"
        self._close_journal()
        return self._result("completed")

    def _close_journal(self):
        if self.journal is not None:
            self.journal.close()
            self.journal = None

    # --- служебное ------------------------------------------------------------

    def _open(self):
        self.journal = Journal(self.run_dir).open()
        self.world = World(self.cells)
        self.registry = LabelRegistry.new()
        self.calls = CallLog(self.run_dir)
        hist = load_history(ARTIFACTS / f"history_{self.seed}.jsonl")
        self.history = tuple(hist)
        self.known_trials = {r.get("trial_id", f"t{i:02d}") for i, r in enumerate(hist, 1)}

    def _result(self, status: str) -> SessionResult:
        return SessionResult(run_dir=str(self.run_dir), status=status,
                             stop_reason=self.stop_reason, audit=self.audit_report,
                             metrics=self.metrics, final_present=self.final_present,
                             respond_calls=self.respond_calls)

    def _expect(self, phase: str):
        if self.phase != phase:
            raise SessionError(f"нарушение порядка фаз: ожидалась {self.phase}, запрошена {phase}")

    def _call_agent(self, phase: str, ctx: AgentContext, attempt: int) -> str:
        """Вызов агента с политикой O1 (`K0_CHANNEL_O1_ACT.md`):
        1 + ≤2 повтора ТОЛЬКО для класса `no_response`; `server_refusal` и
        `indeterminate` — немедленный стоп; каждая попытка фиксируется
        request/meta-файлами (response — только при полученном ответе);
        проверяются лимиты вызовов/времени/токенов."""
        for k in (1, 2, 3):
            self._check_time_limit()
            self._check_call_limit()
            self.respond_calls += 1
            n = self.calls.request(phase, attempt, render_context(ctx))
            try:
                text = self.respond(phase, ctx, attempt)
            except ChannelError as e:
                self._note_prompt_size()
                cls = classify_error(e)
                self.calls.meta(n, phase, attempt,
                                {"class": cls, "code": e.code, "stage": e.stage})
                if cls == "no_response" and k < 3:
                    continue
                raise SessionHalt(cls)
            self._note_prompt_size()
            if not isinstance(text, str):
                raise SessionError(f"ответ агента не строка: {type(text)!r}")
            meta = getattr(self.respond, "last_meta", None)
            self._apply_meta(meta, n, phase, attempt)
            self.calls.response(n, phase, attempt, text)
            return text
        raise SessionError("недостижимо: цикл вызовов завершился без ответа")

    def _check_call_limit(self):
        if self.respond_calls >= self.max_calls:
            raise SessionHalt("call_limit")

    def _check_time_limit(self):
        if (self.started_at is not None
                and (time.monotonic() - self.started_at) >= self.max_seconds):
            raise SessionHalt("time_limit")

    def _apply_meta(self, meta, n: int, phase: str, attempt: int):
        """meta-файл попытки (O1) + счётчики токенов и автостопы."""
        rec = {"class": "answered"}
        if isinstance(meta, dict):
            rec.update(meta)
        elif self.require_token_counts:
            rec["missing"] = True
            self.calls.meta(n, phase, attempt, rec)
            raise SessionHalt("token_counts_missing")
        self.calls.meta(n, phase, attempt, rec)
        if isinstance(meta, dict):
            p = meta.get("prompt_eval_count")
            e = meta.get("eval_count")
            if isinstance(p, int) and p > self.max_prompt_tokens:
                raise SessionHalt("prompt_over_limit")
            if isinstance(p, int) and isinstance(e, int):
                self.total_tokens += p + e
                if self.total_tokens > self.max_total_tokens:
                    raise SessionHalt("token_budget_exhausted")

    def _note_prompt_size(self):
        """Мониторинг объёма промпта (консервативно: bytes/3.0 — оценка сверху
        для смешанного текста; калибровка F1: 1725 Б ≈ 578 ток). При
        приближении к C1 (порог 3900) — предупреждение. num_ctx НЕ меняется:
        ограничение зафиксировано в акте v27."""
        lp = getattr(self.respond, "last_prompt", None)
        if not isinstance(lp, str):
            return
        approx = math.ceil(len(lp.encode("utf-8")) / 3.0)
        self.context_approx.append(approx)
        if approx > self.CONTEXT_WARN_THRESHOLD:
            self.context_warns.append({"call": self.respond_calls,
                                       "approx_tokens": approx})

    def _gate(self):
        """STOP-файл — немедленная остановка; проверяется во всех фазах."""
        if stop_requested(self.run_dir):
            raise SessionHalt(STOP_FILE_REASON)

    def _context(self, phase: str) -> AgentContext:
        obs = tuple((c.as_text(), y) for c, y in self.observations)
        labels = (self.registry.last["Q"], self.registry.last["H"],
                  self.registry.last["P"], self.registry.last["V"])
        hyp = tuple({"n": n, "cell": h["cell"].as_text(),
                     "prediction": h["prediction"]}
                    for n, h in sorted(self.registry.hypotheses.items()))
        vstep = ()                    # v34: раскрытая проба без вердикта
        if phase == "F2" and self.registry is not None:
            verdicted = {v["h"] for v in self.registry.verdicts.values()}
            by_cell = {}
            for pn, pr in sorted(self.registry.probes.items()):
                if pr.get("revealed") and pr.get("cell") is not None:
                    by_cell.setdefault(pr["cell"], []).append((pn, pr))
            for hn, hr in sorted(self.registry.hypotheses.items()):
                if hn in verdicted:
                    continue
                cand = by_cell.get(hr["cell"])
                if cand:
                    pn, pr = cand[0]
                    vstep = (f"H{hn}", f"P{pn}", hr["cell"].as_text(),
                             hr["prediction"], pr["outcome"])
                    break
        dstep = ()                    # v35: принятый вердикт без решения
        if phase == "F2" and self.registry is not None and self.decisions == 0:
            if self.registry.verdicts:
                _vn, _v = max(self.registry.verdicts.items())
                _h = self.registry.hypotheses.get(_v["h"])
                _p = self.registry.probes.get(_v["after_p"])
                if _h is not None and _p is not None:
                    dstep = (f"V{_vn}", f"H{_v['h']}", f"P{_v['after_p']}",
                             _h["cell"].as_text(), _h["prediction"],
                             _p["outcome"], _v["resolution"])
        return AgentContext(phase=phase, history=self.history, observations=obs,
                            rejections=tuple(self.rejections[-5:]),
                            budget_remaining=self.world.remaining,
                            last_probe=(self.world.last_probe.as_text()
                                        if self.world.last_probe is not None else None),
                            notes=tuple(self.notes),
                            battery=(tuple(c.as_text() for c in self.cells)
                                     if phase in ("F1", "F3") else ()),
                            last_labels=labels,
                            hypotheses=(hyp if phase == "F2" else ()),
                            f1_rejection=(tuple(self.f1_rejection)
                                          if phase == "F1" else ()),
                            verdict_step=vstep,
                            decision_step=dstep)

    # --- F1 / F3 --------------------------------------------------------------

    def _forecast_phase(self, phase: str):
        self._expect(phase)
        self._gate()
        writer = (self.journal.prediction_before if phase == "F1"
                  else self.journal.prediction_after)
        for attempt in (1, 2, 3):
            self._gate()
            ctx = self._context(phase)
            self.sent_contexts.append(ctx)
            text = self._call_agent(phase, ctx, attempt)
            fc = validate_forecast(parse_response(text, phase=phase), self.cells)
            if fc.ok:
                self.journal.forecast_status(phase, attempt, "ok")
                for c in sorted(fc.predictions):
                    writer(c, fc.predictions[c])
                if phase == "F1":
                    self.f1_pred, self.f1_status = fc.predictions, "ok"
                else:
                    self.f3_pred, self.f3_status = fc.predictions, "ok"
                self.f1_rejection = ()
                return
            last = (attempt == 3)
            if phase == "F1":
                self.f1_rejection = (tuple(fc.problems)
                                     + tuple(f"строка {i}: {raw}"
                                             for i, raw in fc.bad_raw))
            self.journal.forecast_status(phase, attempt,
                                         "invalid_final" if last else "invalid_retry")
            if last:
                if phase == "F1":
                    self.f1_status = "invalid_final"
                    self.f1_pred = {}
                else:
                    self.f3_status = "invalid_final"
                    self.f3_pred = {}
                self._write_forecasts()
                raise SessionHalt(f"invalid_final {phase}")

    def _write_history_shown(self):
        trials = [r.get("trial_id", f"t{i:02d}") for i, r in enumerate(self.history, 1)]
        self.journal.history_shown(self.seed, trials)

    def _f1(self):
        self._expect("F1")
        self._write_history_shown()
        self._forecast_phase("F1")
        self.phase = "F2"

    def _f3(self):
        self._forecast_phase("F3")
        self.phase = "F4"

    # --- F2 -------------------------------------------------------------------

    def _f2(self):
        self._expect("F2")
        while True:
            self._gate()
            if self.world.remaining <= 0:
                break                      # стоп-критерий F2: бюджет исчерпан
            if not self.world.e_set()["E"]:
                break                      # стоп-критерий F2: K достигнут
            ctx = self._context("F2")
            self.sent_contexts.append(ctx)
            text = self._call_agent("F2", ctx, 1)
            self._gate()                   # STOP до исполнения ответа
            scratch = copy.deepcopy(self.registry)
            v = validate_f2(text, scratch, known_trials=self.known_trials,
                            mode=self.mode, last_probe_cell=self.world.last_probe)
            if not v.full_parse_ok:
                self.invalid_f2 += 1
                if self.invalid_f2 >= self.max_invalid_f2:
                    raise SessionHalt("too_many_invalid_f2")
                continue                   # ход не засчитан; ни реестр, ни журнал не тронуты
            self.invalid_f2 = 0
            self.registry = scratch        # регистрации Q/H/V переносятся разом
            self._apply_f2_response(v)

            # --- v30 (ред.2): предохранитель цикла: K итераций без ПОЛЕЗНОГО
            # прогресса. Прогресс = записи журнала за вычетом action_rejected
            # (их счётчик — malformed, §7): повторяющиеся одинаковые отказы
            # действия НЕ сбрасывают предохранитель; любые иные записи — сбрасывают.
            _progress_now = self.journal.seq - self.malformed
            if text == self.last_response and _progress_now == self.last_progress:
                self.loop_streak += 1
            else:
                self.loop_streak = 0
            self.last_response = text
            self.last_progress = _progress_now
            if self.loop_streak >= self.LOOP_FUSE_K:
                raise SessionHalt("response_loop")
        self.phase = "F3"

    def _apply_f2_response(self, v):
        windows = collect_windows(v.parsed)
        starts = {w[0].index: w for w in windows}
        blockmap = {b.lines: b for b in v.blocks}
        notes_idx = {i for i, _ in v.notes}
        qh_fail_idx = {f["index"] for f in v.qh_failures}
        vf_fail_idx = {f["index"] for f in v.verdict_failures}
        vmap = {i: n for i, n in v.verdicts_committed}
        call_ref = f"{self.respond_calls:04d}_F2_a1"
        for f in v.qh_failures:         # N6 (A7): производный аудит отказов
            label = f"Q{f['n']}" if f["kind"] == "question" else f"H{f['n']}"
            self.rejection_audit.append({
                "line": f["index"], "phase": "F2", "kind": f["kind"],
                "label": label, "reason": f["reason"], "call": call_ref,
                "created": False})
        for f in v.qh_failures:         # v30: сообщения об отказах Q/H — агенту
            label = f"Q{f['n']}" if f["kind"] == "question" else f"H{f['n']}"
            self.rejections.append(
                {"requested": label, "reason": f["reason"],
                 "hint": qh_hint(f["kind"], f.get("reason", ""))})
        for f in v.verdict_failures:
            self.rejection_audit.append({
                "line": f["index"], "phase": "F2", "kind": "verdict",
                "label": None, "reason": f["reason"], "call": call_ref,
                "created": False})

        for line in v.parsed:
            i = line.index
            if i in starts:
                # оставшиеся блоки не исполняются при сработавших стопах F2
                if self.world.remaining <= 0 or not self.world.e_set()["E"]:
                    return
                self._gate()
                b = blockmap.get(tuple(l.index for l in starts[i]))
                if b is None:
                    continue
                if not b.ok:
                    self.journal.action_rejected(b.requested, b.reason,
                        distinguish_confirmed=b.distinguish_confirmed,
                        distinguish_ok=b.distinguish_ok)
                    self.rejections.append(
                        {"requested": b.requested, "reason": b.reason,
                         "hint": REJECTION_HINTS.get(b.reason, "")})
                    self.malformed += 1
                    continue
                self._execute_block(b)
                continue

            kind = line.kind
            if kind == "question" and i not in qh_fail_idx:
                self.journal.question(line.data["n"], line.data["text"], line.data["ref"])
            elif kind == "hypothesis" and i not in qh_fail_idx:
                self.journal.hypothesis(line.data["n"], line.data["q"], line.data["text"],
                                        line.data["cell"], line.data["prediction"])
            elif kind == "rejected":
                self.journal.rejected(line.data["h"], line.data["reason"])
            elif kind == "note" and i in notes_idx:
                self.journal.note(line.data["text"])
                self.notes.append(line.data["text"])   # M1: подаётся в след. вызовах
            elif kind == "verdict" and i not in vf_fail_idx:
                n = vmap.get(i)
                if n is not None:
                    self._record_verdict(line, n)

    def _record_verdict(self, line, n: int):
        h, res, p = line.data["h"], line.data["resolution"], line.data["after_p"]
        rec = self.journal.verdict(f"V{n}", h, res, p)   # метка присвоена валидатором (scratch-реестр)
        hv = self.registry.hypotheses[h]
        pv = self.registry.probes[p]
        # N1/N2 (A21/A18, дополнение №1 v1.0): проверка только по точной
        # клетке пробы; при отсутствии прогноза для этой клетки запись
        # verdict_check НЕ создаётся (аудит даст not_checked).
        if hv["cell"] == pv["cell"]:
            expected = "supported" if hv["prediction"] == pv["outcome"] else "refuted"
            value = "match" if res == expected else "mismatch"
            self.journal.verdict_check(value, rec["seq"])

    def _execute_block(self, b):
        plan = b.plan
        if plan.get("decision"):
            self.journal.decision(plan["decision"], plan["using_v"])
            self.decisions += 1                     # v35: принятое решение
        kind = plan["action"]
        if kind in ("probe", "repeat"):
            cell = plan["prediction"]["cell"]
            pre_seq = self.journal.prediction_pre(cell, plan["prediction"]["outcome"])
            n = self.registry.last["P"] + 1
            desc = f"probe {cell.as_text()}" if kind == "probe" else "repeat"
            ar = self.journal.action_requested(desc, prediction_ref=pre_seq,
                                               p_label=f"P{n}")
            r = self.world.probe(cell) if kind == "probe" else self.world.repeat()
            self.registry.commit_probe(r.cell, r.outcome, r.revealed)
            dst = plan.get("distinguish")
            self.journal.probe_outcome(r.cell, r.outcome, r.masked, r.revealed,
                                       distinguish_confirmed=(dst["confirmed"] if dst else None),
                                       distinguish_ok=(True if dst else None))
            if r.transition:
                self.journal.state_change(ar["seq"], changes=[
                    {"object_id": r.cell.object_id, "from": "present", "to": "disappeared"}])
            self.journal.budget(1, self.world.remaining, ar["seq"])
            if r.revealed:
                self.observations.append((r.cell, r.outcome))
        else:  # reset
            ar = self.journal.action_requested("reset", prediction_ref=None, p_label=None)
            r = self.world.reset()
            self.journal.state_change(ar["seq"], restored=list(r.restored))
            self.journal.budget(1, self.world.remaining, ar["seq"])

    # --- F4 / F5 --------------------------------------------------------------

    def _f4(self):
        self._expect("F4")
        self._gate()
        for attempt in (1, 2, 3):
            self._gate()
            ctx = self._context("F4")
            self.sent_contexts.append(ctx)
            text = self._call_agent("F4", ctx, attempt)
            for line in parse_response(text, phase="F4"):
                if line.kind == "final":
                    self.journal.final(line.data["text"])
                    self.final_present = True
                    self.phase = "F5"
                    return
        self.final_present = False      # фиксируется в derived/metrics.json
        self.phase = "F5"

    def _write_forecasts(self):
        if self._forecasts_written:
            return
        def pack(pred, status):
            if not pred:
                return {"status": status, "predictions": None}
            return {"status": status,
                    "predictions": {c.as_text(): y for c, y in sorted(pred.items())}}
        write_derived_once(self.run_dir, "forecasts.json",
                           {"F1": pack(self.f1_pred, self.f1_status or "not_run"),
                            "F3": pack(self.f3_pred, self.f3_status or "not_run")})
        self._forecasts_written = True

    def _write_rejections(self):
        """N6 (A7, дополнение №1 v1.0): производный аудит отказов Q/H/V."""
        if self._rejections_written:
            return
        write_derived_once(self.run_dir, "rejections.json", self.rejection_audit)
        self._rejections_written = True

    def _passport_payload(self, status: str) -> dict:
        art = {"heldout_battery.json": file_sha(ARTIFACTS / "heldout_battery.json"),
               f"history_{self.seed}.jsonl": file_sha(ARTIFACTS / f"history_{self.seed}.jsonl")}
        code_dir = Path(__file__).resolve().parent            # k0/code
        autonomy = code_dir.parent.parent                     # lab/autonomy
        driver = {name: file_sha(code_dir / name) for name in (
            "world.py", "parser.py", "journal.py", "auditor.py", "session.py",
            "calls.py", "channel.py", "prompts.py")}
        return {
            "series": "K0-M3", "seed": self.seed, "mode": self.mode,
            "status": status, "stop_reason": self.stop_reason,
            "respond_calls": self.respond_calls, "malformed": self.malformed,
            "n_E": (len(self.world.e_set()["E"]) if self.world is not None else None),
            "protocol_version": "v35",
            "protocol_sha256": file_sha(ARTIFACTS.parent / "K0_PROTOCOL_v35.md"),
            "protocol_base_sha256": file_sha(ARTIFACTS.parent / "K0_PROTOCOL.md"),
            "protocol_diff_sha256": file_sha(ARTIFACTS.parent / "version-history"
                                             / "K0_PROTOCOL_v34_to_v35.diff"),
            "spec_sha256": file_sha(autonomy / "WORLD_C_SPEC.md"),
            "package_sha256": file_sha(autonomy / "WORLD_C_DECISIONS_PACKAGE.md"),
            "prompts_sha256": file_sha(code_dir / "prompts.py"),
            "driver_sha256": driver,
            "t0_params": dict(T0_PARAMS),
            "limits": {"max_calls": self.max_calls, "max_seconds": self.max_seconds,
                       "max_total_tokens": self.max_total_tokens,
                       "max_prompt_tokens": self.max_prompt_tokens,
                       "require_token_counts": self.require_token_counts},
            "total_tokens": self.total_tokens,
            "context": {
                "approx_tokens_max": (max(self.context_approx)
                                      if self.context_approx else None),
                "approx_tokens_last": (self.context_approx[-1]
                                       if self.context_approx else None),
                "warn_threshold": self.CONTEXT_WARN_THRESHOLD,
                "warn_calls": list(self.context_warns),
            },
            "artifacts": art,
            "written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _f5(self):
        self._expect("F5")
        e_cells = list(self.world.e_set()["E"])
        write_derived_once(self.run_dir, "e_set.json", self.world.e_set_json())
        self._write_forecasts()
        self._write_rejections()
        has_preds = bool(self.f1_pred) and bool(self.f3_pred)
        if e_cells and has_preds:
            acc_b = accuracy(self.f1_pred, e_cells)
            acc_a = accuracy(self.f3_pred, e_cells)
            improvement = acc_a - acc_b
            o1 = o1_pass(acc_b, acc_a, len(e_cells))
        else:
            acc_b = acc_a = improvement = None
            o1 = False
        self.metrics = {"n_E": len(e_cells), "e_min_ok": len(e_cells) >= 6,
                        "acc_before": acc_b, "acc_after": acc_a,
                        "improvement": improvement, "o1_pass": o1,
                        "final_present": self.final_present,
                        "malformed": self.malformed,   # §7: = число action_rejected
                        "context_approx_max": (max(self.context_approx)
                                               if self.context_approx else None),
                        "context_warns": len(self.context_warns)}
        write_derived_once(self.run_dir, "metrics.json", self.metrics)
        self.audit_report = audit_run(self.run_dir)
        write_derived_once(self.run_dir, "audit.json", self.audit_report.as_dict())
        write_passport_once(self.run_dir, self._passport_payload("completed"))
