#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K0 — мир FULL (компонент драйвера; замороженный протокол ред. 26).

Строго по замороженному `K0_PROTOCOL.md` (ред. 26, sha256 `3d2ab37d…893b`):

- §3  Мир FULL: объекты O1–O4; видимый материал m; скрытый признак p;
       правило исходов `исчезновение ⟺ T=2 ∧ p=A`; ε=0; действия
       `probe`/`repeat`/`reset` по цене 1; бюджет `B=16`; состояние объекта
       `present`/`disappeared`; механика маски; раскрытие клетки; контракт
       `repeat` (новое исполнение последней пробы в текущем состоянии мира).
- §5  Батарея (9 клеток) и набор E: раскрытая / маскированная / не тронутая;
       E = ненаблюдённые клетки батареи; причины исключения
       `revealed_present` / `masked_disappeared`.
- §6  К началу F1 мир сброшен (все объекты `present`).

Границы модуля (первый блок работ): ТОЛЬКО механика мира и бюджет.
Парсер грамматики, аудитор S1–S6, журнал прогона (`raw/journal.jsonl`),
сборка контекста и вызовы модели — отдельные компоненты (следующие блоки).

Модуль детерминирован; сеть не используется; файлы артефактов не
изменяются (функции `load_*` — только чтение).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

# --- Константы мира (§3; заморожены) ---------------------------------------

OBJECTS = ("O1", "O2", "O3", "O4")

#: Видимый материал m (наблюдаемое свойство).
MATERIAL_M = {"O1": "A", "O2": "A", "O3": "B", "O4": "B"}

#: Скрытый признак p (полная кросс-таблица p×m).
HIDDEN_P = {"O1": "A", "O2": "B", "O3": "A", "O4": "B"}

#: Бюджет прогона (§3, решение 3).
BUDGET_TOTAL = 16

#: Цена каждого расходующего действия (§3; ред. 15).
ACTION_COST = 1

PRESENT = "present"
DISAPPEARED = "disappeared"

#: Категории исключения клеток батареи из E (§5).
REVEALED = "revealed_present"
MASKED = "masked_disappeared"


class WorldError(Exception):
    """Базовая ошибка механики мира."""


class InvalidCell(WorldError):
    """Клетка вне допустимых значений (o, T, H) (§3)."""


class BudgetExhausted(WorldError):
    """Бюджет исчерпан: расходующее действие невозможно (§3/§12)."""


class NoLastProbe(WorldError):
    """`repeat` без предшествующей оцениваемой пробы (§3)."""


_CELL_RE = re.compile(r"(O[1-4]) T=([0-2]) H=([0-2])")


@dataclass(frozen=True, order=True)
class Cell:
    """Клетка мира (o, T, H); идентифицируется тройкой (§3)."""

    object_id: str
    T: int
    H: int

    def __post_init__(self):
        if self.object_id not in OBJECTS:
            raise InvalidCell(f"объект вне O1..O4: {self.object_id!r}")
        if self.T not in (0, 1, 2):
            raise InvalidCell(f"T вне 0..2: {self.T!r}")
        if self.H not in (0, 1, 2):
            raise InvalidCell(f"H вне 0..2: {self.H!r}")

    def as_text(self) -> str:
        return f"{self.object_id} T={self.T} H={self.H}"

    @classmethod
    def parse(cls, text: str) -> "Cell":
        """Строгий разбор дескриптора клетки, например `O2 T=1 H=0` (§7).

        Квадратные скобки (мета-обозначение диапазонов) в тексте недопустимы.
        """
        m = _CELL_RE.fullmatch(text.strip())
        if not m:
            raise InvalidCell(f"дескриптор клетки не распознан: {text!r}")
        return cls(m.group(1), int(m.group(2)), int(m.group(3)))


def rule_outcome(object_id: str, T: int, H: int) -> str:
    """Правило мира (§3): объект исчезает ⟺ `T=2 ∧ p=A`; H на исход не влияет."""
    if object_id not in OBJECTS:
        raise InvalidCell(f"объект вне O1..O4: {object_id!r}")
    if T not in (0, 1, 2) or H not in (0, 1, 2):
        raise InvalidCell(f"T/H вне 0..2: T={T!r}, H={H!r}")
    return DISAPPEARED if (T == 2 and HIDDEN_P[object_id] == "A") else PRESENT


