# LONG-2 / CONTEXT-GROWTH-1: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора по OT-1..5 внесён:
OT-1 — 12×2=24 runs; OT-2 — w1 → noise → w1; OT-3 — growth
metrics + context_source_ids + оговорка serializer-proxy;
OT-4 — A-G-1..5 в переформулированном виде (knowledge_count и
context_chars — growth observations, не PASS/FAIL); OT-5 —
trajectory proposals = observation. Добавлен **diagnostic split**
stored vs transported (§4). Strategy не трогается (EF-12 OPEN);
слои не изменяются.

## 1. Вопрос

> **How does longitudinal Knowledge accumulation affect the
> externally constructed context as the episode history grows?**

Мотивация: если driver при N≥10 продолжит включать всю историю
задачи в prompt, внешняя память формально существует, но транспорт
становится ограничен размером контекста. Сначала — измерение; смена
среды — часть траектории, НЕ robustness-гипотеза.

## 2. Что измеряется / что не делается

```
ИЗМЕРЯЕТСЯ:
  G-1  рост Knowledge-состояния (per episode);
  G-2  рост контекста (context_source_ids/n, chars, lines,
       unique_commands, dup_lines);
  G-3  diagnostic split: stored_knowledge_n vs
       transported_knowledge_n (K_store − K_context);
  G-4  L-chain invariant при росте;
  G-5  структурная целостность + r1≡r2.

НЕ ДЕЛАЕТСЯ (запрещено): summarization; ranking; forgetting;
relevance policy; compression; trust; semantic selection; любые
изменения контекст-механизма. O3 не исследуется.
```

## 3. Структура серии (FROZEN)

```
12 эпизодов × 2 реплики = 24 runs:
  E0 seed (w1, fix-a); E1..E4 w1; E5..E7 шум(n); E8..E11 w1.
Рост Knowledge гарантирован при любых исходах (update.apply
создаёт знание и на success, и на non-success).
```

## 4. Growth metrics (FROZEN; per episode)

```
knowledge_count (state_after: число записей);
context_source_ids  (ПОЛНЫЙ ordered list транспортированных kid);
context_source_n    (= len(unique(context_source_ids)));
context_chars; context_lines;
unique_commands; dup_lines;
stored_knowledge_n      (знаний в store на момент конструирования);
transported_knowledge_n (= context_source_n);
K_store_minus_K_context;
Δ по каждому пункту N→N+1.

Оговорка (FROZEN): context_chars measures serialized character
length under the frozen context serializer; it is NOT a
token-count estimate and is NOT interpreted as model-context
utilization.
```

## 5. Критерии (FROZEN)

```
A-G-1  complete episode records + audit (24/24);
A-G-2  Knowledge state is append-only / structurally valid;
A-G-3  context_source_n неубывающий (при frozen retrieval scope и
       отсутствии удаления знаний из store);
A-G-4  L-chain remains recoverable for every transported item
       (first_seen(K) < n);
A-G-5  permission / append-only / provenance gates intact +
       r1≡r2 (структурные поля).
Growth observations (НЕ PASS/FAIL): knowledge_count, context_chars,
форма роста, diagnostic split K_store − K_context, траектория
предложений (proposal/proposal_diff/action/outcome — как в
LONG-1A: никаких «must change/improve/converge»).
PASS = A-G-1..5.
```

## 6. Запреты

```
никаких summarization/ranking/forgetting/compression/trust/
semantic selection; никаких изменений контекст-механизма,
strategy.py и слоёв; D-2/D-3/D-4/D-6/EF-12 не открываются;
расширения длины — отдельным словом.
```

## 7. Процедура

```
FROZEN (этот файл) → PROTOCOL (long2/) → long2_driver.py →
long2_analyze.py → preflight → RUN 24 → LONG2_ANALYSIS.txt →
LONG2_REPORT.md → решение (O3 / cross-series / что делать с
растущим контекстом) — отдельным словом.
```

## 8. Артефакты

LONG2_DESIGN.md (FROZEN), long2/PROTOCOL.md, long2_driver.py,
long2_analyze.py, LONG2_E*_r*.json (24), LONG2_ANALYSIS.txt,
LONG2_REPORT.md. Слои и experimental-каталоги не трогаются.
