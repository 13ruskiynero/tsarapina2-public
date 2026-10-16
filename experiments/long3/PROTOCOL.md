# LONG-3 / CONTEXT-THRESHOLD-1: PROTOCOL (FROZEN 11.09.2026)

База: LONG3_DESIGN.md (FROZEN 11.09; OT-1..5 PASS; OT-3 → A;
checkpoint @N=12). Продолжающаяся серия; стоп по первому B;
контекст-механизм не меняется; единственное изменение кода —
adapter observability patch (§2).

## 1. Серия, среды, ступени

```
E0 seed (w1, fix-a); LLM-эпизоды; паттерн (цикл с E1):
  4×w1 | 3×noise | 4×w1 | 4×w1 | 3×noise | ... (блоки повторяются)
Ступени-чекпоинты: N=12 (LONG-2 compatibility gate), 20, 30, 50,
75. Максимум 75 эпизодов на реплику; ранняя остановка по B.
Резюмируемый запуск: --series r1 --upto 12|20|30|50|75
(продолжение с последнего эпизода; после B — продолжение
запрещено).
```

## 2. Adapter observability patch (единственное изменение кода)

```
llm/adapter.py: propose() возвращает дополнительно
  provider_meta = {"prompt_tokens", "completion_tokens",
                   "total_tokens", "prompt_eval_count", "eval_count"}
(фактические поля ответа провайдера; отсутствующие — None);
OpenAI-совместимый endpoint ollama отдаёт usage.prompt_tokens.
Ничего более. Регрессия: существующие тесты/драйверы работают
без изменений (поле опционально); test_llm_adapter прогоняется
после патча.
```

## 3. Эпизод (как LONG-2 + B-детектор)

```
env_set; observer.collect; strategy_before;
knowledge_state_before;
[E0 seed] — как LONG-2;
[E>0] context = build_context(store, prev) (как LONG-2);
  growth-метрики (как LONG-2);
  bridge.invoke → adapter → provider_meta;
  B2a: ok=False + error → BOUNDARY;
  B2b: counter(n) ≤ counter(n−1) при
       context_chars(n) > context_chars(n−1) → BOUNDARY;
       counter = prompt_eval_count or usage.prompt_tokens;
       (None → B2b=None; observation-gap фиксируется)
  B1: K_store − K_context > 0 → BOUNDARY;
  executed → evaluation → experience → update (как LONG-2);
knowledge_state_after; diff; strategy_after; proposal_diff;
B3: для каждого K ∈ context_source: first_seen(K) < n
    (first_seen — из записей серии; нарушение → BOUNDARY);
B4: try/except вокруг эпизода, audit_before==after,
    полнота записи → BOUNDARY;
запись LONG3_E<k>_<series>.json (+ boundary-запись при стопе:
LONG3_BOUNDARY_<series>.json: {type, ep, values, records_cut});
при B — серия останавливается.
```

## 4. Провайдерские наблюдения (формулировка)

```
provider_meta — provider-side signal; САМ ПО СЕБЕ не является
доказательством truncation. Классификация:
  provider_observation → mechanical boundary detector (правило §3
  B2b, зафиксировано до запуска) → B2 = true/false.
Иных сигналов провайдера не добавляем; при их появлении — только
observation, без изменения эксперимента.
```

## 5. Checkpoint @N=12 (LONG-2 compatibility; gate)

```
После E0..E11 (обе реплики): long3_analyze --checkpoint12:
  сравнить с LONG2_E*_<series>.json по полям:
    knowledge_count(after), context_source_n, context_chars,
    context_lines, unique_commands, dup_lines, K_store−K_context,
    L-chain, траектория предложений.
  «Соответствуют там, где протоколы идентичны» (промпт одинаков;
  метаданные на промпт не влияют). Расхождение — фиксировать,
  НЕ подгонять; при расхождении траектории — сравнение по
  префиксу до первого расхождения.
GATE: N≥20 не запускается, пока checkpoint не завершён (PASS
или зафиксированное расхождение).
```

## 6. Критерии

```
A-T-1..6 (см. DESIGN §7). PASS/FAIL-классификация: механизм /
observation / execution finding. «boundary not observed up to
N=75» — валидный результат.
```

## 7. Процедура

```
FROZEN (этот файл) → adapter patch → test_llm_adapter →
preflight (1 живой вызов: provider_meta присутствует) →
RUN r1/r2 до E11 → checkpoint@12 (gate) → при OK: RUN до
20/30/50/75 или стоп по B → LONG3_ANALYSIS.txt →
LONG3_REPORT.md → решение — отдельным словом.
```

## 8. Артефакты

```
long3/PROTOCOL.md (этот файл), long3_driver.py, long3_analyze.py,
LONG3_E*_r*.json, LONG3_BOUNDARY_<series>.json (при стопе),
LONG3_ANALYSIS.txt, LONG3_REPORT.md; adapter patch (с SHA
до/после). Слои (кроме adapter) и experimental-каталоги не
трогаются.
```
