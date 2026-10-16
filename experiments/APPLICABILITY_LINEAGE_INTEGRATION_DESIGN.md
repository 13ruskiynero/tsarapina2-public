# TSARAPINA APPLICABILITY-LINEAGE INTEGRATION (v0.6.x): DESIGN
# (07.09.2026)

**Статус: FROZEN (07.09.2026).** Ревью профессора: FREEZE
(решения по пяти точкам — раздел 6, таблица; все приняты). База:
LP-3 CLOSED (F1 persistence PASS; F0 self-reinforcing; F2 deliberate
exclusion); F1 — выбранная архитектурная семантика (LP-2 §6);
v0.6 FROZEN (GATE 24/24) — не изменяется до самого gate.

Цель: перевести выбранную семантику lineage (F1) в КОНТРАКТ слоя
Update/Knowledge для v0.6.x. Это не патч _prior_lineage: это
фиксация того, какую информацию lineage обязан сохранять и какие
части этой информации имеют право влиять на condition.

## 0. Слои знания (интеграция НЕ должна их свернуть)

```
CONTENT
 ├── APPLICABLE_WHEN             ── eligibility condition
 └── APPLICABILITY_OBSERVATIONS  ── evidence about applicability
      └── PROVENANCE             ── откуда evidence (неотделим от obs)
```

F0-S6b-мотивация (LP-2): одинаковая форма aw == {E:absent} ещё не
означает одинаковую структуру evidence (V-obs failure-derived при
success=0). v0.6.x обязан сохранять различимость последних двух
слоёв навсегда (L4/L6).

## 1. Контрактные требования (L1–L6)

**L1. prior_lineage = релевантная история, а не последняя запись.**
_prior_lineage(store, sym, E, cmd) возвращает полную релевантную
историю acquisition линии (active/conflicted версии, включая
failure-знания), упорядоченную по created_at. Семантика функции:
перечисление истории линии для acquisition И для recorder'а; НЕ
«последняя запись».

**L2. Pivot для applicable_when.** Acquisition выбирает pivot =
ПОСЛЕДНЕЕ field-bearing verified-success знание линии (знание с
applicable_when), НЕ prior[-1] как таковой. Failure-знания в
перечислении остаются (L1), но pivot'ом стать не могут.

**L3. Failure.** Failure остаётся доступным lineage. Перенос строго
однонаправленный:
```
failure.applicability_observations  →  new_knowledge.applicability_observations
failure.applicability_observations  ↛  new_knowledge.applicable_when
```
Recorder failure-наблюдений становится НАТИВНОЙ частью update.apply
для не-success исходов (контракт, не патч). **Критическая граница:
recorder может добавлять evidence, но не может самостоятельно
создавать или изменять applicable_when** (aw пишется только в
success-ветке, по L2-семантике). Инвариант-связка (F0-находка LP-3):
recorder (b) требует совпадения вектора с aw последнего field-bearing
знания — при испорченном aw recorder слепнет; v0.6.x с L2 сохраняет
aw чистым, recorder остаётся зрячим. Деградация-цепочка F0 (форма
спасена → pivot испорчен → recorder слеп → evidence оборван) в v0.6.x
невозможна по построению.

**L4. Provenance не теряется; source — явный enum.** Каждая новая
observation-запись несёт явный source. **Допустимые значения
(закрытый enum, не произвольная строка):**
```
source ∈ {"verified success", "verified failure"}
```
Записи дивергенции успехов получают source="verified success"
(симметрия); записи recorder'а — source="verified failure".
Legacy-правило чтения: source отсутствует → success-derived (старые
записи не ломаются; новые — с явной provenance). Различимость
success/failure сохраняется на ВСЕХ поколениях; episode_refs —
непустые у новых записей.

**L5. Append-only.** Никаких исправлений старых версий. Дефектная
история v0.6 остаётся историей (миграция стора не переписывает);
новые знания v0.6.x получают корректную структуру по контракту.
Никакого backfill'а: legacy-поля не сочиняются (см. L6).

**L6. Structural provenance invariant (слово профессора).**
Знание v0.6.x позволяет МЕХАНИЧЕСКИ восстановить:
- почему V оказался в observations (дивергенция/failure);
- из какого success/failure он пришёл (source + episode_refs);
- какие episode_refs это подтверждают;
- на каком поколении lineage это было приобретено.

**lineage_generation — явное схемное поле** (не вычисление по
created_at: generation — структурное свойство lineage, а не
календарный факт; формула через временной порядок хрупка).
Семантика: для знания, созданного на линии (sym, E, cmd):
```
lineage_generation = 1 + (число предшествующих verified-success
                         членов линии)
```
Success-знание K1 → 1, K2 → 2, ...; failure-знание между поколениями
s и s+1 получает s+1 (поколение, в котором его evidence всплывёт в
success-знании). Поле хранится append-only вместе с Knowledge.
Legacy-записи без поля: НЕ сочинять поколение — `legacy/unknown` для
целей L6 (новые записи не притворяются историческими
реконструкциями).

## 2. Изменения контракта слоя (scope v0.6.x)

