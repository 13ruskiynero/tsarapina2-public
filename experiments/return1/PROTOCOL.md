# O3 / RETURN-TO-PREVIOUS-HYPOTHESIS: PROTOCOL (FROZEN 11.09.2026)

База: RETURN1_DESIGN.md (FROZEN 11.09; OT-1..5 + narrative gate).
20 runs = 2 конструкции × 2 реплики × 5 эпизодов.

## 1. Серии и среды

```
RETURN-K:  r1 (K_r1), r2 (K_r2)
  E0 seed w1 V1 (fix-a; ожидание success) → K1
  E1..E3 LLM w2 V2 (свободные эпизоды; proposals — observations)
  E4 LLM w1 V1 (возврат условий)
RETURN-NULL: n1 (N_r1), n2 (N_r2)
  E0 seed w2 V2 (fix-a; ожидание partial; success-знания НЕТ)
  E1..E3 LLM w2 V2 (идентичная структура)
  E4 LLM w1 V1 (тот же)
envver задаётся драйвером (V=1|2); шум не используется;
E1..E3 свободны (без принуждения действий).
```

## 2. Эпизод

```
env_set(world, V); observer.collect;
strategy_before = suggest(obs_now={"E":"absent","V":V});
knowledge_state_before;
[E0] seed fix-a → executor → evaluation → experience → update;
[E>0] context = build_context(store, prev) — ТОТ ЖЕ, что в
  LONG-серии (narrative-leakage gate §7 DESIGN: никаких
  сюжетных маркеров);
  bridge.invoke(живой gemma3:4b) → proposal → permission →
  action → executor;
  если executed → evaluation → experience → update;
knowledge_state_after; diff; strategy_after (с obs_now V);
proposal_diff; audit; запись RETURN1_E<k>_<series>.json.
```

## 3. Retrieval-поля (R0..R5; фиксируются для E4)

```
R0  K1 traceable: kid→experience→episode (chain);
R1  K1 ∈ context_source(E4);
R2  K1-строка в отправленном prompt-тексте (context(E4));
R3  parsed action(E4) == K1.command (совместимость);
R4  executor executed (не refused);
R5  evaluation outcome(E4) записан.
strategy_refs(E4) ∋ K1 — отдельное наблюдение (флаг
"strategy_ref_hit"), НЕ входит в R-лестницу.
Все флаги пишутся в запись E4 (и вычисляются анализатором).
```

## 4. Классификация

```
E4-класс (по высшему достигнутому уровню, с сохранением всех
флагов):
  R5: цепочка полная; R4: permission-класс; R3: proposal-
      совместимость без исполнения; R2: транспортировано без
      proposal-совместимости; R1: retrieved без транспорта;
  R0: только существование.
O3 outcome (анализатор, по конструкции):
  RETURN OBSERVED        = R3 (и выше) в RETURN-K при M-PASS;
  RETURN NOT OBSERVED    = R0..R2 (нет R3) в RETURN-K;
  RETURN AMBIGUOUS       = смешанные/неполные случаи;
  RETURN COUNTERCONTROL  = NULL-серия: E4 action == fix-a
                           (K: не fix-a) — против ожидаемого.
```

## 5. Narrative-leakage check (механический)

```
Анализатор проверяет context(E4) на отсутствие маркеров-фраз
(регистронезависимо): "вернул", "снова", "ранее", "напомина",
"reconsider", "returned", "previously", "again", "success
earlier".
Любое вхождение — FAIL gate (E4-промпт рассказывает сюжет).
(Штатный build_context такие фразы не порождает; проверка —
страховка.)
```

## 6. Механический PASS (M1..M6) и outcome

```
M1  полные записи 20/20; audit clean;
M2  K1 создан только из verified success (RETURN-K);
M3  first_seen(K1) = 0; K1 не пересоздавался в E1..E3;
M4  R0..R5 зафиксированы для E4 всех серий;
M5  append-only/A1/Executor/Evaluation/Update/L-chain чисты;
M6  r1/r2 сопоставлены; divergence — фиксируется.
PROTOCOL PASS = M1..M6. O3 outcome — отдельно (§4).
```

## 7. Сравнение конструкций (анализатор)

```
Таблица E4 (по репликам):
           K: action   NULL: action   интерпретация (§4 DESIGN)
+ R-уровни каждой серии; divergence r1/r2 фиксируется.
Формулировка — «associated with», не causal proof.
```

## 8. Процедура

```
FROZEN (этот файл) → return1_driver.py + return1_analyze.py →
preflight → RUN 20 (4 серии) → RETURN1_ANALYSIS.txt →
RETURN1_REPORT.md → решение — отдельным словом.
```

## 9. Артефакты

return1/PROTOCOL.md (этот файл), return1_driver.py,
return1_analyze.py, RETURN1_E*_*.json (20), RETURN1_ANALYSIS.txt,
RETURN1_REPORT.md. Слои и experimental-каталоги не трогаются.
