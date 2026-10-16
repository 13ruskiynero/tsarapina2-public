# LONG-2 / CONTEXT-GROWTH-1: ОТЧЁТ (11.09.2026)

**Статус: PASS → CLOSED (вердикт профессора, 11.09);
24 runs; 89 checks, FAIL=0; audit 24/24; r1 ≡ r2 — growth-значения
совпали до символа.**

Вопрос:

> How does longitudinal Knowledge accumulation affect the
> externally constructed context as the episode history grows?

Ответ: в текущем (замороженном, неоптимизированном) контекст-
механизме транспортируется **вся** задача-релевантная память:
`K_store − K_context = 0` на каждом эпизоде; число
транспортированных записей растёт линейно (+1 на эпизод), длина
сериализованного контекста растёт почти линейно (143→506 chars за
11 эпизодов).

## 1. Growth-таблица (обе реплики идентичны)

```
E0  kc=1   (seed)
E1  kc=2   csn=1  chars=143 lines=4  uniq=1 dup=0  store=1  trans=1  K-=0
E2  kc=3   csn=2  chars=211 lines=5  uniq=2 dup=0  store=2  trans=2  K-=0
E3  kc=4   csn=3  chars=204 lines=6  uniq=2 dup=1  store=3  trans=3  K-=0
E4  kc=5   csn=4  chars=276 lines=7  uniq=3 dup=1  store=4  trans=4  K-=0
E5  kc=6   csn=5  chars=267 lines=8  uniq=3 dup=2  store=5  trans=5  K-=0
E6  kc=7   csn=6  chars=335 lines=9  uniq=3 dup=3  store=6  trans=6  K-=0
E7  kc=8   csn=7  chars=328 lines=10 uniq=3 dup=4  store=7  trans=7  K-=0
E8  kc=9   csn=8  chars=400 lines=11 uniq=3 dup=5  store=8  trans=8  K-=0
E9  kc=10  csn=9  chars=391 lines=12 uniq=3 dup=6  store=9  trans=9  K-=0
E10 kc=11  csn=10 chars=459 lines=13 uniq=3 dup=7  store=10 trans=10 K-=0
E11 kc=12  csn=11 chars=506 lines=14 uniq=3 dup=8  store=11 trans=11 K-=0
```

## 2. Проверки (A-G-1..5)

```
A-G-1  полные записи + audit (24/24);
A-G-2  append-only / структурно валиден (removed=[]; added
       соответствуют created_knowledge_id);
A-G-3  context_source_n неубывающий (1..11, ровно +1);
A-G-4  L-chain: first_seen(K) < n для всех транспортированных;
A-G-5  ворота/chain kid→exp→episode; r1≡r2 (структурные поля).
89/89 PASS.
```

## 2a. LONG-2 establishes / does NOT establish (whiteboard)

```
LONG-2 establishes:
  faithful transport at N=12
  linear record accumulation
  sub-linear unique-content growth
  increasing duplicate burden
LONG-2 does NOT establish:
  context scalability
  transport capacity limit
  optimal context construction
  compression/relevance policy
  model degradation
```

## 3. Наблюдения (не критерии)

```
O1  context_source_ids растут линейно: +1 запись на эпизод;
    контекст транспортирует ВСЁ (K_store − K_context = 0 на всех
    эпизодах). «Память растёт быстрее, чем её видит запрос» — в
    текущем дизайне НЕТ, транспорт не отстаёт.
O2  chars: 143→506; колебания ±(47..72) из-за serializer-эффекта
    (длина prev-строки и двух пробелов отступов), а не из-за смены
    механизма. Не token metric (оговорка FROZEN).
O3  unique_commands: 1→3 (fix-a, systemctl start tsasvc.service,
    systemctl restart tsasvc.service), затем плато: модель
    использует три команды; dup_lines растёт 0→8 (повторяющиеся
    «команда → исход»).
O4  Форма роста: линейная по числу записей; суб-линейная по
    уникальному содержанию (dup доминирует после E4).
O5  Траектория предложений (observation): чередование
    start → fix-a → restart → fix-a → start → fix-a → restart →
    fix-a → start → restart → start; в w1-фазах fix-a даёт success
    (E2/E4/E8), в шумовых — partial (E6).
O6  r1≡r2: growth-значения и траектории совпали полностью.
```

## 4. Ограничения

```
* 12 эпизодов; рост исследован до N=12 (не до предела модели).
* Контекст-механизм не оптимизировался (по решению): измерение,
  не решение о summarization/ranking/forgetting.
* Шумовые фазы — часть траектории, не robustness-гипотеза.
* D-2/D-3/D-4/D-6/EF-12 не открывались; strategy.py не трогался.
```

## 5. Дальше (по слову)

```
Решение после LONG-2: O3 (возврат к гипотезе), cross-series
persistence (counters между сериями), либо отдельный вопрос
«что делать с растущим контекстом» (теперь — на данных:
K_store−K_context=0 при N=12, dup растёт). Ни одно не решается
здесь.
```

## 6. Артефакты

```
long2/PROTOCOL.md (FROZEN), long2_driver.py, long2_analyze.py,
LONG2_E0..E11_r1/r2.json (24), LONG2_ANALYSIS.txt (89 checks),
LONG2_DESIGN.md (FROZEN). Слои v0.6.x+A1 не изменялись
(audit 24/24).
```
