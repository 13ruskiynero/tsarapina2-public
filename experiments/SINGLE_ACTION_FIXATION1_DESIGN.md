# TSARAPINA SINGLE-ACTION-FIXATION-1 (SAF-1): ДИЗАЙН (FREEZE, 12.09.2026; протокол профессора)

**Статус: Question FROZEN / Model Gemma4 / Condition plain bare /
First action start / World A′ revision polygon / Feedback verified
result / E2 ABSENT / Memory ABSENT / P2/BIN ABSENT / Operator 0 /
Prompt change NONE beyond existing RB1 framing / Primary metric
fixation vs escape / Secondary unique actions, success, cost /
Max episodes 8 / Replications 6 / Status DESIGN READY / Execution —
этим циклом.**

## 1. Research question

> Может ли plain Gemma4 самостоятельно выйти из повторяющегося
> неуспешного corrective action после получения результата failure,
> или для перехода к альтернативному действию необходим внешний
> E2-механизм?

## 2. Что фиксируем

Не меняем: Gemma4; executor; action allowlist; environment;
temperature; budget; action space; первый ход; отсутствие
persistent memory; отсутствие CAND3; отсутствие P2/BIN;
operator = 0.

Первый ход принудительно соответствует RB1-траектории:

```text
start → FAIL
```

Никакого нового «попробуй другое действие» в prompt — сверх уже
существующего RB1-framing (разрешение corrective action).

## 3. Feedback cadence (реализация)

Внешняя адаптационная проверка — **decision point после каждых
двух последовательных неуспехов**:

```text
Э1: start (принудительно, без LLM) → FAIL          [consec=1]
Э2: auto-repeat start → FAIL                       [consec=2]
DP1: LLM (получает фактическую ленту результатов) выбирает действие
Э3: выбранное → ?                                  [consec=1 при fail]
Э4: auto-repeat выбранного → ?                     [consec=2 при fail]
DP2: LLM выбирает следующее действие
... до SUCCESS или MAX_EPISODES=8
```

- на decision point модель получает актуальный результат
  (фактическую ленту: эпизод → команда → исход; + число
  последовательных неуспехов) и выбирает следующее corrective
  действие;
- между decision points действие повторяется (авто), чтобы пара
  «два consecutive failures» была фактически наблюдаемой единицей —
  тот же observable pattern, что служит E2-порогом в контуре
  (E2 здесь НЕ включается);
- успех любого эпизода завершает run (SUCCESS);
- иначе run идёт до MAX_EPISODES = 8 (зафиксировано до запуска).

## 4. Primary metric — action transition

```text
FIXATION:  start → start → start → ...
ESCAPE:    start → restart / fix-a / fix-aq / ...
```

Escape не обязан быть успешным. Три исхода:

- **F1 FIXATION:** модель остаётся на одном действии;
- **F2 ESCAPE WITHOUT SUCCESS:** вышла из фиксации, решения не
  нашла;
- **F3 SUCCESSFUL ADAPTATION:** escape → verified success.

## 5. Secondary metrics (на каждый run)

first_action; action_sequence; unique_commands;
first_action_change_episode; number_of_failures_before_escape;
number_of_actions_to_escape; number_of_actions_to_success;
verified_success.

## 6. Сцена

A′ revision polygon (мир w2): старое действие (`start`) известно как
неработающее, новое решение (`fix-aq`) существует и независимо
проверено в MM1/MA1. Модель ответа не получает.

## 7. Run matrix

**6 independent runs**; каждый идёт до SUCCESS или MAX_EPISODES = 8
(без предзаданной остановки по ожидаемому поведению); свежие сторы.

## 8. Gate

- **Gate A:** все runs `start → start → ...` → **Action fixation
  observed** (feedback сам по себе недостаточен для перехода к
  альтернативному corrective action);
- **Gate B:** модель меняет действия → **Action escape observed**
  (E2 не является необходимым для escape);
- **Gate C:** bare самостоятельно находит verified solution →
  **Successful adaptive recovery observed** (минимальная причинная
  роль E2 должна быть пересмотрена).

## 9. Гипотеза

**H-SAF1:** после повторяющегося verified failure plain Gemma4 без
внешнего E2-механизма сохраняет выбранное corrective action либо не
демонстрирует устойчивого перехода к альтернативному действию.
H-SAF1 PASS → fixation persists; H-SAF1 FAIL → model escapes
fixation. (Даже FAIL — не провал: тогда E2 нужен не для способности
менять действие, а для надёжного разрешения/маршрутизации перехода.)

## 10. Запрет

CAND3 в этот эксперимент не тащится: только bare →
repeated failure → does model escape. CAND3 уже дал положительный
контроль в MA1.

## 11. Реализация

- драйвер: `single_action_fixation1/saf1_driver.py`;
- промпт DP: RB1-framed task + фактическая лента результатов run'а
  (эпизод → команда → исход) + счётчик последовательных неуспехов;
- запреты: не называть fix-a/fix-aq, не давать алгоритм поиска, не
  упоминать историю вне run / CAND3 / Knowledge;
- логи: `SAF1_run.log`, `SAF1_trace.jsonl`; сторы `data_saf1_*`;
- preflight: сенсоры/полигон/fix-*/adapter (стандартный).

## 12. Границы

Один полигон (tsasvc, gemma4); оператор 0; один вариант cadence
(DP после двух неуспехов); MAX_EPISODES=8; D-4 / D-selection-1 /
COMPETE-2 / R2 / R4 не трогаются; production-слои не изменяются.

**FREEZE: 12.09.2026.**
