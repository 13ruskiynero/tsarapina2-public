#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — сохранение вызовов агента (`raw/calls/`) и паспорт прогона (`passport/`).

[v26] §11: «вызовы сохраняются в `raw/calls/` (сырые байты запросов и
ответов)»; каталог `passport/` входит в структуру прогона.
[RE] Формат (проект, к утверждению вместе с journal_schema.md):
- `raw/calls/<NNNN>_<phase>_a<attempt>.request.txt` — детерминированная
  сериализация контекста вызова (JSON, UTF-8);
- `raw/calls/<NNNN>_<phase>_a<attempt>.response.txt` — ответ агента
  (исходный текст, UTF-8, без изменений);
- `passport/passport.json` — идентификация прогона (серия, сид, режим,
  статус, хэши якорных артефактов); состав — проект (A25).
Запись: flush + fsync; файлы не перезаписываются.

Границы: модуль только фиксирует вызовы и паспорт; сеть/модель не
используются; журнал (`raw/journal.jsonl`) ведёт `journal.py`.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


class CallLogError(Exception):
    """Ошибка сохранения вызовов/паспорта."""


def file_sha(p) -> str:
    """SHA-256 фактического файла (для паспорта прогона)."""
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def render_context(ctx) -> str:
    """Детерминированная сериализация контекста вызова (для `raw/calls`)."""
    def hist_item(rec):
        d = {k: v for k, v in rec.items() if k != "cell"}
        if "cell" in rec:
            d["cell"] = rec["cell"].as_text()
        return d
    payload = {
        "phase": ctx.phase,
        "history": [hist_item(r) for r in ctx.history],
        "observations": [list(t) for t in ctx.observations],
        "rejections": [dict(r) for r in ctx.rejections],
        "budget_remaining": ctx.budget_remaining,
        "last_probe": ctx.last_probe,
        "last_labels": list(getattr(ctx, "last_labels", (0, 0, 0, 0))),
    }
    if ctx.phase == "F2":   # v32: вход секции «СЛЕДУЮЩИЙ ШАГ» — виден в артефакте
        payload["hypotheses"] = [dict(h) for h in getattr(ctx, "hypotheses", ())]
    if ctx.phase == "F1":   # v33: причина отказа F1 — виден в артефакте
        _f1r = getattr(ctx, "f1_rejection", ())
        if _f1r:
            payload["f1_rejection"] = list(_f1r)
    if ctx.phase == "F2":   # v34: шаг вердикта — виден в артефакте
        _vs = getattr(ctx, "verdict_step", ())
        if _vs:
            payload["verdict_step"] = list(_vs)
    return json.dumps(payload, ensure_ascii=False, indent=1)


class CallLog:
    """append-only сохранение пар запрос/ответ (`raw/calls/`)."""

    def __init__(self, run_dir):
        self.dir = Path(run_dir) / "raw" / "calls"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.n = 0

    def _write(self, name: str, text: str) -> Path:
        p = self.dir / name
        if p.exists():
            raise CallLogError(f"файл вызова уже существует: {p}")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        return p

    def request(self, phase: str, attempt: int, text: str) -> int:
        """Пишет запрос; возвращает номер вызова (для парного ответа)."""
        self.n += 1
        self._write(f"{self.n:04d}_{phase}_a{attempt}.request.txt", text)
        return self.n

    def response(self, n: int, phase: str, attempt: int, text: str) -> Path:
        """Пишет ответ (сырой текст агента)."""
        return self._write(f"{n:04d}_{phase}_a{attempt}.response.txt", text)

    def meta(self, n: int, phase: str, attempt: int, meta: dict) -> Path:
        """Метаданные попытки вызова (класс исхода O1; счётчики токенов).
        Ровно один файл на попытку; перезапись запрещена."""
        return self._write(f"{n:04d}_{phase}_a{attempt}.meta.json",
                           json.dumps(meta, ensure_ascii=False, indent=1))


def write_passport_once(run_dir, payload: dict) -> Path:
    """`passport/passport.json` — ровно один раз (tmp + rename)."""
    d = Path(run_dir) / "passport"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "passport.json"
    if p.exists():
        raise CallLogError(f"passport уже существует: {p}")
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)
    return p
