# TSARAPINA MIN-MECHANISM-1: ДИЗАЙН (FREEZE, 12.09.2026)

**Статус: FREEZE (12.09.2026; все шесть развилок §6 приняты в
рекомендованном варианте).** Purpose: causal decomposition первого
разреза — что необходимо для эффекта `first acquisition → repeat =
1 action` и где его границы. **9 → 1 трактуется как experimental
probe**, не как результат. Слои v0.6.x+A1 не меняются; MAPPING —
experimental driver-level candidate (прецедент: strategy_v2 в
RELEVANCE-1, отдельный модуль ветки). D-4 / D-selection-1 /
COMPETE-2 / R2 / R4 — не трогаются.

## 1. Вопрос

Какая минимальная связка воспроизводит target-эффект?

```text
FULL:    Experience → Knowledge → applicability → retrieval → Strategy → repeat
MAPPING: verified success → persistent (condition, action, result) → lookup → repeat
```

И где проходят границы поведения — Repeat / Mismatch / Revision /
сохранение старого K / реакция на failure.

## 2. Target-критерий

После первого verified SUCCESS класса повторное предъявление того же
класса решается за **1 действие** (действия считаются как в EE-1/2;
успех — по evaluation, не по словам).

## 3. Стороны (два прогона, одинаковые сцены)

- **FULL:** Tsarapina v0.6.x+A1 + политика EE-2 (S2 → execute;
  exploration/E2/S1(no relevant K) → BIN; иное → LLM-fallback), слои
  как есть.
- **MAPPING (minimal candidate):** experimental модуль ветки —
  файл-map `{condition(symptom): (action, result)}`; запись после
  каждого verified success; при задаче — lookup по condition →
  execute. Иных обработок (failure, revision, applicability) НЕТ.
  Persistence — между эпизодами (файл), без ротации носителя.
- Acquisition для обеих сторон — **общий BIN-перебор** (одинаковая
  процедура; для FULL это драйверная P2-политика, для MAPPING —
  единственный путь приобретения).

## 4. Сцена (одинаковая; R1–R9)

```text
R1  acq A (w1)      первый контакт (BIN)
R2  repeat A (w1)   target: 1 действие?
R3  A + E (extra)   mismatch (E: present)
R4  repeat A (w1)
R5  A′ = a+q  #1    1-й fail
R6  A′ #2           2-й fail (для FULL — накопление события)
R7  A′ #3           FULL: E2 → explore; MAPPING: слепой lookup
R8  A′ #4           post-revision exploitation?
R9  A (w1)          старое K живо?
```

9 сцен × 2 стороны = 18 эпизодов; один стор на сторону.

## 5. Выход — таблица разреза

```text
Механизм            | Repeat | Mismatch | Revision | Старое K | Failure
Persistent mapping  |   ?    |    ?     |    ?     |    ?     |   ?
Full Tsarapina path |   ?    |    ?     |    ?     |    ?     |   ?
```

Заполняется фактами обоих прогонов; цель — отделить **механизм
амортизации** от **механизма развития**.

## 6. Развилки (на слово профессора)

1. MAPPING при non-success: **(a) ничего — минимальный кандидат
   (рекомендую)**; (b) пометка failed + перебор — это уже вторая
   ступень декомпозиции, не первый разрез.
2. Condition для MAPPING: **только symptom (рекомендую)**; вариант
   `(symptom, E)` — кандидат второй ступени (MAPPING+applicability),
   не сейчас.
3. Acquisition: общий BIN для обеих сторон (рекомендую) — фиксирует
   различие только в механизме повторного использования.
4. Сцена R1–R9 — подтвердить (или сократить).
5. FULL-стор — свежий прогон на тех же сценах (рекомендую; он же
   репликация EE-2), а не переиспользование логов EE-2.
6. Имя ветки: `min_mechanism1`.

## 7. Границы

- первый разрез — ровно две стороны; промежуточные механизмы
  (MAPPING+applicability, MAPPING+E2 и т.п.) не запускаются до
  результата первого разреза — последовательная декомпозиция, один
  срез за раз;
- никаких правок Strategy/Knowledge/Executor/Evaluation;
- интерпретация — после прогонов; negative results не спасаются;
- persistence/ротация (RE-1), длинный контекст, ресурсные ветки —
  вне scope.

## 8. Артефакты (планируемые)

min_mechanism1/: mm1_driver.py, mm1_mapping.py (minimal candidate),
MM1_trace.jsonl (обе стороны), MM1_run.log, MM1_TABLE.md,
MIN_MECHANISM1_REPORT.md.

## 9. FREEZE (12.09.2026; слово профессора)

Все шесть развилок §6 — приняты в рекомендованном варианте:
MAPPING при non-success — ничего; condition — только `symptom`;
acquisition — общий BIN; R1–R9 — целиком; FULL — свежий прогон;
имя — `min_mechanism1`.

**Главное условие разреза (заморожено):**
> Обе стороны имеют одинаковый acquisition mechanism. Фактором
> различия является только механизм использования уже
> приобретённого знания после первого verified success.

**MAPPING не получает recovery policy.** Если он сломается на A′ —
это не «плохая реализация mapping», это ровно тот результат,
который нужен: минимальный persistent mapping достаточен для
амортизации, но недостаточен для развития.

**Железный критерий:** не сравнивать только финальный success;
фиксировать полный набор границ — Repeat / Mismatch / Revision /
Old Knowledge / Failure.

**FREEZE: 12.09.2026.**