# TSARAPINA EXCLUDE-TRIED-1 (ET-1): ДИЗАЙН (FREEZE, 12.09.2026; протокол профессора)

**Статус: Question FROZEN / Polygon A′ revision / Model Gemma4 /
Control BIN / Candidate EXCLUDE-TRIED / First action start /
E2 present / Memory no persistent K / Applicability held constant /
Operator 0 / Primary metric successful exploration / Secondary
search efficiency / Hidden solution fix-aq / Replications 3 × 2 /
Total runs 6 / Status DESIGN READY / Execution — этим циклом.**

## 1. Research question

> Достаточно ли внешнего исключения уже проверенных действий,
> чтобы превратить LLM choice в эффективную exploration, или для
> успеха необходим полный систематический BIN-перебор?

После MX-1: `E2 → LLM authorization ✗`, `E2 → BIN ✓`. BIN делает
две вещи: (1) systematic enumeration; (2) автоматически убирает
проверенные кандидаты. Отделяем (2) от (1).

## 2. Кандидаты

- **EXCLUDE-TRIED:** после E2 — `tested actions → external exclusion
  → remaining actions → LLM chooses`. Полного BIN нет.
- **BIN:** положительный контроль из MX-1 (тот же BIN-механизм).

## 3. Ключевая fairness condition

Внешний слой сообщает модели **только**: «эти действия уже
проверены и недоступны». Он **не сообщает**, какое действие
правильное. Запрещены: ranking; heuristic; action ordering (как
приоритезация); semantic hints; success prediction. Только:

```text
already tried → unavailable
```

## 4. Реализация (зафиксировано до запуска)

- **candidate space EXCLUDE-TRIED = BIN-набор** (8 команд:
  start, restart, fix-a, fix-b, fix-ab, fix-a2, fix-aq, fix-c);
  не полный allowlist — чтобы изолировать exclusion-механизм от
  free generation (как в M1);
- до E2 одинаково у всех: Э1 `start` (forced) → partial; Э2
  auto-repeat → failure → **E2** (threshold не меняем);
- после E2: `tested` = выполненные действия; `remaining = BIN \
  tested`; список remaining показывается в каноническом (BIN)
  порядке — без ранжирования; LLM выбирает из remaining; выбранное
  исполняется; при fail пополняет `tested`; при verified success
  run завершается;
- предложение вне remaining → фиксируется (`out_of_space`),
  эпизод без действия; `tested` не пополняется;
- поисковый бюджет: 8 эпизодов после E2; MAX_EPISODES = 10;
- `fix-aq` остаётся скрытым от модели; success — только
  executor/evaluation.

## 5. Метрики

**Primary:** successful exploration (определение MX-1: после E2 →
выбор из remaining → `fix-aq` → verified success).

**Secondary:** search efficiency (`actions_after_E2`); search_order;
рост excluded-набора; число `out_of_space`.

Сильный результат — `fix-aq → SUCCESS` (быстрая эффективность);
нормальный — `fix-b, fix-ab, fix-a2, fix-aq, SUCCESS` (механизм
работает, порядок выбирает LLM).

## 6. Run matrix

```text
EXCLUDE-TRIED × 3
BIN          × 3   (положительный контроль; должен повторить MX-1)
```

**6 runs.** Если BIN внезапно изменится — различие не приписывается
EXCLUDE-TRIED; сначала разбирается контроль.

## 7. Decision tree

- **X1 PASS:** `EXCLUDE-TRIED → remaining-space choice → SUCCESS`
  → BIN не является необходимым; механизм минимизируется до
  `external memory of attempted actions + exclusion + LLM choice`;
- **X1 FAIL + BIN PASS:** одного исключения недостаточно; вопрос —
  что именно даёт BIN сверх exclusion (порядок, полнота,
  детерминированность);
- **EXCLUDE-TRIED меняет действия, но не находит решение:**
  `remaining-space choice ≠ systematic coverage` — та же граница,
  что в MX-1, но с более сильным контролем.

## 8. Что запрещено менять

Gemma4; prompt (сверх remaining-блока); temperature; budget;
executor; allowlist; polygon; E2; operator; acquisition;
applicability.

## 9. Границы

Один полигон (tsasvc, gemma4); один threshold; один бюджет;
candidate space фиксирован (BIN); три реплики на кандидата;
production-слои не изменяются; negative results не спасаются.

**FREEZE: 12.09.2026.**
