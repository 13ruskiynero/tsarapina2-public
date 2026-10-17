#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — журнал прогона (§11 замороженного протокола ред. 26): `raw/journal.jsonl`.

- append-only; flush + fsync после каждой записи; «ничто не перезаписывается»
  (повторное открытие непустого журнала — ошибка: новый прогон = новый
  каталог `run_<серия>_<сид>/`);
- каталоги прогона: `raw/`, `raw/calls/`, `derived/`, `passport/`;
  STOP-файл в корне прогона (`stop_requested`);
- типы записей и контракты — §7/§10/§11 (закрытый список §11); поля,
  помеченные допущениями A8/A9, см. `ASSUMPTIONS.md` (verdict_ref;
  форма state_change для переходов probe/repeat);
- контракты исполнений (§3/§11, ред. 23): каждое исполненное действие
  (`probe`/`repeat`/`reset`) — ровно одна запись `budget` (`cost=1`,
  `remaining`, `action_ref` = seq `action_requested` этого исполнения);
  `probe`/`repeat` дополнительно `probe_outcome` (поля DISTINGUISH — только
  при наличии поля в блоке); `reset` — `state_change` (`restored`).

Границы модуля: запись и чтение журнала. Очерёдность событий, присвоение
меток P/V и сочленение с миром — драйвер серии (следующий блок).
Вызовы модели и derived-метрики — отдельные блоки.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional, Sequence

from world import Cell

VALID_VERDICT_CHECK = ("match", "mismatch")
VALID_FORECAST_STATUS = ("ok", "invalid_retry", "invalid_final")

ORIGIN_RECORDS = ("question", "hypothesis", "rejected", "note", "action_requested",
                  "prediction_pre", "prediction_before", "prediction_after",
                  "verdict", "decision", "final")
FACT_RECORDS = ("history_shown", "probe_outcome", "budget", "stop", "state_change",
                "mode_violation", "verdict_check", "action_rejected", "forecast_status")


class JournalError(Exception):
    """Ошибка журнала (нарушение контракта или попытка перезаписи)."""


def run_dir_for(base, series: str, seed: int) -> Path:
    """Каталог прогона: `run_<серия>_<сид>/` (§11)."""
    return Path(base) / f"run_{series}_{seed}"


