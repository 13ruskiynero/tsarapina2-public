# TSARAPINA MIN-MECHANISM-1 / CUT-2: MAPPING + APPLICABILITY (FREEZE, 12.09.2026)

**Статус: FREEZE (12.09.2026; решения Cut-2 приняты; слово
профессора: «Запускаем именно Cut-2, не Cut-3»).** Purpose:
causal decomposition, второй срез — один добавленный слой поверх
Cut-1. Слои v0.6.x+A1 не меняются; CAND2 — experimental
driver-level модуль ветки.

## 1. Вопрос

> Достаточно ли добавить к persistent action-result mapping
> информацию об условиях применимости, чтобы получить не только
> дешёвый repeat, но и корректный отказ от старого знания при
> mismatch?

Cut-1: `Repeat ✓ / Mismatch ✗ / Revision ✗`.
Cut-2 (гипотеза): `Repeat ? / Mismatch ? / Revision ?`.
Ожидание: `Repeat ✓ / Mismatch ✓ / Revision ✗` — при этом
отсутствие revision у Cut-2 не является недостатком эксперимента.

## 2. Один фактор

Добавляется ровно один слой: `applicable_when` к записи mapping.
Ничего больше:

- без E2; без Explore; без failure-trigger;
- без новой selection policy;
- без LLM involvement; без изменения Strategy;
- без новых правил восстановления.

Condition остаётся **symptom-only** (не `(symptom, E)`).

## 3. Стороны

- **FULL:** v0.6.x+A1 + политика EE-2 + ctx_extra (прибор Run-2) —
  без изменений; свежий прогон (третья репликация границ).
- **CAND2 (MAPPING + applicability):** persistent запись
  `(condition=symptom, action, result, applicable_when={E: obs})`;
  запись — только после verified success; lookup → если
  `applicable_when` не совпадает с текущим наблюдением → **mechanical
  reject** (знание не применяется; ничего вместо — Explore не
  подключается); acquisition — общий BIN до первого verified
  success; обработки failure нет.

## 4. Сцена (R1–R9, та же замороженная)

```text
R1 acq w1; R2 repeat w1; R3 w1+extra (E=present; mismatch);
R4 repeat w1; R5–R8 A′=w2 ×4; R9 w1.
```

Ожидаемая картина Cut-2: Repeat ✓; Mismatch ✓ (reject,
0 действий); Revision ✗ (fix-a ×4 fail); Old K ✓; Failure ✗.

## 5. Preflight — часть протокола (обязательная)

До первого R1 основного прогона, с записью в preflight-артефакт:

1. FULL: `ctx_extra` → `applicable_when` реально создан (Run-2
   проверка, включая S3/cm на mismatch);
2. CAND2: запись реально получает `applicable_when={E: ...}`;
3. CAND2: lookup возвращает запись; `condition=symptom` зафиксирован;
4. CAND2: mismatch **mechanically rejectable** при E=present.

Любой пункт false → PREFLIGHT FAIL; основная серия не запускается.

## 6. Выход

Таблица Cut-2: Механизм × {Repeat, Mismatch, Revision, Old K,
Failure}; сравнение с Cut-1 и FULL. Ожидаемое разложение:
persistent mapping → amortization; +applicability →
applicability-aware rejection; +E2 → revision/exploration
(Cut-3 — отдельно, не объединять).

## 7. Границы

- один полигон (tsasvc, gemma4, драйверные политики);
- CAND2 — минимальный кандидат, не «Царапина минус слои»;
- D-4 / D-selection-1 / COMPETE-2 / R2 / R4 — не трогаются;
- negative results не спасаются; Cut-3 не запускается до
  результата Cut-2.

## 8. Артефакты

min_mechanism1/: `mm1_cut2_driver.py`, `mm1_cut2_mapping.py`,
`MM1_CUT2.log`, `MM1_CUT2_trace.jsonl`, `MM1_CUT2_TABLE.md`,
stores `data_cut2_full/`, `data_cut2_mapping/`.

## 9. FREEZE (12.09.2026; решения Cut-2)

- запускаем именно Cut-2, не Cut-3;
- один фактор: applicable_when поверх persistent mapping; ничего
  больше (no E2 / Explore / failure-trigger / selection policy /
  LLM / Strategy);
- condition остаётся symptom-only;
- сцена R1–R9 сохраняется целиком;
- preflight — часть протокола (пункты §5), до первого R1,
  результат — в preflight-артефакте;
- не ожидаем revision: `Repeat ✓ / Mismatch ✓ / Revision ✗` —
  валидный результат;
- Cut-3 (`MAPPING + E2`) — только после результата Cut-2, отдельно.

**FREEZE: 12.09.2026.**
