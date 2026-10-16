# TSARAPINA ROBUST-ADVANTAGE-1: ДИЗАЙН (FREEZE, 12.09.2026; протокол профессора)

**Статус: Question FROZEN / CAND3 FROZEN (unchanged) / BARE —
stronger action framing / Scenes — MA1 paired sequence / Primary
metric — verified success / Secondary — action type, cost, revision /
Intervention — prompt only / Operator 0 / Runs 24 bare / Execution —
этим циклом.**

## 1. Вопрос

> Сдвигается ли observed advantage CAND3 относительно plain Gemma4,
> если bare получает более сильное action framing, явно разрешающее
> предпринимать corrective action вместо одной диагностики?

Это проверка единственного очевидного confound у MIN-ADVANTAGE-1.

## 2. Что меняем

**Только bare prompt.** CAND3 остаётся абсолютно неизменным
(CAND3, P2, applicability, E2, Gemma4, executor, action space,
budget, temperature, environments, sequence). Драйвер CAND3 не
перезапускается — он reference anchor из MA1.

Bare получает одну дополнительную инструкцию:

> «Если имеющихся свидетельств достаточно, предпринимай конкретное
> corrective действие, а не ограничивайся диагностикой; после
> действия оцени его результат.»

**Никаких подсказок какое именно действие выполнять.**

## 3. Запрещено (чтобы не превратить эксперимент в театр подсказок)

- нельзя назвать `fix-a` / `fix-aq`;
- нельзя давать алгоритм поиска;
- нельзя упоминать Knowledge CAND3 / давать history;
- нельзя менять executor / action allowlist;
- нельзя менять temperature/budget;
- нельзя менять сцену;
- нельзя вручную вмешиваться после failure.

Только: «если достаточно доказательств — переходи от диагностики к
corrective action».

## 4. Primary comparison

```text
BARE-old prompt        → 0/48 success        (MA1 baseline)
BARE-action-framed     → ?                   (эта глава)
CAND3                  → anchor (не меняется)
```

**Primary метрика:** verified success rate bare.
**Вторичные:** action cost; тип первого действия; diagnostic vs
corrective proposal; acquisition/repeat; revision; operator
dependence.

## 5. Минимальный дизайн

Те же сцены MA1 (A, B, C, A′, noise, no-change), только bare:

```text
6 scenes × 2 (реплики MA1: r1, r2) × 2 (повторности) = 24 bare runs
```

Свежие сторы; тот же executor/evaluation/полигон; только промпт
отличается. Расширение только после сдвига.

## 6. Gate (заранее)

```text
verified_success > 0  → framing effect observed
                      → MA1 advantage is prompt-sensitive
                      → open decomposition
verified_success = 0  → no framing rescue observed
                      → MA1 advantage survives this control
```

Важнее нуля — **тип поведения**: если bare начнёт делать corrective
actions, но систематически неверные («diagnostic-only →
corrective-but-wrong»), это тоже сдвиг: framing меняет policy
space, даже если не меняет success.

## 7. Особый интерес — revision (A′)

Для A′ смотрим последовательность:

```text
old implied solution → failure → failure → alternative corrective
action → verified result
```

- если bare по-прежнему: `status → journalctl → status → ...` —
  MA1 существенно убедительнее;
- если bare сам находит `fix-aq` — сильный отрицательный результат
  для сильной версии гипотезы: «E2 + external exploration не
  обязательно необходимы для revision, если модель получает
  правильный поведенческий framing».

## 8. Реализация

- драйвер: `robust_advantage1/rb1_driver.py` (только bare-сторона);
- промпт: базовый task_text + framed-предложение (см. §2); SYSTEM
  адаптера и контракт не меняются;
- классификация действий: corrective (start/restart/stop/fix-*) vs
  diagnostic (status/journalctl/is-active/...); фиксируется тип
  первого действия и все кандидаты;
- логи: `RB1_run.log`, `RB1_trace.jsonl`; сторы `data_rb1_*`;
- preflight: сенсоры/полигон/fix-*/adapter — как в MA1 (без
  behavior-фиксации).

## 9. Границы

Один полигон (tsasvc, gemma4); оператор 0; CAND3 не изменяется;
D-4 / D-selection-1 / COMPETE-2 / R2 / R4 не трогаются;
production-слои не изменяются; negative results не спасаются.

**FREEZE: 12.09.2026.**