1. update.apply:
   - outcome == success: acquisition по L2 (pivot = последний
     field-bearing) + перенос failure-obs членов линии в obs нового
     знания по L3 (дедупликация слиянием episode_refs по сигнатуре —
     как F1 в LP-2/LP-3);
   - outcome != success: recorder (a)/(b) пишет observations
     (frozen-формат) — нативно; aw не создаётся и не изменяется.
2. update._acquire / _prior_lineage: L1/L2-семантика.
3. Схема knowledge: новое поле lineage_generation (по правилу L6;
     legacy — None). Observation entries новых знаний: source из enum
     L4, episode_refs непустые.
4. K1 honest-срез первого success {E:absent,V:1}: НОРМА v0.6.x —
     первая успешная запись честно отражает состояние приобретения;
     история задним числом не переписывается (F1 ≠ переписывание).
5. strategy-слой: НЕ изменяется (поведенческая эквивалентность;
     legacy-путь адресации остаётся; LEGACY_ADDRESSING_CORRECTION —
     отдельная будущая работа, в текущую интеграцию НЕ проникает).

## 3. Вне scope v0.6.x

- F2-семантика (отвергнута);
- LEGACY_ADDRESSING_CORRECTION (стратегическая слепота к
  failure-знанию через legacy-путь — корригенда LP-1 §4; отдельная
  будущая работа; gate проверяет структурную lineage-семантику
  НЕЗАВИСИМО от того, какой legacy candidate случайно спасает
  поведение);
- D2-семантика проб как отдельный механизм (ACQ-1 obs_d2);
- изменение первого среза (K1-норма);
- новые миры/механизмы полигона.

## 4. Ожидаемое поведение на сценариях лаборатории (карта для gate)

Под v0.6.x (реальный код, без патчей) ожидается воспроизведение
K-цепочек F1 из LP-2/LP-3:
- S0–S5, S6a(=S1)/S6b: reopened=0; aw чист на K2+; K1 {E:absent,V:1};
  S6b — obs V[1,2] с обоими источниками; S1 — obs + D2-запись;
- P1/P2: монотонность evidence_signature, рост episode_refs,
  source из enum сохраняется (L4), lineage_generation = 1,2,3,... по
  цепочке (L6);
- поведенческие пробы S2 fix-a идентичны v0.6;
- провал-условие: возвращение V в aw на K2+; потеря failure-derived
  evidence между поколениями; нарушение L4/L6-инвариантов.

## 5. Gate-план (отдельный документ после FREEZE)

INTEGRATION_GATE_V06X_DESIGN.md (отдельный дизайн): реализация
контракта в рабочих слоях → gate-прогоны на РЕАЛЬНОМ коде (без
in-process-патчей): G1 регрессия ACQ-1-инварианта; G2 AB-1-сценарии
(reopened=0, aw чист); G3 LP-2-дискриминатор (failure-derived в obs);
G4 LP-3-persistence (монотонность + lineage_generation-цепочка);
G5 поведенческая эквивалентность; G6 audit + append-only + L6-
механические проверки:
```
для каждой новой applicability observation:
    source явный (из enum L4)
    episode_refs непустые
    lineage_generation восстановим
    origin (success/failure) механически идентифицируем
    applicable_when не содержит failure-derived observation
```
и F0-S6b-подобный случай: форма aw выглядит правильной, но
происхождение evidence неправильное — проверяется отдельно
(в v0.6.x S6b-состояние «aw чист при failure-only V-evidence»
невозможно: obs обязаны нести оба источника).
Детали, критерии PASS/FAIL — в INTEGRATION_GATE_V06X_DESIGN.md.

## 6. Ревью профессора (решения; все приняты — FREEZE)

| Точка                | Решение                                    |
| -------------------- | ------------------------------------------ |
| Success `source`     | Вводим `source="verified success"` (enum)  |
| Failure `source`     | `source="verified failure"` (enum)         |
| L6 generation        | Вводим явное поле `lineage_generation`     |
| Legacy addressing    | Вне v0.6.x (LEGACY_ADDRESSING_CORRECTION)  |
| K1                   | `{E: absent, V: 1}` остаётся нормой        |
| Recorder             | Native contract `(a)/(b)`                  |

Дополнительно: допустимые source — закрытый enum (без «маленького
антропологического музея»); legacy без source читается как
success-derived; legacy без lineage_generation — legacy/unknown (не
сочинять); gate проверяет структурную семантику независимо от
legacy-спасения поведения (G2–G4 на структуре стора).

## 7. Процедура

1. DRAFT → ревью → **FREEZE (07.09.2026; решения таблицы §6
   приняты)** — выполнено.
2. INTEGRATION_GATE_V06X_DESIGN.md (отдельный; критерии G1–G6,
   включая L6-механические проверки) — следующий шаг.
3. Реализация v0.6.x в рабочих слоях (update/knowledge; v0.6
   сохраняется как baseline-копии; ПОСЛЕ FREEZE gate-дизайна, по
   слову профессора).
4. Gate-прогоны → INTEGRATION_V06X_REPORT.md → статус v0.6.x.
   v0.6 не изменяется до самого gate.

## 8. Артефакты

APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md (этот файл, FROZEN),
INTEGRATION_GATE_V06X_DESIGN.md (после FREEZE этого — DRAFT→ревью),
реализация в слоях (после gate-дизайна), INTEGRATION_V06X_REPORT.md.
Слои v0.6 не изменяются до слова профессора.
