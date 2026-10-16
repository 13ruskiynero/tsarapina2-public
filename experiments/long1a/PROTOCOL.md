# LONG-1A: PROTOCOL (FROZEN 11.09.2026)

База: LONG1A_DESIGN.md (FROZEN 11.09; OT-1..5 + L-chain
invariant). 12 runs = 6 эпизодов × 2 реплики. Strategy не
трогается; слои не изменяются.

## 1. Серия и среды

```
Серия r1 (r2 — независимый свежий store):
  E0  seed  w1       fix-a (production path; как LOOP-0);
  E1  LLM   w1;
  E2  LLM   шум (n);
  E3  LLM   шум (n);
  E4  LLM   w1;
  E5  LLM   w1.
```

## 2. Эпизод

```
env_set(world, noise); envver="1";
observer.collect; strategy_before = suggest(...);
knowledge_state_before (проекция: kid → {version, status,
  outcome, aw, gen, cmd, syms});
[E0] seed fix-a → executor → evaluation → experience → update;
[E1..E5] context = build_context(store, prev);
  bridge.invoke(..., grant=True) — живой вызов gemma3:4b;
  если executed → result → evaluation → experience → update;
knowledge_state_after; knowledge_diff = diff(before, after);
strategy_after = suggest(...);
proposal_diff (vs предыдущий LLM-эпизод; observation);
запись LONG1A_E<k>_<series>.json.
```

## 3. build_context (OT-1: расширенный; механически)

```
Выборка: все latest-знания (status ∈ {active, conflicted}),
адрес которых — задача symptom=a (ctx == "absent"), ЛЮБАЯ
команда (strategy._addr_cmd_of; адресация v0.6.x+A1).
Сортировка: created_at, tie-break kid.
Текст:
  "Текущая задача: tsasvc.service inactive symptom=a"
  "Предыдущий эпизод: <команда> → <исход>"
  "Известные результаты (задача symptom=a):"
  "  <команда> → <исход>"   (по строке на знание)
context_source = [kid...] (в порядке вывода; в record).
В текст prompt НЕ попадают: kid, experience_refs, provenance,
strategy internals, служебные ID.
```

## 4. L-chain invariant (проверка)

```
Для каждого эпизода E_n и каждого K ∈ context_source(E_n):
first_seen(K) < n, где first_seen — эпизод первого появления
K в knowledge_diff.added (по записям серии).
Нарушение = FAIL (cause/effect смешать нельзя).
```

## 5. Counters (анализатор; observability)

```
per kid: first_seen_episode; last_used_episode; times_retrieved
(K ∈ context_source); times_actioned (K.cmd == action cmd
эпизода с исполнением); times_verified_success / failure
(outcome эпизода: success → success; partial/failure → failure).
```

## 6. Проверки

```
A-L1-1  полная запись + audit чистый (12/12);
A-L1-2  verified consequence → knowledge_diff (каждый эпизод
        с исполнением: diff.added ∋ created_knowledge_id);
A-L1-3  retrieved-связи восстановимы (counters §5 + context_source
        в записях);
A-L1-4  динамика: для каждого N→N+1: context_source(N+1) содержит
        ≥1 K с first_seen(K) ≤ N (L-chain §4) — цепочка проходит
        механически;
A-L1-5  деградации нет: ворота/append-only/chain kid→exp→episode
        на всех runs;
A-L1-6  r1 ≡ r2 (структурные поля: mode/world/decision/
        strategy_id/diff-counts/context_has_prev/chain-ok).
Observation: proposal_diff (changed==true ≠ PASS; false ≠ FAIL);
accumulation-форма (какие команды/линии растут).
```

## 7. PASS/FAIL

```
PASS = A-L1-1..6. FAIL-классификация: механизм / observation /
execution finding (регистрация).
Числа: 12 runs; расширений нет.
```

## 8. Процедура

```
FROZEN (этот файл) → long1a_driver.py + long1a_analyze.py →
preflight → RUN 12 → LONG1A_ANALYSIS.txt → LONG1A_REPORT.md →
решение о длинной серии — отдельным словом.
```

## 9. Артефакты

long1a/PROTOCOL.md (этот файл), long1a_driver.py,
long1a_analyze.py, LONG1A_E*_r*.json (12), LONG1A_ANALYSIS.txt,
LONG1A_REPORT.md. Слои и experimental-каталоги не трогаются.
