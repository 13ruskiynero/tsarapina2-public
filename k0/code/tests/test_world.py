#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Синтетические тесты мира K0 (§3/§5/§6/§9 замороженного протокола ред. 26).

Без вызовов модели. Запуск:
    python3 lab/autonomy/k0/code/tests/test_world.py -v
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

THIS = Path(__file__).resolve()
CODE_DIR = THIS.parents[1]        # .../k0/code
K0_DIR = THIS.parents[2]          # .../k0
sys.path.insert(0, str(CODE_DIR))

from world import (  # noqa: E402
    BUDGET_TOTAL, DISAPPEARED, HIDDEN_P, MATERIAL_M, OBJECTS,
    PRESENT, REVEALED, MASKED, BudgetExhausted, Cell, InvalidCell,
    NoLastProbe, World, accuracy, cell_outcome, load_battery, load_history,
    o1_pass,
)

ARTIFACTS = K0_DIR / "artifacts"


def battery_cells():
    return [item.cell for item in load_battery(ARTIFACTS / "heldout_battery.json")]


class TestRule(unittest.TestCase):
    """§3: правило `исчезновение ⟺ T=2 ∧ p=A` на всех 36 клетках."""

    def test_all_36_cells(self):
        for o in OBJECTS:
            for T in (0, 1, 2):
                for H in (0, 1, 2):
                    expected = DISAPPEARED if (T == 2 and HIDDEN_P[o] == "A") else PRESENT
                    self.assertEqual(cell_outcome(Cell(o, T, H)), expected,
                                     f"{o} T={T} H={H}")

    def test_cross_table_frozen(self):
        # Полная кросс-таблица p×m (замороженные значения, §3)
        self.assertEqual(tuple(MATERIAL_M[o] for o in OBJECTS), ("A", "A", "B", "B"))
        self.assertEqual(tuple(HIDDEN_P[o] for o in OBJECTS), ("A", "B", "A", "B"))


class TestCellParse(unittest.TestCase):
    """§7: строгий дескриптор клетки; квадратные скобки недопустимы."""

    def test_parse_ok(self):
        self.assertEqual(Cell.parse("O2 T=1 H=0"), Cell("O2", 1, 0))

    def test_parse_bad(self):
        bad = ["O5 T=2 H=0", "O1 T=3 H=0", "O1 t=2 H=0", "O1 T=2 H=0 DISTINGUISH: H1,H2",
               "O[1-4] T=[0-2] H=[0-2]", "O1  T=2  H=0", "O1 T=2"]
        for text in bad:
            with self.assertRaises(InvalidCell, msg=text):
                Cell.parse(text)


class TestBatteryArtifacts(unittest.TestCase):
    """§5/приложение B: батарея; скоринг воспроизводит контрольные числа."""

    def test_battery_shape(self):
        items = load_battery(ARTIFACTS / "heldout_battery.json")
        self.assertEqual(len(items), 9)
        ys = [i.y_expected for i in items]
        self.assertEqual(ys.count(DISAPPEARED), 4)
        self.assertEqual(ys.count(PRESENT), 5)

    def test_control_models_reproducible(self):
        # Скоринг «до/после» воспроизводит контрольные числа простых моделей
        # (чек-лист допуска, раздел A; приложение B). Контрольные числа
        # опубликованы с 3 знаками — сравнение через округление ОТОБРАЖЕНИЯ;
        # сами значения acc хранятся точными (без округления).
        cells = battery_cells()
        with open(ARTIFACTS / "control_models.json", encoding="utf-8") as f:
            cm = json.load(f)
        models = {
            "always_present": lambda c: PRESENT,
            "always_disappeared": lambda c: DISAPPEARED,
            "T2_rule": lambda c: DISAPPEARED if c.T == 2 else PRESENT,
            "m_rule_A_disappears": lambda c: DISAPPEARED if MATERIAL_M[c.object_id] == "A" else PRESENT,
            "object_O1_rule": lambda c: DISAPPEARED if c.object_id == "O1" else PRESENT,
            "reference_truth": lambda c: cell_outcome(c),
        }
        for name, fn in models.items():
            preds = {c: fn(c) for c in cells}
            self.assertEqual(round(accuracy(preds, cells), 3), cm[name], name)
        simple_max = max(v for k, v in cm.items() if k != "reference_truth")
        self.assertLessEqual(simple_max, 0.6)

    def test_accuracy_guards(self):
        with self.assertRaises(Exception):
            accuracy({}, [])
        with self.assertRaises(Exception):
            accuracy({Cell("O1", 2, 1): "maybe"}, [Cell("O1", 2, 1)])


