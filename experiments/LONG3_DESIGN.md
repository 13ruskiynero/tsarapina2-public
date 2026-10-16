# LONG-3 / CONTEXT-THRESHOLD-1: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора: OT-1..5 — PASS; OT-3 →
вариант A (минимальный adapter observability patch: только проброс
уже существующих метаданных ответа; НЕ доказательство truncation
сам по себе — provider-side signal, классификация по правилу
протокола, зафиксированному до запуска); ADD — **LONG-2
compatibility checkpoint @N=12** (gate перед N=20). При обнаружении
boundary — СТОП; **никаких исправлений context-механизма** —
граница измеряется в исходной системе.

## 1. Вопрос

> **At what point does longitudinal Knowledge accumulation cease
> to be faithfully transportable under the current
> context-construction mechanism?**

## 2. Подход

```
Одна ПРОДОЛЖАЮЩАЯСЯ серия (r1 и r2 независимо); чекпоинты
N = 12 → 20 → 30 → 50 → 75; стоп по первому mechanical boundary.
N=12 — LONG-2 compatibility checkpoint (ADD, gate перед N=20).
«All known task results → next context» (как LONG-2; контекст-
механизм не меняется).
```

## 3. Mechanical boundary (FROZEN; правила до запуска)

```
B1  K_store − K_context > 0 (первый эпизод);
B2a transport failure: ok=False + непустая ошибка;
B2b truncation signal: provider counter (prompt_eval_count /
    usage.prompt_tokens — фактическое поле провайдера)
    (n) ≤ (n−1) при context_chars(n) > context_chars(n−1) —
    провайдер перестал «видеть» рост промпта;
    если счётчик недоступен — B2b не вычисляется
    (observation-gap, фиксируется явно);
B3  L-chain violation: транспортированный K с first_seen(K) ≥ n;
B4  иное механическое: исключение при эпизоде / audit mismatch /
    нарушение append-only / незаполненная обязательная запись.

СТОП: первый B → серия останавливается; фиксируется (тип, эпизод,
значения). B не наступил до N=75 → «boundary not observed up to
N=75» — валидный результат.
```

## 4. Adapter observability patch (FROZEN; OT-3 → A)

```
Минимальное расширение llm/adapter.py: propose() дополнительно
возвращает УЖЕ СУЩЕСТВУЮЩИЕ метаданные ответа:
    provider_meta = {prompt_tokens, completion_tokens, total_tokens,
                     prompt_eval_count, eval_count}
    (что фактически отдаёт провайдер; отсутствующие — None).
НЕ меняются: prompt; serialization; context construction;
strategy; permission; proposal schema; decision logic.
Счётчик НЕ объявляется доказательством truncation: он — вход
правила B2b (§3). Иных наблюдений провайдера не добавляем.
```

## 5. Среды (FROZEN)

```
E0 seed (w1, fix-a); далее LLM-эпизоды; средовой паттерн —
циклические блоки LONG-2-формы: 4×w1, 3×noise, 4×w1 (сохраняет
сопоставимость с LONG-2; новая переменная не вводится);
паттерн фиксирован до запуска.
```

## 6. Метрики (FROZEN)

```
Все growth-метрики LONG-2 (context_source_ids/n, chars, lines,
unique_commands, dup_lines, stored/transported, K_store−K_context);
per-episode: B-проверки (B1/B2a/B2b/B3/B4), provider_meta,
llm_error, decision;
чекпоинты N ∈ {12,20,30,50,75};
truncation — только через правило B2b.
```

## 7. Критерии (FROZEN)

```
A-T-1  до первого B: инварианты LONG-2 держатся
       (audit/append-only/chain/permission);
A-T-2  первый B зафиксирован механически (тип, эпизод, значения)
       ИЛИ «boundary not observed up to N=75» — оба валидны;
A-T-3  после первого B серия остановлена (без «дожима»);
A-T-4  полная запись каждого эпизода (до стопа);
A-T-5  r1/r2 фиксируют СОБСТВЕННЫЕ границы; при расхождении —
       записать оба момента и исследовать расхождение (не
       выбирать «истинный» и не усреднять);
A-T-6  LONG-2 compatibility checkpoint @N=12: growth-поля
       (knowledge_count, context_source_n, context_chars,
       context_lines, unique_commands, dup_lines, L-chain,
       траектория) соответствуют LONG-2 там, где протоколы
       идентичны (raw не byte-for-byte — добавлены метаданные);
       при расхождении — фиксировать, НЕ подгонять;
       checkpoint — gate: N≥20 не запускается до его завершения.
PASS = A-T-1..6.
```

## 8. Запреты

```
никаких summarization/ranking/forgetting/compression/trust/
semantic selection; никаких изменений context-механизма/
strategy.py/слоёв (единственное изменение — §4); изменений
эксперимента ради появившихся наблюдений провайдера; O3 не
исследуется; D-2/D-3/D-4/D-6/EF-12 не открываются; пороги не
двигать после запуска; при B — СТОП (не исправлять).
```

## 9. Вердикты OT (закрыты 11.09)

```
OT-1 PASS: ступени+стоп, продолжающаяся серия;
OT-2 PASS: 4×w1 → 3×noise → 4×w1;
OT-3 PASS → A (observability patch §4);
OT-4 PASS: A-T-1..5 (отсутствие boundary — валидный результат);
OT-5 PASS: независимые границы r1/r2;
ADD: LONG-2 compatibility checkpoint @N=12 (§7 A-T-6).
```

## 10. Процедура

```
FROZEN (этот файл) → PROTOCOL (long3/) → adapter patch (§4) →
preflight → RUN до N=12 → checkpoint @N=12 (gate) →
продолжение до 20/30/50/75 или стоп по первому B →
LONG3_ANALYSIS.txt → LONG3_REPORT.md → решение — отдельным
словом.
```

## 11. Артефакты

LONG3_DESIGN.md (FROZEN), long3/PROTOCOL.md, long3_driver.py,
long3_analyze.py, LONG3_E*_r*.json, LONG3_ANALYSIS.txt,
LONG3_REPORT.md; adapter patch (единственное изменение кода).
O3/cross-series — замороженные candidates.
