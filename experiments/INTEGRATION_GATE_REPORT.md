# TSARAPINA INTEGRATION GATE A1: ОТЧЁТ (10.09.2026)

**Статус: PASS.** Конъюнкция strict: G1–G10 ∧ guards ∧ audit ∧
L6=0 ∧ append-only ∧ regression (R0) ∧ детерминизм ∧ R≡S — все
выполнены. Планировка: INTEGRATION_GATE_A1_DESIGN.md (FROZEN;
No-new-policy + No-implicit-extension). Код: experiments/
integration_gate/ (experimental module; слои v0.6.x не изменялись —
audit 48/48).

## 1. Числа

```
Механические клетки (c1..c8): 30 прогонов
  c1  addressing (N1D, без прав)              2×r
  c2  POOL  E6N (G2/G3/G8)                    4×r ×R/S ×2 права
  c3  TEMP  E6N success-цикл (G4)             4
  c4  TEMP  TempF failure-ветка (G5)          4
  c5  POOL  SD empty→S3→Explore (G6)          4
  c6  TEMP  N6bV3 (G7: explore без slot)      4
  c7  POOL  SD4 (R1)                          4
  c8  POOL  S6bV3 (R1)                        4
R0 anchor (S0..S5,S6b,P1,P2): 18 прогонов
ИТОГО: 48 прогонов; r1/r2 везде; R/S раздельно везде
Determinism: r1≡r2 OK (все пары); R≡S: расхождений нет
```

## 2. Результаты G1–G10

```
G1  Addressing: failure-derived не выбирается; refs[0] — только
    success-знания (c1, обе реплики). PASS
G2  R/S-объект: право применяется к K той же линии; R/S-ветки
    неразличимы по исходу (c2/c7/c8, 12 клеток). PASS
G3  POOL: excluded K невидим для selection (в т.ч. injection-
    проверки); sibling продолжает работать (c2: 3×S2, sibling
    выбирается, excluded в refs после триггера отсутствует). PASS
G4  TEMP slot: exclusion→sol(K′)→slot(K)→attempt→eligible(снятие
    с ошибкой нет) — 4/4 (c3); после eligible exclusions пуст. PASS
G5  TEMP failure: attempt(reзультат≠success)→K remains excluded;
    slot=1, без второго slot, eligible отсутствует — 4/4 (c4). PASS
G6  Empty pool: после exclusion пул пуст → S3 → Explore(fix-aq) →
    success — 4/4 (c5, SD-среда). PASS
G7  Explore isolation: slot не создаётся; excluded K не
    восстанавливается; новый candidate — fix-aq-линия — 4/4 (c6,
    N6bV3-TEMP; после explore exclusion сохраняется). PASS
G8  Non-empty pool: sibling eligible → обычный выбор (S2), не
    S3/Explore (c2 после exclusion; c4 шаг 2 — S2). PASS
G9  Append-only: version=1 у всех знаний; L6-структурный walk —
    0 нарушений (source enum; refs непусты; (a)/(b)-состав). PASS
G10 Regression R0: 18/18 сверено с v0.6.x anchor (steps — строго
    равны); пробы: 4 A1-authorized отличия (см. §3) — PASS.
```

Guards модуля: 30/30 OK (mechanические инварианты). Audit: 48/48
слои не изменялись. Детерминизм: OK.

## 3. A1-authorized отличия (R0)

```
S5 r1: проба w1/noise — old (v0.6.x): S2 fix-a через K_81057271
       (failure-derived, aw=None, outcome=partial — legacy D-1);
       модуль (A1): S3 (failure-derived вне выбора; V1 не матчит).
S5 r2: аналогично (K_b18374c37a).
Всего 4 отличия; каждое — точная цель A1. Иных отличий нет.
```

## 4. Execution findings (в ходе гейта; слои не затрагивались)

```
EF-6  R0-режим драйвера терял флаг n (noise-миры давали success);
      найден аудитом, исправлен; R0 перезапущен (18).
EF-7  Анализатор: окно G2-проверки включало шаг до триггера →
      ложный FAIL; исправлено (сканируются шаги после триггера).
EF-8  gate_driver не заполнял final_snapshot (G1/L6 были слепы);
      исправлено; 30 механических клеток перезапущены.
EF-9  fp-сравнение тянуло случайные kid'ы из slot_state →
      ложный determinism-FAIL; нормализовано.
EF-10 Анализатор не загружал c1-клетки (право NA) → ложный PASS
      G1; исправлено.
```

Все перезапуски — тем же протоколом/семантикой; результаты
устойчивы (детерминизм OK после фиксов).

## 5. Номенклатура и следующий шаг

- Текущее имя: «A1 experimental integration» (ветка
  experiments/integration_gate). НЕ v0.7.
- Перенос A1 в production layers — по слову профессора; после
  переноса и полного regression — «v0.6.x+A1».
- POOL и TEMP остаются обе валидными конфигурациями
  (`exclusion_semantics = POOL | TEMP`); HALT не интегрируется.

## 6. Примечание о сопутствующем изменении

`experiments/gate_v06x_analyze.py` был заменён новой версией в ходе
сессии (анализ v0.6.x-гейта от 07.09: результат — GATE_V06X_
ANALYSIS.txt, 17 КБ — цел; RAW/аудиты от 07.09 целы, не
запускались заново). Скрипт-версия анализатора от 07.09 утеряна;
текущая версия не прогонялась. При необходимости анализ v0.6.x
воспроизводим по имеющимся RAW.

## 7. Артефакты

integration_gate/: PROTOCOL.md, gate_module.py, gate_driver.py,
gate_a1_analyze.py, INTEGRATION_GATE_ANALYSIS.txt,
GATE_A1_cell_*.json (48), data_gate_a1_* (47 сторов). Планировка:
INTEGRATION_GATE_A1_DESIGN.md. Слои v0.6.x не изменялись.
