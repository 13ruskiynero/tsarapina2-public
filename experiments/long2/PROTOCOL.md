# LONG-2 / CONTEXT-GROWTH-1: PROTOCOL (FROZEN 11.09.2026)

База: LONG2_DESIGN.md (FROZEN 11.09; OT-1..5 + diagnostic split).
24 runs = 12 эпизодов × 2 реплики. Strategy не трогается; слои
не изменяются; контекст-механизм не оптимизируется.

## 1. Серия и среды

```
Серия r1 (r2 — независимый свежий store):
  E0       seed  w1      fix-a (production path);
  E1..E4   LLM   w1;
  E5..E7   LLM   шум(n);
  E8..E11  LLM   w1.
```

## 2. Эпизод

```
env_set(world, noise); envver="1";
observer.collect; strategy_before = suggest(...);
knowledge_state_before;
[E0] seed fix-a → executor → evaluation → experience → update;
[E1..E11] context = build_context(store, prev) + growth-metrics (§3);
  bridge.invoke(..., grant=True) — живой вызов gemma3:4b;
  если executed → result → evaluation → experience → update;
knowledge_state_after; knowledge_diff;
strategy_after; proposal_diff (observation);
growth-block в запись (§3); запись LONG2_E<k>_<series>.json.
```

## 3. build_context + growth metrics (FROZEN)

```
Выборка/текст — как LONG-1A (все знания задачи symptom=a, любая
команда; сортировка created_at, tie-break kid; prev-строка;
kid/provenance — не в текст).

growth = {
  knowledge_count_after: len(state_after),
  context_source_ids: [...] (ordered, полный),
  context_source_n: len(set(ids)),
  context_chars: len(context_text),
  context_lines: len(context_text.split("\n")),
  unique_commands: len(set(cmd строк знаний)),
  dup_lines: (число строк знаний) - unique_commands,
  stored_knowledge_n: len(state_before при конструировании),
  transported_knowledge_n: context_source_n,
  K_store_minus_K_context: stored - transported,
  deltas: {по каждому пункту N→N-1}}.
ОДИН источник metrics: driver считает при построении context;
analyzer читает из записей (не пересчитывает по-своему).

Оговорка: context_chars — serializer-specific proxy; не token
metric; не интерпретируется как model-context utilization.
```

## 4. Проверки (analyzer)

```
A-G-1  полная запись + audit (24/24);
A-G-2  Knowledge append-only / структурно валиден (removed=[],
       версии не убывают, diff корректен);
A-G-3  context_source_n неубывающий (N→N+1);
A-G-4  L-chain: first_seen(K) < n для всех K ∈ context_source;
A-G-5  ворота/append-only/chain kid→exp→episode + r1≡r2
       (структурные поля).
Growth-таблица (observation): knowledge_count, context_source_n,
chars, lines, unique/dup, stored/transported, K_store−K_context,
Δ; форма роста (линейная/иная) — observation.
Траектория предложений — observation (без must*).
```

## 5. PASS/FAIL

```
PASS = A-G-1..5. FAIL-классификация: механизм / observation /
execution finding. Числа: 24 runs; расширений нет.
```

## 6. Процедура

```
FROZEN (этот файл) → long2_driver.py + long2_analyze.py →
preflight (seed + context-growth dry) → RUN 24 (r1, r2) →
LONG2_ANALYSIS.txt → LONG2_REPORT.md → решение — отдельным
словом.
```

## 7. Артефакты

long2/PROTOCOL.md (этот файл), long2_driver.py, long2_analyze.py,
LONG2_E*_r*.json (24), LONG2_ANALYSIS.txt, LONG2_REPORT.md.
Слои и experimental-каталоги не трогаются.
