# COMPETE-1: PROTOCOL (FROZEN 11.09.2026)

База: COMPETE1_DESIGN.md (FROZEN 11.09). 20 runs = 4 серии ×
5 эпизодов (C1_r1, C1_r2, C2_r1, C2_r2).

## 1. Серии и среды

```
C1 (K_F-first): E0 w1/V1 fix-a [acq] | E1 w1/V1 LLM |
                E2 w1/V1 LLM | E3 w2/V1 fix-aq [acq] |
                E4 w1/V1 LLM [competition]
C2 (K_G-first): E0 w2/V1 fix-aq [acq] | E1 w1/V1 LLM |
                E2 w1/V1 LLM | E3 w1/V1 fix-a [acq] |
                E4 w1/V1 LLM [competition]
envver = "1" везде; шум не используется.
```

## 2. Эпизоды

```
[acq] E0/E3: operator-controlled (forced fix-a / fix-aq),
  прямое исполнение через executor; ожидание verified success
  (факт фиксируется; несоблюдение = M-нарушение).
[LLM] E1/E2/E4: штатный путь: build_context (как RETURN-1;
  narrative-free) → bridge.invoke(живой gemma3:4b) → proposal →
  permission → executor → evaluation → experience → update.
Всё как return1_driver; отличия: две acquisition-формы,
  отсутствие V2-фазы, E4 — фокус.
```

## 3. Регистрация E4 (раздельно)

```
E4.retrieval:   K_F/K_G ∈ context_source (обе);
E4.context:     полный текст; строки обеих линий присутствуют;
E4.strategy:    strategy_before/after refs; strategy_ref_hit —
                какая линия выбрана exact-пулом (механич.);
E4.proposal:    raw + parsed action;
E4.permission:  decision (executed/refused);
E4.execution:   result (exit_code/refused);
E4.consequence: evaluation outcome.
```

## 4. Анализ (compete1_analyze)

```
Уровни §3 для всех 4 E4; Случаи A/B/C;
Паттерн-таблица (§5 DESIGN): пары (C1_x, C2_x) по репликам;
итог: единый паттерн ИЛИ unstable (расхождение r1/r2);
«consistent with»-формулировки; strategy_ref_hit отдельно.
M-проверки:
  M1 20 записей полны; audit 20/20;
  M2 K_F и K_G — оба verified success (distinct kid; E0/E3
     исходы success);
  M3 обе traceable (first_seen=0/3; kid→exp→episode);
  M4 E4: обе retrieved; обе строки в prompt; proposal/
     permission/consequence записаны;
  M5 append-only / L-chain / слои;
  M6 r1/r2 сопоставлены (не выравниваются).
narrative-leak: E4-context без маркеров (список RETURN-1).
```

## 5. Запреты

```
без trust/ranking/D-2; без интерпретации «механизм»; без
изменений контекст-механизма/слоёв; N≈404 не трогать; при
divergence — фиксировать, не добирать прогоны.
```

## 6. Процедура

```
FROZEN (этот файл) → compete1_driver.py + compete1_analyze.py →
preflight (1 acquisition-smoke + 1 выбор-smoke) → RUN 20 →
COMPETE1_ANALYSIS.txt → COMPETE1_REPORT.md → решение — отдельным
словом.
```

## 7. Артефакты

compete1/PROTOCOL.md (этот файл), compete1_driver.py,
compete1_analyze.py, COMPETE1_E*_*.json (20), COMPETE1_ANALYSIS.txt,
COMPETE1_REPORT.md. Слои и experimental-каталоги не трогаются.