class TestProbe(unittest.TestCase):
    """§3: механика проб, маска, переходы состояний."""

    def test_present_disappears(self):
        w = World()
        r = w.probe(Cell("O1", 2, 1))
        self.assertEqual(r.outcome, DISAPPEARED)
        self.assertTrue(r.revealed)
        self.assertFalse(r.masked)
        self.assertTrue(r.transition)
        self.assertEqual(w.state["O1"], DISAPPEARED)

    def test_present_stays_present(self):
        w = World()
        r = w.probe(Cell("O2", 2, 2))
        self.assertEqual(r.outcome, PRESENT)
        self.assertTrue(r.revealed)
        self.assertFalse(r.transition)
        self.assertEqual(w.state["O2"], PRESENT)

    def test_mask_after_disappearance(self):
        w = World()
        w.probe(Cell("O1", 2, 1))          # O1 → disappeared
        r = w.probe(Cell("O1", 0, 0))      # маска
        self.assertTrue(r.masked)
        self.assertFalse(r.revealed)
        self.assertEqual(r.outcome, DISAPPEARED)
        self.assertFalse(r.transition)
        self.assertEqual(w.state["O1"], DISAPPEARED)

    def test_probe_again_after_reset(self):
        w = World()
        w.probe(Cell("O1", 2, 1))
        rr = w.reset()
        self.assertEqual(rr.restored, ("O1",))
        r = w.probe(Cell("O1", 1, 0))
        self.assertEqual(r.outcome, PRESENT)
        self.assertTrue(r.revealed)


class TestRepeat(unittest.TestCase):
    """§3: repeat — новое исполнение последней пробы в текущем состоянии мира."""

    def test_repeat_requires_probe(self):
        with self.assertRaises(NoLastProbe):
            World().repeat()

    def test_repeat_after_reset_is_new_execution(self):
        # Пример §3: проба O1 при T=2 → disappeared; reset; repeat O1 T=2 —
        # новое исполнение: объект снова present, исход по правилу.
        w = World()
        w.probe(Cell("O1", 2, 1))
        w.reset()
        r = w.repeat()
        self.assertEqual(r.kind, "repeat")
        self.assertEqual(r.cell, Cell("O1", 2, 1))
        self.assertEqual(r.outcome, DISAPPEARED)
        self.assertTrue(r.transition)

    def test_repeat_masked_without_reset(self):
        w = World()
        w.probe(Cell("O1", 2, 1))
        r = w.repeat()
        self.assertTrue(r.masked)
        self.assertEqual(r.outcome, DISAPPEARED)
        self.assertEqual(w.state["O1"], DISAPPEARED)


class TestBudget(unittest.TestCase):
    """§3: бюджет B=16; цена 1 у probe/repeat/reset."""

    def test_sixteen_actions_then_exhausted(self):
        w = World()
        for i in range(BUDGET_TOTAL):
            w.probe(Cell("O4", 0, i % 3))
            self.assertEqual(w.remaining, BUDGET_TOTAL - (i + 1))
        self.assertEqual(w.remaining, 0)
        with self.assertRaises(BudgetExhausted):
            w.probe(Cell("O4", 0, 0))

    def test_reset_costs_budget(self):
        w = World()
        w.probe(Cell("O1", 2, 1))
        for _ in range(BUDGET_TOTAL - 2):
            w.probe(Cell("O4", 0, 0))
        self.assertEqual(w.remaining, 1)
        w.reset()
        self.assertEqual(w.remaining, 0)
        with self.assertRaises(BudgetExhausted):
            w.reset()
        self.assertEqual(w.remaining, 0)


class TestESet(unittest.TestCase):
    """§5: категории клеток; E = ненаблюдённые клетки батареи."""

    def setUp(self):
        self.battery = battery_cells()

    def test_all_untouched_without_probes(self):
        w = World(self.battery)
        es = w.e_set()
        self.assertEqual(len(es["E"]), 9)
        self.assertTrue(all(es["included_mask"].values()))
        self.assertEqual(es["exclude_reason"], {})

    def test_exclusion_reasons(self):
        w = World(self.battery)
        w.probe(Cell("O1", 2, 1))   # батарейная, revealed (O1 → disappeared)
        w.probe(Cell("O1", 1, 0))   # батарейная, masked (O1 disappeared)
        es = w.e_set()
        self.assertEqual(len(es["E"]), 7)
        self.assertEqual(es["exclude_reason"][Cell("O1", 2, 1)], REVEALED)
        self.assertEqual(es["exclude_reason"][Cell("O1", 1, 0)], MASKED)

    def test_revealed_priority_after_mixed_history(self):
        # Смешанная история клетки (masked → reset → revealed): по определениям
        # §5 итоговая причина — revealed_present («исход получен»).
        w = World(self.battery)
        w.probe(Cell("O1", 2, 1))   # O1 → disappeared
        w.probe(Cell("O1", 1, 0))   # masked
        self.assertEqual(w.touched_reason(Cell("O1", 1, 0)), MASKED)
        w.reset()                   # O1 снова present
        w.probe(Cell("O1", 1, 0))   # revealed
        self.assertEqual(w.touched_reason(Cell("O1", 1, 0)), REVEALED)
        self.assertEqual(w.e_set()["exclude_reason"][Cell("O1", 1, 0)], REVEALED)

    def test_non_battery_probes_do_not_touch_e(self):
        w = World(self.battery)
        w.probe(Cell("O2", 0, 0))
        w.probe(Cell("O4", 1, 1))
        self.assertEqual(len(w.e_set()["E"]), 9)

    def test_revealed_priority_when_masked_after(self):
        # N5 (A6, дополнение №1): исход получен хотя бы раз → revealed_present,
        # даже если позже клетка была маскирована
        w = World(self.battery)
        w.probe(Cell("O1", 1, 0))   # revealed
        w.probe(Cell("O1", 2, 1))   # O1 → disappeared (revealed)
        w.probe(Cell("O1", 1, 0))   # O1 disappeared → masked (позже)
        self.assertEqual(w.touched_reason(Cell("O1", 1, 0)), REVEALED)

    def test_k_analysis_scan_strategy(self):
        # §5: «систематический обход O1/O3 при T=2 задевает 4 батарейные
        # клетки → |E| ≤ 5»: проверяем буквально.
        w = World(self.battery)
        w.probe(Cell("O1", 2, 1))   # revealed
        w.probe(Cell("O3", 2, 0))   # revealed
        w.probe(Cell("O3", 2, 1))   # masked
        w.probe(Cell("O3", 2, 2))   # masked
        self.assertEqual(len(w.e_set()["E"]), 5)


