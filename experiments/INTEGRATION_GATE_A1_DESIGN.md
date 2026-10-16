# TSARAPINA INTEGRATION GATE (A1 → strategy layer): DESIGN
# (FROZEN 10.09.2026)

**Статус: FROZEN.** Решения профессора по всем восьми точкам §4
внесены (см. §4); добавлены обязательные инварианты §5
(No-new-policy, No-implicit-extension). Принцип:

> **Integration must implement the experimentally established
> permission algebra, not introduce a new policy.**

«Раз уж мы здесь, улучшим Strategy» — запрещено. Цепочка входа:
EP-1 → AA-1 → EP-2A → EP-2B → TEMP-F → EP-2C (все CLOSED).
Слои v0.6.x до gate PASS не изменяются (чистая граница
baseline → integration).

## 1. Цепочка и предмет

```
Evidence → permission        (установлено EP-1/EP-2A/B/TEMP-F/EP-2C;
                              policy / external — НЕ гейт)
permission → mechanism       (A1 gate: реализация и механическая
                              валидация)
```

## 2. Проверки G1–G10 (FROZEN; из вердикта)

```
G1  Addressing: failure-derived knowledge не может самостоятельно
    стать кандидатом через legacy aw=None path.
G2  R/S: право применяется к тому же K, который выбран из
    соответствующей applicability lineage.
G3  POOL: excluded K удалён из eligibility pool; остальные
    eligible candidates продолжают работать.
G4  TEMP: sign-of-life → slot → attempt — только для конкретного
    excluded K.
G5  TEMP failure: attempt → non-success → K remains excluded;
    второго slot автоматически нет.
G6  Empty pool: no eligible candidate → S3 → Explore.
G7  Explore isolation: не восстанавливает excluded K; не создаёт
    TEMP slot; создаёт новый candidate / новую applicability
    lineage.
G8  Non-empty pool: остался eligible candidate → normal selection
    (НЕ S3 → Explore).
G9  Append-only / provenance: исторический K-record не изменяется.
G10 Regression: v0.6.x behavioral anchor эквивалентен baseline там,
    где новая политика не должна менять поведение.
```

## 3. Объём (FROZEN)

**Входит (механическая реализация установленных прав):**
candidate addressing (A1); exclusion eligibility; POOL; TEMP
state/slot; S3 detection; Explore dispatch; provenance и
append-only; механические guards.

**Не входит:** выбор «когда evidence заслуживает R/S» (policy —
внешняя, установлена EP-2A и далее); гейт не превращается в EP-3.

**Семантики:** POOL и TEMP обе реализуются как valid mechanisms,
конфигурация явная (`exclusion_semantics = POOL | TEMP`), gate
обязан прогнать обе. HALT НЕ интегрируется (EP-2A: insufficient).
Никакого «TEMP = recommended / POOL = fallback» (и наоборот).

**Код:** сначала отдельный experimental модуль/ветка; после PASS —
перенос в production layers. v0.6.x до PASS не изменяется — нужна
доказуемая граница `v0.6.x baseline ≡ A1 integration` там, где
новая механика не должна ничего менять.

## 4. Решения по восьми точкам (FROZEN)

```
1. Граница механизм/политика: гейт проверяет ТОЛЬКО механическую
   реализацию уже установленных прав (список §3). Выдача прав —
   external/policy; гейт не выбирает.
2. Код: experimental branch first; production layers после PASS.
3. POOL+TEMP: обе как valid mechanisms; HALT excluded; gate
   прогоняет обе.
4. Среды: не расширять полигон; core (SD/NpD, S6bV3,
   C5-after-exclusion, N6bV3, TEMP success, TEMP failure) +
   controls (E6N, E6N-V3, E6S) + ровно те boundary cases, что
   нужны для G5/G6/G8. Гейт проверяет переносимость уже
   исследованной семантики, не открывает новую ветку.
5. Regression: ДВЕ группы — R0 (существующий полный v0.6.x
   regression anchor; остаётся неизменным) и R1 (targeted для
   permission chain: старый acquisition; applicability; strategy
   v0.6 behavior; legacy knowledge без applicable_when;
   существующие transition-event cases).
6. PASS/FAIL: без статистики (это интеграция, не effect
   experiment). PASS только конъюнкция: G1–G10 PASS + audit clean
   + L6 0 violations + append-only PASS + regression anchor PASS +
   determinism PASS + R ≡ S PASS. Любое нарушение одного
   механического инварианта = FAIL, независимо от остальных
   зелёных. Отдельно: no new behavior outside the experimentally
   authorized permission algebra.
7. Номенклатура: не v0.7. Сначала — «A1 experimental integration»;
   после gate PASS — «v0.6.x+A1». Следующая архитектурная версия —
   только после переноса и полного regression.
8. Арифметика: coverage-oriented, НЕ повторение 40-cell × 2
   semantics. Сначала coverage matrix (G → carrier), затем числа;
   старый эксперимент, уже дающий carrier, не перезапускается без
   необходимости (§PROTOCOL).
```

## 5. Обязательные инварианты

**No-new-policy invariant:**

> **The integration gate MUST NOT introduce, infer, or alter
> evidence-to-permission policy. It may only implement and
> mechanically validate permission semantics established by EP-1,
> EP-2A, EP-2B, TEMP-F, and EP-2C.**

**No-implicit-extension invariant:**

> **Any behavior required by the implementation but not established
> by the frozen experiments is an integration defect or a new
> research question, not an implicit extension of A1.**

(Защита от «логично добавить маленькое правило»: через неделю оно
становится новой теорией, через месяц никто не помнит, откуда.)

## 6. Процедура

```
FROZEN (этот файл) → PROTOCOL (integration_gate/; coverage matrix
→ числа) → gate-driver (experimental module; гейт-режимы; обе
semantics) → preflight (G1..G10-смоуки + R0/R1 anchor) → RUN →
INTEGRATION_GATE_ANALYSIS.txt → INTEGRATION_GATE_REPORT.md →
перенос A1 в production layers (по слову) → v0.6.x+A1.
```

## 7. Артефакты

INTEGRATION_GATE_A1_DESIGN.md (этот файл, FROZEN),
integration_gate/PROTOCOL.md, gate-driver, INTEGRATION_GATE_
ANALYSIS.txt, INTEGRATION_GATE_REPORT.md. До gate PASS слои
v0.6.x не изменяются.
