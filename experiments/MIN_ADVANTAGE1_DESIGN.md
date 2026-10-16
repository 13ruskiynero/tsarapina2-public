# TSARAPINA MIN-ADVANTAGE-1: ДИЗАЙН (FREEZE, 12.09.2026; протокол профессора)

**Статус главы: Question FROZEN / Conditions FROZEN / CAND3 FROZEN /
BARE FROZEN / Paired scenes FROZEN / Revision PRIMARY / Metric
FROZEN / Operator 0 / Fresh runs REQUIRED / Execution — этим
циклом.**

Ключевое отличие от MM1: MM1 спрашивал «воспроизводится ли
механизм»; MIN-ADVANTAGE-1 спрашивает **«даёт ли минимальный
механизм реальную дельту против модели без него»**.

## 1. Research question

> Сохраняет ли минимальный причинный кандидат CAND3 практическое
> преимущество над plain Gemma4 на тех же задачах, где
> преимущество Tsarapina уже было ранее наблюдено?

## 2. Conditions

- **CAND3:** persistent action-result mapping + applicable_when +
  E2 transition/exploration + P2 BIN acquisition policy.
  Не является новой production-версией; это исследовательский
  кандидат MM1.
- **BARE:** Gemma4 → proposal → Executor → Result. Без persistent
  Knowledge, applicability, E2, acquisition, P2 BIN, внешнего
  memory carrier. Bare не получает искусственного «урезанного
  аналога памяти».

## 3. Fairness rule

> Обе стороны получают одну и ту же последовательность сцен, мир,
> task, доступные действия, executor, evaluation, модель Gemma4,
> prompt budget и temperature. Различается только наличие
> CAND3-механизма.

Особенно для EE-2-сцен: исторический bare-контроль не
используется; парность реализуется двумя сторонами на одних
эпизодах, с отдельными сторами и трейсами.

## 4. Scene families

- **A (EE-1-класс):** acquisition + repeat;
- **B:** acquisition + repeat (второй класс);
- **C:** acquisition + repeat (третий класс);
- **A′ (revision, PRIMARY):** acquired solution → environment
  change → old solution fails → E2 → exploration → new solution →
  repeat;
- **noise control:** single + double шум (проверка, что CAND3 не
  объявляет revision при случайном failure);
- **no-change control:** стабильная среда (проверка, что CAND3 не
  создаёт лишнюю стоимость).

## 5. Primary metric

Action cost to successful solution — для каждого класса:
`acquisition_cost / repeat_cost / revision_cost`; дополнительно:
success / failure / coverage / operator_dependence / amortization.

> **Главная величина: сколько действий требуется до проверенного
> успешного решения и после него.**

Исторические числа EE-2 (3→1, 5→1, 9→1, 7→1) — reference history,
не ожидаемый результат; новая глава получает числа заново.

## 6. Advantage definition

**Practical advantage:** на paired scene (1) CAND3 достигает
verified success там, где bare не достигает; **или** (2) оба
достигают success, но CAND3 требует существенно меньшего числа
действий за счёт ранее приобретённого знания.

**Revision advantage:** старый solution → смена среды → успешный
новый solution достигается с меньшей стоимостью, чем у bare, **без
внешнего operator intervention**.

## 7. Operator dependence

CAND3: operator_slots = 0 (P2). Bare: оператор тоже не подсказывает
решение.

## 8. Acquisition fairness

> Обе стороны проходят одинаковые acquisition scenes; только CAND3
> обладает механизмом превращения verified interaction в persistent
> Knowledge:
> `Scene A → CAND3: interaction → verified success → K;
> BARE: interaction → verified success → no K`.

Это и есть объект исследования; внешняя запись решения для bare не
даётся.

## 9. Controls (N1–N3)

- **N1 no-change:** среда стабильна — CAND3 не создаёт лишнюю
  стоимость;
- **N2 noise:** одиночный/двойной шум — CAND3 не объявляет revision
  при случайном failure (single); double-шум — известная граница
  E2-детектора (2 fail → E2), цена измеряется;
- **N3 revision:** настоящее изменение среды — primary advantage
  cell.

## 10. Что НЕ объявляем как proof

«CAND3 умнее» / «учится» / «обобщает» / «лучше Gemma4 вообще» /
«память достаточна для интеллекта» / «механизм масштабируется».
Максимальная формулировка: **на исследованных paired scenes CAND3
сохраняет практическое преимущество относительно plain Gemma4,
выраженное в снижении action cost и/или успешном revision после
изменения среды.**

## 11. Freshness requirement

LONGITUDINAL-1 / RELEVANCE-1 / GENERALIZATION-1 / EE-1 / EE-2 /
MM1 Cut-1/2/3 — reference history. Обе стороны запускаются заново
на свежих paired сценах; **EE-2 bare впервые измеряется реально**.

## 12. Run matrix (24 runs)

```text
Scene                  | CAND3 | BARE
A acquisition + repeat |   1   |  1
B acquisition + repeat |   1   |  1
C acquisition + repeat |   1   |  1
A′ revision + repeat   |   1   |  1
noise control          |   1   |  1
no-change control      |   1   |  1
```

6 paired scenes × 2 conditions × 2 independent repetitions = 24 runs.

## 13. Decision tree (после 24 runs)

- **A.** CAND3 лучше на acquisition/amortization И revision →
  **ADVANTAGE OBSERVED**;
- **B.** лучше только на revision → **REVISION-SPECIFIC
  ADVANTAGE**;
- **C.** лучше на repeat, но не на revision → **AMORTIZATION
  ADVANTAGE ONLY**;
- **D.** одинаково → **NO ADVANTAGE OBSERVED**;
- **E.** bare превосходит → **CAND3 COST / NEGATIVE ADVANTAGE**.

## 14. Гипотезы

**H-MA1:** CAND3 сохраняет ранее наблюдавшееся практическое
преимущество Tsarapina над plain Gemma4 в задачах, требующих
повторного использования verified interaction и/или адаптации
после изменения применимости ранее успешного решения.
**H-MA1a:** persistent mapping + applicability дают преимущество в
amortized repeat.
**H-MA1b:** E2 + exploration дают преимущество в revision после
изменения среды.

## 15. Реализация (эпизодные последовательности; свежие сторы)

```text
A:        [w1, w1]
B:        [b, b]
C:        [c, c]
A′:       [w1, w1, w2, w2, w2, w2]   (acq, repeat, fail, fail,
                                      E2→new, repeat)
noise:    [w1, w1, noise, w1, noise, noise, w1, w1]
no-change:[w1, w1, w1, w1]
```

Сторона CAND3: MappingCut3 (min_mechanism1/mm1_cut3_mapping.py,
без изменений) + P2 BIN; сторона BARE: LLM → executor →
evaluation (MAX_ACTS=4), без памяти. Реплики: rep1/rep2, свежие
сторы и свежие mapping-файлы.

Preflight (до первого run, в артефакт): сенсоры w1/w2/b/c/noise;
fix-a/fix-aq/fix-b/fix-c; BIN-позиции; adapter; CAND3 dry-run
(acquisition → aw → E2 → new → both preserved). Любой пункт false →
PREFLIGHT FAIL.

Артефакты: min_advantage1/ma1_driver.py, MA1_run.log,
MA1_trace.jsonl, MA1_TABLE.md; сторы data_ma1_*.

## 16. Границы

Один полигон (tsasvc, gemma4); драйверные политики (P2/CAND3 —
экспериментальные); D-4 / D-selection-1 / COMPETE-2 / R2 / R4 не
трогаются; production-слои не изменяются; negative results не
спасаются.

**FREEZE: 12.09.2026.**