def cell_outcome(cell: Cell) -> str:
    """Исход клетки по правилу (для скоринга; агенту напрямую не выдаётся)."""
    return rule_outcome(cell.object_id, cell.T, cell.H)


@dataclass(frozen=True)
class ProbeResult:
    """Результат исполнения пробы (`probe` или `repeat`; §3)."""

    kind: str          # "probe" | "repeat"
    cell: Cell
    outcome: str       # сообщённый исход: "present" | "disappeared"
    masked: bool       # True ⟺ объект был `disappeared` (маска; клетка не раскрыта)
    revealed: bool     # True ⟺ объект был `present` (исход клетки получен)
    transition: bool   # True ⟺ объект перешёл present→disappeared этим исполнением
    remaining: int     # остаток бюджета после списания


@dataclass(frozen=True)
class ResetResult:
    """Результат `reset` (§3)."""

    restored: tuple    # объекты, переведённые disappeared→present (порядок O1..O4)
    remaining: int


class World:
    """Мир FULL: состояние объектов, действия, бюджет, учёт клеток для E (§3/§5/§6)."""

    def __init__(self, battery: Optional[Iterable[Cell]] = None):
        self.battery = tuple(battery) if battery is not None else ()
        self.state = {o: PRESENT for o in OBJECTS}   # §6: к началу F1 мир сброшен
        self.remaining = BUDGET_TOTAL
        self.last_probe: Optional[Cell] = None       # последняя оцениваемая проба (для repeat)
        self._touched = {}                           # Cell → REVEALED | MASKED
        self.events = []                             # минимальный внутренний лог событий

    # --- наблюдение ---------------------------------------------------------

    def snapshot(self) -> dict:
        """Снимок состояний объектов (для отчётов/тестов)."""
        return dict(self.state)

    def touched_reason(self, cell: Cell) -> Optional[str]:
        """Причина затронутости клетки (`revealed_present`/`masked_disappeared`) или None."""
        return self._touched.get(cell)

    # --- бюджет (§3) ---------------------------------------------------------

    def _spend(self) -> int:
        if self.remaining < ACTION_COST:
            raise BudgetExhausted(f"бюджет исчерпан (остаток {self.remaining})")
        self.remaining -= ACTION_COST
        return self.remaining

    # --- действия (§3) -------------------------------------------------------

    def _execute_probe(self, cell: Cell, kind: str) -> ProbeResult:
        was = self.state[cell.object_id]
        if was == PRESENT:
            out = cell_outcome(cell)
            transition = (out == DISAPPEARED)
            if transition:
                self.state[cell.object_id] = DISAPPEARED
            revealed, masked = True, False
            # Приоритет раскрытия (следствие определений §5): «раскрытая» = «исход
            # клетки получен»; «маскированная» = «исход НЕ получен». Если клетка
            # была маскирована, а затем раскрыта (после reset), итог — revealed_present.
            self._touched[cell] = REVEALED
        else:
            out = DISAPPEARED               # маска: состояние не меняется (§3)
            transition = False
            revealed, masked = False, True
            self._touched.setdefault(cell, MASKED)
        res = ProbeResult(kind=kind, cell=cell, outcome=out, masked=masked,
                          revealed=revealed, transition=transition,
                          remaining=self.remaining)
        self.events.append({"event": kind, "cell": cell.as_text(),
                            "outcome": out, "masked": masked,
                            "revealed": revealed, "transition": transition,
                            "remaining": self.remaining})
        return res

    def probe(self, cell: Cell) -> ProbeResult:
        """`probe(o,T,H)`: исполнение пробы (§3).

        Проверка предзаписи `PREDICT` — обязанность F2-слоя (§7.2); здесь —
        только механика мира и бюджет.
        """
        self._spend()
        self.last_probe = cell
        return self._execute_probe(cell, kind="probe")

    def repeat(self) -> ProbeResult:
        """`repeat`: новое исполнение последней оцениваемой пробы в ТЕКУЩЕМ
        состоянии мира (§3; не воспроизведение прошлого исхода)."""
        if self.last_probe is None:
            raise NoLastProbe("repeat допустим только после ≥1 оцениваемой пробы")
        self._spend()
        return self._execute_probe(self.last_probe, kind="repeat")

    def reset(self) -> ResetResult:
        """`reset`: возвращает все `disappeared`→`present`; цена 1; допустим
        всегда (§3). `last_probe` сохраняется (repeat допустим после reset)."""
        self._spend()
        restored = tuple(o for o in OBJECTS if self.state[o] == DISAPPEARED)
        for o in restored:
            self.state[o] = PRESENT
        res = ResetResult(restored=restored, remaining=self.remaining)
        self.events.append({"event": "reset", "restored": list(restored),
                            "remaining": self.remaining})
        return res

    # --- набор E (§5) --------------------------------------------------------

    def e_set(self) -> dict:
        """Набор E (§5) в виде Python-структур: B, E, маска включения, причины."""
        included = [c for c in self.battery if c not in self._touched]
        mask = {c: (c not in self._touched) for c in self.battery}
        excluded = {c: self._touched[c] for c in self.battery if c in self._touched}
        return {"B": list(self.battery), "E": included,
                "included_mask": mask, "exclude_reason": excluded}

    def e_set_json(self) -> dict:
        """Набор E в виде, готовом для `derived/e_set.json` (строковые ключи)."""
        es = self.e_set()
        return {
            "B": [c.as_text() for c in es["B"]],
            "E": [c.as_text() for c in es["E"]],
            "included_mask": {c.as_text(): v for c, v in es["included_mask"].items()},
            "exclude_reason": {c.as_text(): r for c, r in es["exclude_reason"].items()},
        }


