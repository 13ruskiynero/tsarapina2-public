# TSARAPINA EVIDENCE-PERMISSION-2C (EP-2C): DESIGN (FROZEN 10.09.2026)

**Статус: FROZEN.** Решения профессора (10.09): U5 → U5a (основной)
+ U5b (boundary/stress; double exclusion, вне core recovery claim);
U6 → оба носителя (S6bV3-TEMP, N6bV3-TEMP); арифметика: 8 units ×
2 права × 2 реплики = 32 core + 3 negative × 2 × 2 = 12 → 44
роле-клетки. R и S остаются раздельными правами (эквивалентность
на предыдущем полигоне не повод удалять). База: EP-1 (Explore =
permitted verification — НЕ переоткрывается); AA-1; EP-2A; EP-2B/
TEMP-F (POOL/TEMP обе sufficient; TEMP operational обе ветки).
Слои v0.6.x frozen; strategy_aa не интегрируется; интеграция A1 —
отдельным gate ПОСЛЕ EP-2C.

**Примечание по носителю U5a:** U5a («K1 excluded + sibling K2
eligible → S3/Explore НЕ возникают») использует носитель, совпадающий
с negative-E6N (то же состояние «excluded K ≠ empty pool»). Клетки
ролей пересекаются: уникальных клеток 40 (32 core-роли + 12
negative-роли − 4 общих); 44 — сумма ролей. Дублирование прогонов
не производится; среда помечается двойной ролью (U5a / negative).
Если профессор потребует буквальные 44 — добавляется дубль-прогон
E6N-носителя (+4, отдельные data-сторы).

## 1. Вопрос

> **What should happen when exclusion removes the last eligible
> candidate?**

```
candidate selection → candidate excluded → no eligible candidate
→ S3 → Explore
```

## 2. Главный инвариант

> **Candidate absence may authorize exploration, but must not
> implicitly restore or re-authorize an excluded knowledge item.**

Раскрытие (механически проверяемое):
```
1.  после exclusion K не применяется;
2.  eligible pool пуст → возникает S3;
3.  S3 (как следствие exclusion) → Explore разрешён;
4.  Explore может найти новый verified-success candidate;
5.  старый excluded K не становится eligible только из-за Explore;
6.  Explore не создаёт TEMP verification slot;
7.  новый candidate принадлежит новой/другой applicability lineage;
8.  история exclusion сохраняется;
9.  audit/L6 чистый;
10. append-only сохраняется.
```

Разделение прав: `Explore ≠ TEMP verification` (отсутствие
применимого знания vs восстановление конкретного K после
sign-of-life).

## 3. Среды и конструкции

```
E6-семейство (learn w1@V1, w1@V2); SD4/SD (learn w1@V1).
N6bV3 (НОВАЯ): learn w1@V1, w1@V2 → phase [w1] @V3:
   f@V3(n) → exclusion(K2); obs_now=V3 → sibling K1{V1} не
   матчит → pool empty → S3 → Explore(fix-aq) → success (живой
   мир). S3 без мёртвого мира.
Explore-эпизод — EP-1-стиль (simulated): по S3-детекции (пустой
eligible pool ПОСЛЕ exclusion) следующий эпизод исполняется как
exploration — fix-aq; события s3_detected / explore; в TEMP-средах
explore-эпизод НЕ sign-of-life и НЕ открывает slot.
U5b (stress): двойное exclusion — после exclusion(K2) выполняется
стресс-событие exclusion(K1) (вне policy-семантики; только
boundary-проверка «нулевой eligible population»).
```

## 4. Policy units (FROZEN)

```
CORE (8 units × R,S × r1/r2 = 32)
U1   SD-POOL:       exclusion единственного → S3 → Explore → apply
U2   SD4-POOL:      persistent (серия 3) → exclusion → S3 → Explore
                    (1 exclusion; без dead-end)
U3   S6bV3-POOL:    sibling incompatible (V3) → empty → S3 → Explore;
                    excluded K2 не eligible
U4   N6bV3-POOL:    C5-контекст → exclusion → absence → S3 → Explore
                    (живой мир)
U5a  E6N-POOL:      K excluded + sibling eligible → NO S3, NO Explore
                    (носитель общий с negative-E6N; двойная роль)
U5b  E6N-POOL-dbl:  K1+K2 excluded (stress) → empty → S3 → Explore
U6a  S6bV3-TEMP:    TEMP + no eligible → S3 → Explore;
                    slot НЕ создаётся; Explore не подменяет TEMP
U6b  N6bV3-TEMP:    Explore не восстанавливает TEMP-K; новый
                    candidate — новая линия

NEGATIVE (3 × R,S × r1/r2 = 12; общие носители с U5a — см. шапку)
E6N, E6N-V3, E6S:   pool не пуст → normal selection → S3/Explore
                    НЕ возникают («не рефлекс»)
```

## 5. Метрики (testable)

```
explore_activated; causality s3_detected → explore;
excluded K: present=False, refs не содержат;
slot_created_by_explore = False (TEMP-среды);
new candidate lineage = fix-aq (≠ L excluded);
exclusion-история сохранена; audit; L6; r1≡r2;
stop/повторы (вторично); U5b: 1 stress-exclusion + 1 exclusion
(роли помечены).
```

## 6. Запреты

Не переоткрывать Explore (EP-1); не смешивать с TEMP verification;
без trust-чисел; без TTL/окон/счётчиков; без мутаций исторических
записей; слои v0.6.x не изменяются; strategy_aa не интегрируется;
анализ — после полного RAW; U5b — boundary, не policy-claim;
интеграция — отдельным gate ПОСЛЕ EP-2C.

## 7. Процедура

```
FROZEN (этот файл) → PROTOCOL (evidence_permission2c/) →
ep2c_driver.py (база ep2b_driver + Explore-эпизод + N6bV3 +
U5b-стресс) → preflight (смоуки: U1-цепочка; U4-живой мир;
U5a-неактивация; U6b-разделение прав; U5b-стресс) → RUN
(40 уникальных клеток; 44 роле-клетки) → EP2C_ANALYSIS.txt →
EVIDENCE_PERMISSION2C_REPORT.md → integration gate → A1.
```

## 8. Артефакты

EVIDENCE_PERMISSION2C_DESIGN.md (этот файл, FROZEN),
evidence_permission2c/PROTOCOL.md, ep2c_driver.py,
EP2C_ANALYSIS.txt, EVIDENCE_PERMISSION2C_REPORT.md. Слои v0.6.x не
изменяются.
