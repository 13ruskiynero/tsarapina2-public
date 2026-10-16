# A1 PRODUCTION TRANSFER: ОТЧЁТ (11.09.2026)

**Статус: PASS (с маркировкой; решение профессора 11.09).**

```
A1 production transfer
    ├── semantic equivalence       PASS
    ├── production gate            PASS
    ├── A1 regression              PASS
    ├── existing test suite        8/9 baseline-compatible
    └── EF-11                      OPEN / D-6 (defect isolated)
```

Решение: EF-11 принят как integration defect, вариант (a); **A1 не
откатывается**. Каноническая семантика этапа: «Knowledge without a
verified outcome is not an A1 candidate». Ярлык «v0.6.x+A1» —
условно зафиксирован (EF-11/D-6 вне scope переноса). Откат доступен
(baseline-копии зафиксированы).

## 1. Что сделано (процедура FROZEN, A1_PRODUCTION_TRANSFER_DESIGN.md)

```
Шаг 2  unchanged tests/: прогон ДО переноса зафиксирован
       (/tmp/tstar_before): 7/9 PASS; knowledge FAIL (K1a schema
       0.2 vs 0.3; K1c 9 vs 10 фактов), update FAIL (U3 schema
       0.2 vs 0.3) — устаревшие ожидания эпохи до v0.6.x; учтены
       как pre-existing.
Шаг 3  backup: strategy/strategy_v06x_baseline.py
       (sha 2040d495… = исходный strategy.py; не изменяется).
Шаг 4  перенос:
       S1 strategy.py: 3 ханка (шапка-пометка; хелпер
          _aa1_outcome_is_success + regex; фильтр строго ДО
          matching). diff baseline→new = ровно эти 3 ханка,
          ничего больше; кодовые блоки совпадают с strategy_aa.py
          (различия — только в текстах комментариев).
       S2 strategy/exclusion.py: механизм 1:1 из gate_module
          (FilteredStore + GateModule; API и имена сохранены;
          self.st = production strategy; единственное отличие —
          assert → ValueError: fail-closed работает и при -O).
       S3 конфиг: exclusion_semantics обязателен, дефолта нет;
          missing/HALT → ValueError (проверено).
       S4 Explore dispatch: внешний (pop_explore()), как в гейте.
       SHA: strategy.py 2040d495… → 6aac4725…; exclusion.py
       9d20a1de…; update/knowledge/storage/executor/evaluation/
       observer — НЕ менялись.
Шаг 5  tests/test_exclusion.py: 24/24 PASS (POOL; TEMP success/
       failure; empty pool; история/guards; FAIL CLOSED).
```

## 2. Production gate и сравнение (шаг 6-7)

```
Прогоны на production-модуле (gate_driver_prod.py; RAW —
GATE_A1_PROD_cell_*.json, 48 записей):
  механические клетки c1–c8: 30/30;
  R0 (S0..S5,S6b,P1,P2): 18/18; audit чистый во всех.
Сравнение exp ↔ prod (gate_a1_prod_compare.py; kid-нормализация;
fp: steps/events/slot_state/exclusions/guards/audit):
  совпало 30/30, расхождений 0;
  R0: 18 сверено; A1-authorized отличий — те же 4 (S5 w1/noise:
  old выбирал failure-derived K; A1 — S3); иных нет.
ВЕРДИКТ: ЭКВИВАЛЕНТНОСТЬ PASS.
```

## 3. EF-11 (integration defect; OPEN → D-6)

**Canonical statement (профессор, 11.09):**

> EF-11: The A1 integration exposes an existing production/test-path
> mismatch. `knowledge.create` permits manually constructed knowledge
> without verified outcome provenance, while A1 candidate selection
> requires outcome evidence. The production update path currently
> creates knowledge through `update.apply`, which supplies
> outcome-bearing context. Therefore the failing test exercises a
> legacy construction path not represented in the experimental A1
> corpus.

**Finding:**

> A1 faithful integration rejects outcome-unknown knowledge as a
> candidate. Resolving whether outcome-unknown legacy knowledge
> should ever be eligible is outside the A1 transfer scope and
> remains D-6.

**Решение (11.09):** вариант (a) — семантика сохранена; A1-фильтр
ради зелёного CI не меняется; `test_strategy` t1 помечен как
известный expected mismatch (EF-11); вопрос статуса outcome-unknown
knowledge выделен в D-6 (RESEARCH_DEBT.md).

Факты контекста: в экспериментальном контуре знания без
outcome-метки не встречались (все — через `update.apply`,
`update.py:343`); без метки знания создаются только вручную/в
тестах; буква experimental A1 = «не success ⇒ не кандидат».

## 4. Итоговое состояние

```
Слои: strategy.py + exclusion.py изменены (перенос применён);
      update/knowledge/storage/executor/evaluation/observer —
      не менялись; baseline-копии на месте (откат = копия).
Regression: observer/experience/executor/evaluation/aggregation/
      llm_adapter — как до переноса; knowledge/update — те же
      pre-existing падения (логи идентичны); strategy — EF-11
      (known expected mismatch, t1).
Гейт v0.6.x+A1: PASS (маркировка); EF-11 → D-6.
Далее (по слову): проектирование Strategy → LLM → Action.
```

## 5. Артефакты

```
strategy/exclusion.py, strategy/strategy.py (изм.),
strategy/strategy_v06x_baseline.py,
tests/test_exclusion.py,
experiments/integration_gate/gate_driver_prod.py,
gate_a1_prod_compare.py, GATE_A1_PROD_cell_*.json (48),
INTEGRATION_GATE_A1_PROD_COMPARE.txt,
experiments/A1_PRODUCTION_TRANSFER_DESIGN.md (FROZEN).
Спецификация не изменялась; experimental A1 не модифицировался.
```
