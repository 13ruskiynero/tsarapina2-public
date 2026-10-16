# TSARAPINA MIN-MECHANISM-1 / CUT-3: MAPPING + APPLICABILITY + E2 (FREEZE, 12.09.2026)

**Статус: FREEZE (12.09.2026; уточнения Cut-3 приняты; слово
профессора: «Погнали в Cut-3»).** Purpose: третий срез лестницы —
единственный новый механизм: E2-driven transition to exploration.
Слои v0.6.x+A1 не меняются; CAND3 — experimental driver-level
модуль ветки.

## 1. Вопрос

Даёт ли добавление E2-механизма к mapping+applicability
наблюдаемую revision-границу: реакцию на повторяющийся failure,
переход к exploration, приобретение нового решения и
post-revision repeat — при сохранении старого знания?

```text
Cut-1 MAPPING:                Repeat ✓ / Mismatch ✗ / Revision ✗
Cut-2 MAPPING+applicability:  Repeat ✓ / Mismatch ✓ / Revision ✗
Cut-3 MAPPING+applicability+E2: Repeat ? / Mismatch ? / Revision ?
```

## 2. Один новый механизм

**E2 = transition signal:** накопление двух последовательных
non-success **применений** текущей записи → `E2_detected`; тем же
сигналом — `exploration_authorized`; запускается **тот же общий
acquisition mechanism** (BIN до устойчивого success), что был
acquisition в EE-2/MM1.

- E2 **не выбирает действие сам** — новое действие выбирает только
  BIN (фиксированный порядок);
- при BIN-успехе запись **добавляется** (verified success; история
  сохраняется; записи не удаляются; lookup — последняя);
- reject (mismatch) — не «применение» и в fail-streak не идёт;
- streak — в памяти прогона, привязан к condition; сбрасывается при
  успехе.

**Не добавляем:** trust, новую selection policy, D-4, LLM, COMPETE,
изменения production layers.

## 3. Стороны

- **FULL:** как в Cut-2 (без изменений; свежий прогон, четвёртая
  репликация границ).
- **CAND3:** persistent `(condition=symptom, action, result,
  applicable_when)` + fail-streak + E2-переход, как §2. Condition —
  symptom-only.

## 4. Сцена (R1–R9, та же)

```text
R1 acq w1; R2 repeat w1; R3 mismatch (E=present); R4 repeat w1;
R5–R6 A′ fail ×2; R7 E2 → BIN → новое; R8 repeat (revised);
R9 возврат w1.
```

Ожидаемый путь CAND3: R5 fail → R6 fail → R7: `e2_detected` +
`exploration_authorized` + `exploration_started` +
`acquisition_steps` (BIN) + `new_knowledge` (fix-aq) → R8/R9:
cheap exploit.

## 5. Trace — обязательные раздельные поля

Episode-запись CAND3 обязана содержать **отдельно**:

- `e2_detected` (bool);
- `exploration_authorized` (bool);
- `exploration_started` (bool);
- `acquisition_steps` (список команд BIN);
- `new_knowledge` (запись или null);
- `fail_streak_before` (до эпизода).

Не сворачивать в один «event».

## 6. Обязательные границы

Repeat; Mismatch; Revision; **Old K preservation** (после revision
fix-a остаётся в записях — проверка фактом по mapping-файлу);
Failure; post-revision repeat (R8/R9 — 1 действие).

## 7. Preflight — часть протокола (до первого R1)

1. FULL-прибор (как Cut-2: `ctx_extra` → `applicable_when` →
   S3/cm);
2. CAND3 applicability-прибор (record → aw; reject при present);
3. CAND3 E2-прибор (dry-run): 2 non-success → `E2_detected=true`,
   `exploration_authorized=true`; после записи нового — lookup
   возвращает новое; в записях оба действия (fix-a и fix-aq) —
   Old K preservation mechanically confirmed.

Любой пункт false → PREFLIGHT FAIL.

## 8. Артефакты

min_mechanism1/: `mm1_cut3_driver.py`, `mm1_cut3_mapping.py`,
`MM1_CUT3.log`, `MM1_CUT3_trace.jsonl`, `MM1_CUT3_TABLE.md`;
сторы `data_cut3_full/`, `data_cut3_mapping/`.

## 9. Границы

- один полигон (tsasvc, gemma4, драйверные политики);
- CAND3 — минимальный кандидат, не «Царапина минус слои»;
- D-4 / D-selection-1 / COMPETE-2 / R2 / R4 — не трогаются;
- negative results не спасаются; FULL остаётся кандидатом-эталоном
  для сравнения границ.

## 10. FREEZE (12.09.2026)

- новый механизм ровно один: E2-driven transition to exploration;
- E2 не придумывает действие; exploration/action — тот же BIN;
- trace-поля раздельные (§5) — обязательны;
- обязательные границы §6 (включительно Old K preservation);
- ничего из «не добавлять» (trust / selection / D-4 / LLM /
  COMPETE / production);
- Cut-3 — последний шаг лестницы перед сравнением с FULL;
  объединений нет.

**FREEZE: 12.09.2026.**
