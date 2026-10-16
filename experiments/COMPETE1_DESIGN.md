# COMPETE-1: КОНКУРЕНЦИЯ СТАРЫХ ЗНАНИЙ: ДИЗАЙН (FROZEN 11.09.2026)

**Статус: FROZEN.** Вердикт профессора внесён:
OT-1 ACCEPT (без V2-дистанции);
OT-3 ACCEPT (обе K применимы при V=1; формулировка — «At E4, both
previously verified Knowledge lines satisfy the current
applicability predicate under V=1»);
OT-4 ACCEPT (E4 = w1; «selection is measured before outcome can
provide a discriminating signal»);
терминология: **two distinct previously verified Knowledge lines**
(не «independent»: fix-aq структурно = fix-a + дополнительная
операция; независимость не заявляется);
acquisition — operator-controlled setup;
E4: раздельные уровни retrieval → context → selection/strategy →
proposal || permission → execution → consequence;
паттерны — «consistent with», не «mechanism»; 20 runs; N≈404 — не
трогать.

## 1. Вопрос

> **When multiple previously verified Knowledge lines become
> applicable again, how does the current system select among them?**

> **Does the current Strategy/LLM path exhibit a stable selection
> pattern when two distinct previously verified Knowledge lines
> are simultaneously applicable?**

«Current» фиксировано: НЕ trust/ranking/«ум»; D-2 не открывается.

## 2. Факты полигона (проверено)

```
fix-a  = rm lock.a + start        (success в w1: только a)
fix-aq = rm lock.a lock.q + start (success в w2: a+q; и в w1)
Наблюдаемые условия: E, V; миры w1/w2 скрыты от агента.
Обе линии приобретаются при V=1 → aw обоих {E:absent,V:1}.
```

## 3. Конструкции (FROZEN)

```
Линии: K_F = fix-a (success-мир w1); K_G = fix-aq (success-мир w2).

C1 (K_F-first):
  E0 w1/V1  fix-a  [acquisition: operator-controlled] → K_F
  E1 w1/V1  LLM (свободный)
  E2 w1/V1  LLM (свободный)
  E3 w2/V1  fix-aq [acquisition: operator-controlled] → K_G
  E4 w1/V1  LLM — COMPETITION (обе линии retrieved/transported;
            обе satisfy applicability predicate under V=1)

C2 (K_G-first):
  E0 w2/V1  fix-aq [acquisition] → K_G
  E1 w1/V1  LLM
  E2 w1/V1  LLM
  E3 w1/V1  fix-a  [acquisition] → K_F
  E4 w1/V1  LLM — COMPETITION (то же)

× r1/r2 → 4 серии × 5 эпизодов = 20 runs.
Acquisition — setup (гарантия verified success); предмет
эксперимента — E4-selection.
```

## 4. Уровни регистрации E4 (FROZEN; не сливать)

```
RETRIEVAL          K_F/K_G ∈ context_source(E4)  (обе);
CONTEXT            строки обеих в отправленном prompt;
SELECTION/STRATEGY механический выбор exact-пула на E4
                   (strategy_ref_hit: какая линия; ОТДЕЛЬНОЕ
                   наблюдение);
PROPOSAL           proposed action (LLM);
PERMISSION         executed/refused;
EXECUTION          result;
CONSEQUENCE        evaluation.
Случаи: A (strategy→K_F, proposal=fix-a); B (strategy→K_F,
proposal=fix-aq; retrieval ≠ proposal — интересный результат);
C (proposal вне Knowledge — валидно, не насиловать в «выбрал»).
```

## 5. Паттерн-таблица (FROZEN; «consistent with»)

```
1. recency-like  : C1→F, C2→G (последнее приобретённое)
2. dominance K_F : C1→F, C2→F
3. dominance K_G : C1→G, C2→G
4. non-recency   : C1→G, C2→F (первое приобретённое / иной сигнал)
5. unstable      : расхождение r1/r2 (результат, не «добор»)
6. outside       : proposal вне {fix-a, fix-aq} (отдельный слой
                   retrieval ≠ selection ≠ proposal)
Формулировка: «selection is consistent with acquisition-order /
recency-like behavior» — НЕ «обнаружен recency mechanism».
strategy_ref_hit — отдельное механическое наблюдение.
```

## 6. Запреты

```
никаких trust/ranking/confidence/«лучше»; D-2 не открывать; не
интерпретировать выбор как качество/интеллект; контекст-механизм
и слои не менять; boundary N≈404 не трогать; порядок C1/C2 не
усреднять; narrative-leakage gate (E4-промпт — штатный
build_context, без сюжетных маркеров).
```

## 7. Числа (FROZEN)

```
20 runs = 2 конструкции × 2 реплики × 5 эпизодов. Не увеличивать.
```

## 8. Процедура

```
FROZEN (этот файл) → PROTOCOL (compete1/) → compete1_driver.py →
compete1_analyze.py → preflight → RUN 20 → COMPETE1_ANALYSIS.txt →
COMPETE1_REPORT.md → решение (N≈404 / иное) — отдельным словом.
```

## 9. Артефакты

COMPETE1_DESIGN.md (FROZEN), compete1/PROTOCOL.md,
compete1_driver.py, compete1_analyze.py, COMPETE1_E*_*.json (20),
COMPETE1_ANALYSIS.txt, COMPETE1_REPORT.md. Слои и experimental-
каталоги не трогаются.
