# LONG-3 / CONTEXT-THRESHOLD-1: ОТЧЁТ (11.09.2026)

**Статус: PASS → CLOSED (вердикт профессора, 11.09) —
`boundary not observed up to N=75`**
(75 эпизодов × 2 реплики; оба чекпоинта LONG-2-compat пройдены;
ноль срабатываний B1/B2a/B2b/B3/B4 на 148 LLM-эпизодах).
Next: LONG-3A (provider-scale verification: num_ctx ↔ counter);
масштабная метрика для provider-границ — counter; chars —
serializer observation.

Вопрос:

> At what point does longitudinal Knowledge accumulation cease
> to be faithfully transportable under the current
> context-construction mechanism?

Ответ на данных N≤75: **в исследованном диапазоне точка не
наступает.** Текущий (неоптимизированный) контекст-механизм
транспортирует всю историю задачи без обрыва: K_store − K_context = 0
на каждом эпизоде обеих реплик, провайдерский счётчик промпта
(prompt_tokens) монотонно растёт до 878 без единого признака плато,
L-chain invariant сохранён на всех 148 переходах.

## 1. Чекпоинты (обе реплики; K− всегда 0)

```
N=12  kc=12  csn=11  chars=506   (LONG-2 compatibility: PASS, 0 diffs)
N=20  kc=20  csn=19  chars=781
N=30  kc=30  csn=29  chars=1065
N=50  kc=50  csn=49  chars=1689
N=75  kc=75  csn=74  chars≈2505–2509
```

## 2. B-детекторы (правила зафиксированы до запуска)

```
B1  K_store−K_context > 0 ............ 0 срабатываний
B2a transport failure (ok=False) ..... 0 срабатываний
B2b counter не растёт при росте chars  0 срабатываний
    (counter: 167 → 878, монотонно; +17..19/эпизод)
B3  L-chain violation ................ 0 срабатываний (148/148)
B4  иное механическое ................ 0 срабатываний
STOP не наступал; серии дошли до N=75 штатно.
```

## 3. Проверки A-T-1..6

```
A-T-1  audit 148/148 чисто (слои не изменялись);
A-T-2  первый B: не зафиксирован; результат — «boundary not
       observed up to N=75» (валидный исход, заморожен);
A-T-3  n/a (стопа не было);
A-T-4  неполных записей: 0;
A-T-5  границы реплик: r1 — нет, r2 — нет (не усредняем;
       наблюдение недетерминизма ниже);
A-T-6  checkpoint@12: PASS у обеих реплик (0 расхождений по
       growth-полям и траектории; gate отработал).
```

## 4. Наблюдения (не критерии)

```
O1  counter (prompt_tokens) идентичен у r1/r2 на ВСЕХ 74 эпизодах
    (167…878), при том что chars на E56/E58/E62/E64/E68/E70/E74
    микродивергировали (±2–4 знака, разные по длине команды
    start/restart при occasionally недетерминированном выборе
    модели). Provider-токенизация оказалась устойчивее
    serializer-строк: полезное свойство для B2b детекции.
O2  Форма роста: csn ≈ ep (линейно); chars ≈ 32×ep (суб-линейно
    к csn из-за повторов); counter ≈ 120 + 10.2×ep (фикс. часть
    промпта + линейный прирост контекста).
O3  Дублирующий балласт продолжает расти (как в LONG-2), но
    структурного ограничения до N=75 не вызывает.
O4  Модель в w1-фазах периодически возвращает success (E12, E15,
    E19, E22, E24, E26, E30, E32, …), в шумовых — partial;
    поведение стабильно на протяжении 75 эпизодов.
```

## 5. Ограничения

```
* Диапазон N≤75; граница может лежать дальше (или не лежать
  в этом механизме вовсе — зависит от правды о num_ctx).
* Одна модель (gemma3:4b), один размер контекста ollama.
* Контекст-механизм не оптимизировался (по решению);
  summarization/ranking/forgetting — не трогались.
* D-2/D-3/D-4/D-6/EF-12 не открывались; strategy.py не изменялся.
```

## 6. Whiteboard

```
LONG-3 establishes:
  faithful transport through N=75 (обе реплики)
  linear record accumulation without transport failure
  monotone provider-counter growth (no plateau signal)
  L-chain + audit invariants hold over 148 transitions
LONG-3 does NOT establish:
  transport capacity limit (не достигнут)
  context scalability beyond N=75
  optimal context construction
  compression/relevance policy
  model degradation
```

## 7. Дальше (по слову)

```
Решение: (a) расширять N (100/150/200) — искать дальше;
(b) считать границу «практически недостижимой при данном
механизме» и переходить к O3 / cross-series / вопросам
оптимизации контекста; (c) сначала «отмотка масштаба» —
сопоставить 148-токенные счётчики с фактическим num_ctx
провайдера (наблюдение провайдера, не изменение механизма).
Ни одно не решается здесь.
```

## 8. Артефакты

```
long3/PROTOCOL.md (FROZEN), long3_driver.py, long3_analyze.py,
LONG3_E0..E74_r1/r2.json (150 записей), LONG3_ANALYSIS.txt,
LONG3_CHECKPOINT12_r1/r2.json (оба PASS), LONG3_DESIGN.md (FROZEN);
llm/adapter.py — observability patch (sha 143f3609…, тест
test_llm_adapter пройден; прочие слои не изменялись).
```
