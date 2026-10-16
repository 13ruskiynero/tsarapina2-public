# TSARAPINA MIN-EXPLORATION-1 (MX-1): ДИЗАЙН (FREEZE, 12.09.2026; протокол профессора)

**Статус: Question FROZEN / Polygon A′ revision / Model Gemma4 /
M1 E2→LLM search / M2 E2→BIN / M3 E2+BIN (positive control) /
First action start / Operator 0 / Memory absent / Applicability
held constant / Executor frozen / Budget frozen / Primary metric
successful systematic exploration / Replications 3×3 / Total runs 9
/ Status DESIGN READY / Execution — этим циклом.**

## 1. Research question

> Что превращает смену действия после repeated failure в
> systematic exploration, достаточную для нахождения нового
> verified solution?

Граница SAF-1 зафиксирована: `feedback → action change ✗
exploration`. Теперь разделяем `E2` и `BIN`, которые до сих пор
ходили парой.

## 2. Три кандидата

- **M1: E2 → LLM search.** После E2 система НЕ получает BIN; LLM
  получает режим поиска («разрешается предложить альтернативное
  corrective действие, отличное от ранее неуспешных») и сама
  выбирает следующий action из allowlist (каждый поисковый эпизод —
  новый выбор).
- **M2: E2 → BIN.** LLM не получает semantic instruction и вообще
  не вовлекается; после E2 — внешний systematic enumeration (тот же
  BIN, что в acquisition).
- **M3: E2 + BIN (positive control).** Текущий CAND3-путь: fail×2
  → E2 → exploration authorization → BIN. Наблюдаемая механика
  поиска совпадает с M2; различие — провенанс (точный Cut-3-путь с
  authorization-семантикой).

**Важная методологическая поправка (принята):** M3 не получает
преимуществ persistent mapping/applicability — после E2 все три
кандидата находятся в **одинаковом revision state**; memory —
absent, applicability — held constant.

## 3. Фиксировано для всех кандидатов

Gemma4; executor; action space; environment; budget; temp=0;
operator=0; первый action = `start`; одинаковая failure-лента до
E2; независимые сторы; old Knowledge отсутствует; `fix-aq` модели
не сообщается; success — только executor/evaluation.

До E2 (одинаково у всех): Э1 `start` (принудительно) → partial;
Э2 auto-repeat `start` → failure → **E2 срабатывает** (два
последовательных non-success — установленный threshold, НЕ
меняем).

**Search budget (зафиксировано до запуска):** после E2 всем
кандидатам доступно 8 эпизодов (полный BIN = 8 команд; M1 — 8
поисковых ходов). MAX_EPISODES = 10 (2 до-E2 + 8 поисковых).

## 4. Primary metric

**Successful systematic exploration:** после E2 система выходит в
exploration → проверяет альтернативные действия → находит `fix-aq`
→ verified success.

Классы:

- **E0 — no exploration:** после E2 same/arbitrary action →
  failure;
- **E1 — exploration without success:** после E2 разные действия →
  без verified success;
- **E2-класс — successful exploration:** после E2 systematic
  search → `fix-aq` → SUCCESS.

## 5. Secondary metrics

exploration_started; unique_commands_after_E2;
first_alternative_action; **search_order**; actions_to_success;
verified_success.

Search order — ключевая различающая величина: M2/M3 (если работают
через BIN) обязаны дать систематический порядок; M1-«угадывание»
(`start → fix-aq`) — успех, но НЕ systematic search; не смешивать.

## 6. Run matrix

```text
M1 × 3 repetitions
M2 × 3 repetitions
M3 × 3 repetitions
```

**9 runs**; temp=0 даёт высокую детерминированность, три реплики
ловят механическую нестабильность.

## 7. Ожидаемые интерпретации

- **M1 succeeds** → E2 сам по себе способен перевести модель в
  exploration mode; BIN не необходим;
- **M2 succeeds, M1 не** → permission/transition без
  структурированного поиска недостаточен; ключ — systematic
  external search;
- **только M3 succeeds** → разбирать, что в комбинации даёт эффект
  (на данной реализации M2/M3 механически совпадают в фазе BIN —
  ожидание фиксируется; исход «M2✗, M3✓» конструктивно исключён);
- **все три succeed** → E2 — вероятный достаточный переключатель,
  BIN — один из способов реализации exploration;
- **ни один не succeeds** → модель exploration неполна; успех
  Cut-3 мог зависеть от ещё одного скрытого механизма.

## 8. Frozen boundaries

Не исследуем: scalability; generalization; quality of BIN; разные
LLM; разные prompts; разные полигоны; long-run; trust; forgetting;
representation. **E2 threshold не меняем** — вопрос не «правилен ли
порог», а «что происходит после его срабатывания».

## 9. Реализация

- драйвер: `min_exploration1/mx1_driver.py`; логи `MX1_run.log`,
  `MX1_trace.jsonl`; сторы `data_mx1_*`;
- M1: на каждом поисковом эпизоде — LLM-выбор (RB1-frame +
  фактическая лента + authorization-фраза; действие не называется);
- M2: после E2 — BIN-перебор без LLM;
- M3: то же, что M2, с CAND3-провенансом (authorization-флаг в
  trace);
- preflight: сенсоры/полигон/fix-aq/adapter (стандартный).

## 10. Границы

Один полигон (tsasvc, gemma4); один threshold; один бюджет
(8 поисковых эпизодов); action allowlist фиксирован; production-
слои не изменяются; negative results не спасаются.

**FREEZE: 12.09.2026.**
