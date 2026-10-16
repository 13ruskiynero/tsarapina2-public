# A1 PRODUCTION TRANSFER: СПЕЦИФИКАЦИЯ (FROZEN 11.09.2026)

**Статус: FROZEN.** Решения по всем пяти точкам внесены (слово
профессора, 11.09); scope не расширен. Операция: первый перенос
исследованного механизма в production-код Царапины. База:
INTEGRATION_GATE_REPORT.md (A1 Gate PASS, 48 прогонов; experimental
module).

**Принцип (FREEZE):**

> **Production transfer must preserve the experimental A1 semantics
> exactly. It must not improve, simplify, generalize, or reinterpret
> them.**

Плюс унаследованные инварианты гейта: No-new-policy +
No-implicit-extension (любое поведение, нужное реализации, но не
установленное замороженными экспериментами = integration defect /
новый research debt).

## 1. Scope: что переносится (FROZEN)

```
S1  A1-фильтр candidate addressing (failure-derived вне выбора):
    strategy/strategy.py — хелпер + фильтр строго ДО matching
    (точно как в strategy_aa.py; ханки сверяются diff'ом).
S2  Exclusion-механизм: strategy/exclusion.py — перенос ТОЛЬКО
    механизма из gate_module (FilteredStore + GateModule) с
    сохранением API: exclude / eligible_pool / decide / on_episode /
    attempt_needed / process_attempt / pop_explore; events + guards.
    Экспериментальная обвязка (driver/analyzer/records) НЕ
    переносится. Импорт strategy — из strategy-пакета.
S3  Конфиг: exclusion_semantics ∈ {POOL, TEMP} — обязательный
    параметр; дефолта НЕТ; missing → FAIL CLOSED.
S4  S3 → Explore dispatch: внешний (pop_explore()). Модуль сам
    действий не генерирует; exclusion сам Explore не вызывает.
```

## 2. Что НЕ входит (подтверждено; появление = defect/debt)

```
N1  Персистентность exclusion-state между рестартами процесса
    (переносим: exclusion/eligibility/POOL/TEMP/slot/attempt/
    eligible↔excluded transitions/guards/append-only events;
    НЕ решаем: где состояние переживает рестарт).
N2  Выбор/дефолт semantics (winner не определён; дефолт запрещён).
N3  LLM-канал Strategy → LLM → Action (отдельная операция; тест
    T7 «strategy не импортирует llm» эволюционирует тогда же).
N4  Долгоживущие прогоны и метрики.
N5  Любые улучшения/обобщения кода вне S1–S4.
```

## 3. Изменения файлов (FROZEN; ничего больше)

```
strategy/strategy.py           +хелпер +фильтр (малый diff)
strategy/exclusion.py          новый (механизм gate_module)
tests/test_exclusion.py        новый (юниты; §5)
strategy/strategy_v06x_baseline.py  ОБЯЗАТЕЛЬНАЯ backup-копия ДО
                               изменения; baseline НЕ изменяется
                               во время переноса; откат =
                               восстановление зафиксированных
                               файлов (не «примерно как было»)
experiments/gate_driver_prod.py     драйвер гейта против
                               production-модуля (experimental
                               gate_driver/RAW не трогаются)
update/knowledge/storage/executor/evaluation/observer — НЕ меняются.
```

## 4. Процедура (FROZEN)

```
1. FREEZE (этот файл).
2. unchanged tests/: весь набор tests/ на НЕизменённых слоях →
   зафиксировать результат (база сравнения).
3. backup: strategy_v06x_baseline.py (до любого изменения).
4. production transfer: S1–S4; SHA слоёв до/после; обзор diff
   («менялось только необходимое»; ханки S1 сверяются против
   strategy_aa.py).
5. tests: tests/test_exclusion.py + весь набор.
6. production GATE: R0 (18), R1 (8), полный механический гейт
   (30 клеток, G1–G10) на production implementation.
7. compare experimental ↔ production: структурные fingerprints
   (steps/events/guards/audit/slot_state нормализованный) —
   совпадение при kid-нормализации; расхождения классифицируются
   (kid-шум vs новое поведение).
PASS = конъюнкция strict (как в гейте) + эквивалентность exp/prod.
```

## 5. tests/test_exclusion.py (FROZEN; четыре механические границы)

```
5.1 POOL
    - excluded K отсутствует в eligible pool;
    - sibling eligible остаётся доступен.
5.2 TEMP
    - exclusion → sign-of-life → slot → attempt;
    - success → eligible;
    - non-success → остаётся excluded;
    - второй автоматический slot не появляется.
5.3 Empty pool
    - отсутствие eligible candidate обнаруживается;
    - сам exclusion НЕ вызывает Explore;
    - Explore dispatch — только через внешний S3 path.
5.4 История / guards
    - K record не мутируется;
    - события append-only;
    - запрещённый K не возвращается в selection;
    - provenance/lineage не теряются.
5.5 FAIL CLOSED
    - missing exclusion_semantics → FAIL (обязательный тест).
Больше тестов не добавляется (решение профессора).
```

## 6. Решения по пяти точкам (FROZEN, 11.09)

```
1. Раскладка: strategy/exclusion.py (не отдельный permissions/;
   общий permission framework преждевременен; переносится
   конкретно exclusion-механизм A1; API experimental сохраняется;
   экспериментальная обвязка не переносится).
2. Конфиг: обязательный параметр, без дефолта; отсутствие →
   ERROR (FAIL CLOSED). Нет исследовательского основания выбирать
   default; production-код не превращает отсутствие решения в
   решение (POOL и TEMP обе sufficient; winner не определён).
3. Персистентность: вне scope (см. N1); отдельный вопрос.
4. Откат: backup-копии (git отсутствует); порядок
   baseline backup → tests/ → transfer → gate; baseline
   неизменяем на время переноса; откат — восстановлением
   зафиксированных файлов.
5. Юнит-тесты: §5.1–5.5 (четыре границы + FAIL CLOSED);
   достаточны; расширение не требуется.
```

## 7. Итог и номенклатура

```
PASS → «v0.6.x+A1» (первое production-изменение);
       INTEGRATION_GATE_A1_PROD_REPORT.md;
       RESEARCH_DEBT: D-5 → «A1 in production»;
далее, только после этого (по слову) — шаг №2:
Strategy → LLM → Action.
Слои вне §3 не изменяются. Experimental A1 остаётся
референсом сравнения и не модифицируется.
```
