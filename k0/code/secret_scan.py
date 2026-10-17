#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — сканирование артефактов на утечки секретов (этап подготовки, офлайн).

По условиям акта `K0_LIVE_CHANNEL_PREP_ACT.md` (§3.2): скан проверяет не
только точное совпадение секрета, но и формы его представления; скан —
НЕ единственная защита (дополнительно проверяются исключения,
диагностические сообщения и аварийные пути — см. `scan_text` на строках
исключений в тестах).

Формы (для строковых секретов):
  exact       — как есть;
  lower       — в нижнем регистре (поиск регистронезависимый);
  hex         — hex-кодирование байтов;
  b64         — base64 (standard);
  b64url      — base64 urlsafe без padding;
  json        — JSON-экранированная форма (без внешних кавычек);
  url         — percent-encoding (quote, safe="").

Поиск каждой формы выполняется и в исходном, и в нижнем регистре
проверяемого текста (для hex/base64 даёт регистронезависимость).
Секреты короче 4 символов отвергаются (`ValueError`) — скан такого
«секрета» бессмыслен (ложные срабатывания).
"""
from __future__ import annotations

import base64
import binascii
import json
import urllib.parse
from pathlib import Path
from typing import Iterable, Optional, Sequence

MIN_SECRET_LEN = 4


def secret_forms(secret: str) -> dict:
    """Формы представления секрета: имя → строка (только непустые/различные)."""
    if not isinstance(secret, str) or len(secret) < MIN_SECRET_LEN:
        raise ValueError(f"секрет короче {MIN_SECRET_LEN} символов: скан отклонён")
    raw = secret.encode("utf-8")
    forms = {
        "exact": secret,
        "hex": binascii.hexlify(raw).decode("ascii"),
        "b64": base64.b64encode(raw).decode("ascii"),
        "b64url": base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="),
        "json": json.dumps(secret)[1:-1],
        "url": urllib.parse.quote(secret, safe=""),
    }
    out = {}
    for name, value in forms.items():
        if value and value.lower() not in {v.lower() for v in out.values()}:
            out[name] = value
    out["lower"] = secret.lower()
    return {k: v for k, v in out.items() if v}


def scan_text(text: str, secret: str) -> list:
    """Имена форм секрета, найденных в тексте (регистронезависимо)."""
    forms = secret_forms(secret)
    hay_lower = text.lower()
    hay = text
    hits = []
    for name, value in forms.items():
        if value in hay or value.lower() in hay_lower:
            hits.append(name)
    return hits


def scan_bytes(data: bytes, secret: str) -> list:
    """То же для байтовых данных (артефакты читаются как bytes)."""
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return scan_text(text, secret)


def scan_file(path, secret: str, max_bytes: Optional[int] = None) -> list:
    """Формы секрета в одном файле (пусто — чисто)."""
    data = Path(path).read_bytes()
    if max_bytes is not None:
        data = data[:max_bytes]
    return scan_bytes(data, secret)


def scan_tree(root, secret: str, max_bytes_per_file: Optional[int] = None) -> list:
    """Рекурсивный скан каталога: [{path, forms}]; пусто — чисто."""
    findings = []
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        forms = scan_file(p, secret, max_bytes=max_bytes_per_file)
        if forms:
            findings.append({"path": str(p), "forms": forms})
    return findings


def scan_exceptions(exceptions: Iterable[BaseException], secret: str) -> list:
    """Скан аварийных путей: строковые представления исключений
    (type, str, repr) на формы секрета; пусто — чисто."""
    findings = []
    for e in exceptions:
        text = f"{type(e).__name__}: {e!s}\n{e!r}"
        forms = scan_text(text, secret)
        if forms:
            findings.append({"exception": type(e).__name__, "forms": forms})
    return findings