class TestThresholds(unittest.TestCase):
    """§9: пороги O1; округление до сравнения не применяется."""

    def test_o1_pass_boundaries(self):
        self.assertTrue(o1_pass(0.444, 0.800, 9))     # ровно 0.80 — порог включительный
        self.assertFalse(o1_pass(0.444, 0.799, 9))
        self.assertTrue(o1_pass(0.500, 0.800, 9))     # Δ = ровно +0.30 — включительно
        self.assertFalse(o1_pass(0.501, 0.800, 9))    # Δ < 0.30
        self.assertFalse(o1_pass(0.444, 0.900, 5))    # |E| < 6
        self.assertTrue(o1_pass(0.444, 0.900, 6))

    def test_rounding_equivalence_on_real_fractions(self):
        # Для |E| ∈ 6..9 все возможные acc и Δacc — дроби k/n. Проверяем,
        # что округление до 3 знаков НЕ меняет булево решение порогов ни
        # на одной реальной дроби (запас до порогов ≫ 0.0005).
        for n in range(6, 10):
            fracs = [k / n for k in range(n + 1)]
            for v in fracs:
                self.assertEqual(v >= 0.80, round(v, 3) >= 0.80, (n, v))
            for a in fracs:
                for b in fracs:
                    d = a - b
                    if d >= 0:
                        self.assertEqual(d >= 0.30, round(d, 3) >= 0.30, (n, a, b))


class TestHistory(unittest.TestCase):
    """§4: стартовые истории; батарея из истории исключена."""

    def test_load_all_seeds(self):
        battery = set(battery_cells())
        for seed in (101, 202, 303):
            rows = load_history(ARTIFACTS / f"history_{seed}.jsonl")
            self.assertEqual(len(rows), 12)
            cells = set()
            for r in rows:
                self.assertEqual(r["origin"], "environment")
                self.assertEqual(r["m"], MATERIAL_M[r["object_id"]])
                self.assertIn(r["y"], (PRESENT, DISAPPEARED))
                cells.add(r["cell"])
            self.assertEqual(len(cells), 12)                 # без дубликатов (R2)
            self.assertEqual(cells & battery, set())         # без утечки батареи (R3)


class TestLeakageMechanics(unittest.TestCase):
    """§5: симуляция «до/после» без модели — контроль механики утечки.

    Полный путь данных F1 → F3 (парсинг прогнозов + журнал + сессия) —
    отдельный пункт допуска; он НЕ закрыт этим классом (см. отчёт).
    """

    def test_no_outcomes_before_any_probe(self):
        w = World(battery_cells())
        self.assertEqual(w.events, [])                       # событий нет
        self.assertTrue(all(v == PRESENT for v in w.state.values()))
        self.assertEqual(len(w.e_set()["E"]), 9)             # все батарейные нетронуты
        for cell in battery_cells():
            self.assertIsNone(w.touched_reason(cell))

    def test_probes_outside_battery_keep_e_intact(self):
        w = World(battery_cells())
        for cell in (Cell("O2", 0, 0), Cell("O4", 1, 1), Cell("O3", 1, 2)):
            w.probe(cell)
        for cell in battery_cells():
            self.assertIsNone(w.touched_reason(cell))
        self.assertEqual(len(w.e_set()["E"]), 9)

    def test_forecast_scoring_path(self):
        # Синтетический F1→F3 без модели: предсказания не меняются,
        # действия вне батареи не исключают клеток; acc считается на E.
        w = World(battery_cells())
        cells = battery_cells()
        preds = {c: PRESENT for c in cells}                  # синтетическая стратегия
        acc_before = accuracy(preds, w.e_set()["E"])
        w.probe(Cell("O2", 0, 0))
        w.probe(Cell("O4", 1, 1))
        acc_after = accuracy(preds, w.e_set()["E"])
        self.assertEqual(round(acc_before, 3), 0.556)
        self.assertEqual(round(acc_after, 3), 0.556)         # E не изменился


if __name__ == "__main__":
    unittest.main(verbosity=2)