class Journal:
    """Append-only журнал прогона (raw/journal.jsonl)."""

    def __init__(self, run_dir):
        self.run_dir = Path(run_dir)
        self.raw_dir = self.run_dir / "raw"
        self.calls_dir = self.raw_dir / "calls"
        self.derived_dir = self.run_dir / "derived"
        self.passport_dir = self.run_dir / "passport"
        self.seq = 0
        self._fh = None

    @property
    def journal_path(self) -> Path:
        return self.raw_dir / "journal.jsonl"

    def open(self) -> "Journal":
        for d in (self.raw_dir, self.calls_dir, self.derived_dir, self.passport_dir):
            d.mkdir(parents=True, exist_ok=True)
        jp = self.journal_path
        if jp.exists() and jp.stat().st_size > 0:
            raise JournalError(f"журнал уже непуст (прогон не перезаписывается): {jp}")
        self._fh = open(jp, "a", encoding="utf-8")
        return self

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # --- базовая запись ------------------------------------------------------

    def _append(self, rtype: str, origin: str, label_by: str, **fields) -> dict:
        if self._fh is None:
            raise JournalError("журнал не открыт")
        self.seq += 1
        rec = {"seq": self.seq, "type": rtype, "origin": origin, "label_by": label_by}
        rec.update(fields)
        self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        return rec

    # --- origin-несущие записи (§11) ----------------------------------------

    def question(self, n: int, text: str, ref: str,
                 origin: str = "agent", label_by: str = "agent") -> dict:
        return self._append("question", origin, label_by,
                            label=f"Q{n}", text=text, ref=ref)

    def hypothesis(self, n: int, q: int, text: str, cell: Cell, prediction: str,
                   origin: str = "agent", label_by: str = "agent") -> dict:
        return self._append("hypothesis", origin, label_by, label=f"H{n}",
                            of=f"Q{q}", text=text, cell=cell.as_text(),
                            prediction=prediction)

    def rejected(self, h: int, reason_text: str, origin: str = "agent") -> dict:
        return self._append("rejected", origin, "none", h_label=f"H{h}",
                            reason=reason_text)

    def note(self, text: str) -> dict:
        return self._append("note", "agent", "none", text=text)

    def decision(self, descriptor: str, using_v: int) -> dict:
        return self._append("decision", "agent", "none",
                            descriptor=descriptor, using=f"V{using_v}")

    def final(self, text: str) -> dict:
        return self._append("final", "agent", "none", text=text)

    def prediction_pre(self, cell: Cell, outcome: str) -> int:
        """Предзапись F2 (§7.2). Возвращает seq — для `prediction_ref`."""
        rec = self._append("prediction_pre", "agent", "none",
                           cell=cell.as_text(), outcome=outcome)
        return rec["seq"]

    def prediction_before(self, cell: Cell, outcome: str) -> dict:
        return self._append("prediction_before", "agent", "none",
                            cell=cell.as_text(), outcome=outcome)

    def prediction_after(self, cell: Cell, outcome: str) -> dict:
        return self._append("prediction_after", "agent", "none",
                            cell=cell.as_text(), outcome=outcome)

    def action_requested(self, descriptor: str, prediction_ref: Optional[int] = None,
                         p_label: Optional[str] = None, origin: str = "agent") -> dict:
        """Исполненное действие (§7/§3). Для `probe`/`repeat` — метка `P<n>`
        (label_by=driver); для `reset` — без метки (label_by=none).
        `prediction_ref` — seq `prediction_pre` этого исполнения."""
        label_by = "driver" if p_label else "none"
        fields = {"label": p_label, "descriptor": descriptor}
        if prediction_ref is not None:
            fields["prediction_ref"] = prediction_ref
        return self._append("action_requested", origin, label_by, **fields)

    def verdict(self, v_label: str, h: int, resolution: str, after_p: int,
                origin: str = "agent") -> dict:
        return self._append("verdict", origin, "driver", label=v_label,
                            h_label=f"H{h}", resolution=resolution,
                            after=f"P{after_p}")

    # --- записи-факты и механические записи (§11; origin=none) ---------------

    def history_shown(self, seed: int, trials: Sequence[str]) -> dict:
        return self._append("history_shown", "none", "none",
                            seed=seed, trials=list(trials))

    def probe_outcome(self, cell: Cell, outcome: str, masked: bool, revealed: bool,
                      distinguish_confirmed: Optional[Sequence[str]] = None,
                      distinguish_ok: Optional[bool] = None) -> dict:
        fields = {"cell": cell.as_text(), "outcome": outcome,
                  "masked": bool(masked), "revealed": bool(revealed)}
        if distinguish_ok is not None:
            fields["distinguish_confirmed"] = list(distinguish_confirmed or [])
            fields["distinguish_ok"] = bool(distinguish_ok)
        return self._append("probe_outcome", "none", "none", **fields)

    def budget(self, cost: int, remaining: int, action_ref: int) -> dict:
        return self._append("budget", "none", "none",
                            cost=cost, remaining=remaining, action_ref=action_ref)

    def state_change(self, action_ref: int,
                     restored: Optional[Iterable[str]] = None,
                     changes: Optional[Sequence[dict]] = None) -> dict:
        """Изменения состояний (§7; форма `changes` — допущение A8)."""
        fields = {"action_ref": action_ref}
        if restored is not None:
            fields["restored"] = list(restored)
        if changes is not None:
            fields["changes"] = list(changes)
        return self._append("state_change", "none", "none", **fields)

    def mode_violation(self, kind: str, index: int, reason: str = "invalid_mode") -> dict:
        return self._append("mode_violation", "none", "none",
                            reason=reason, kind=kind, line=index)

    def verdict_check(self, value: str, verdict_ref: int) -> dict:
        """Обязательная проверка при каждом валидном вердикте (§7/§11);
        `verdict_ref` — seq записи вердикта (допущение A9)."""
        if value not in VALID_VERDICT_CHECK:
            raise JournalError(f"verdict_check: недопустимое значение {value!r}")
        return self._append("verdict_check", "none", "none",
                            value=value, verdict_ref=verdict_ref)

    def action_rejected(self, requested: Optional[str], reason: str,
                        distinguish_confirmed: Optional[Sequence[str]] = None,
                        distinguish_ok: Optional[bool] = None) -> dict:
        fields = {"requested": requested, "reason": reason}
        if reason == "distinguish_failed":
            fields["distinguish_confirmed"] = list(distinguish_confirmed or [])
            fields["distinguish_ok"] = bool(distinguish_ok) if distinguish_ok is not None else False
        return self._append("action_rejected", "none", "none", **fields)

    def forecast_status(self, phase: str, attempt: int, status: str) -> dict:
        if status not in VALID_FORECAST_STATUS:
            raise JournalError(f"forecast_status: недопустимый статус {status!r}")
        return self._append("forecast_status", "none", "none",
                            phase=phase, attempt=attempt, status=status)

    def stop(self, reason: str) -> dict:
        return self._append("stop", "none", "none", reason=reason)


# --- чтение и derived --------------------------------------------------------

def read_journal(path) -> list:
    """Читает журнал; проверяет строгую последовательность `seq` (1..N).

    Повреждённая/частично записанная строка — явная ошибка (`JournalError`);
    журнал не «исправляется» и не пропускается молча (§11: ничто не
    перезаписывается; нарушение инварианта останавливает обработку).
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                raise JournalError(f"повреждённая запись {n} (не JSON): {e}") from e
            if not isinstance(rec, dict) or "seq" not in rec or "type" not in rec:
                raise JournalError(f"запись {n}: нет обязательных полей seq/type")
            if rec["seq"] != len(rows) + 1:
                raise JournalError(f"нарушение seq в строке {n}: {rec.get('seq')}")
            rows.append(rec)
    return rows


def write_derived_once(run_dir, name: str, obj) -> Path:
    """Запись `derived/<name>` ровно один раз (ничто не перезаписывается);
    запись атомарная (tmp + rename)."""
    p = Path(run_dir) / "derived" / name
    if p.exists():
        raise JournalError(f"derived уже существует (не перезаписывается): {p}")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return p


def stop_requested(run_dir) -> bool:
    """STOP-файл оператора (§11)."""
    return (Path(run_dir) / "STOP").exists()