# --- Скоринг (§9: acc на наборе клеток) -------------------------------------

def accuracy(predictions: Mapping[Cell, str], cells: Sequence[Cell]) -> float:
    """`acc` на наборе клеток (§9): доля совпадений с исходом по правилу.

    В v26 округление `acc` не предписано; пороги §9 сравниваются с долями.
    Функция возвращает ТОЧНУЮ долю, без округления — сравнение выполняется
    до любой нормализации; округление до 3 знаков — только отображение
    (так опубликованы контрольные числа дизайн-валидации, приложение B).
    """
    cells = list(cells)
    if not cells:
        raise WorldError("accuracy: пустой набор клеток")
    ok = 0
    for c in cells:
        p = predictions.get(c)
        if p not in (PRESENT, DISAPPEARED):
            raise WorldError(f"accuracy: невалидное предсказание для {c.as_text()}: {p!r}")
        if p == cell_outcome(c):
            ok += 1
    return ok / len(cells)


def o1_pass(acc_before: float, acc_after: float, n_e: int) -> bool:
    """Критерий O1 (§9): `acc_after ≥ 0.80` И `acc_after − acc_before ≥ +0.30`
    И `|E| ≥ 6`. Сравнения — точные (без округления значений)."""
    return (n_e >= 6) and (acc_after >= 0.80) and ((acc_after - acc_before) >= 0.30)


# --- Чтение замороженных артефактов (только чтение) -------------------------

@dataclass(frozen=True)
class BatteryItem:
    cell: Cell
    y_expected: str


def load_battery(path) -> tuple:
    """Читает `heldout_battery.json`; проверяет согласованность с правилом (§5)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    items = []
    for row in data["battery"]:
        cell = Cell(row["object_id"], row["T"], row["H"])
        y = row["y_expected"]
        if y != cell_outcome(cell):
            raise WorldError(f"батарея расходится с правилом в {cell.as_text()}: {y!r}")
        items.append(BatteryItem(cell, y))
    if data.get("n") != len(items):
        raise WorldError(f"heldout_battery.json: n={data.get('n')} != клеток {len(items)}")
    return tuple(items)


def load_history(path) -> tuple:
    """Читает стартовую историю (`history_<seed>.jsonl`; только чтение).

    Проверяет: 12 записей; поля наблюдения; исходы соответствуют правилу.
    """
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            cell = Cell(r["object_id"], r["T"], r["H"])
            if r["y"] != cell_outcome(cell):
                raise WorldError(f"история, строка {n}: y={r['y']!r} расходится с правилом")
            rows.append({**r, "cell": cell})
    if len(rows) != 12:
        raise WorldError(f"история: ожидается 12 записей, получено {len(rows)}")
    return tuple(rows)
