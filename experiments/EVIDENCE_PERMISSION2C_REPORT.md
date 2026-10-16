# TSARAPINA EVIDENCE-PERMISSION-2C (EP-2C): ОТЧЁТ (10.09.2026)

**Статус: CLOSED (слово профессора, 10.09.2026).** Канонический
finding:

> **Finding EP-2C:** When exclusion removes the last eligible
> candidate, candidate absence triggers S3 → Explore. Explore does
> not restore or re-authorize the excluded knowledge item, does not
> create a TEMP verification slot, and produces a candidate on a new
> applicability lineage. When an eligible candidate remains,
> exclusion does not trigger S3 or Explore.

Сохраняемые разделения: `exclusion ≠ evidence`, `Explore ≠ TEMP
verification`, `absence ≠ restoration`. U5b — boundary/stress
observation, без расширения policy claim. Носитель U5a/NEG-E6N
(каноническое число — 40 unique cells):

> **U5a and NEG-E6N share one experimental carrier. The carrier is
> counted once in unique-cell accounting and assigned two analytical
> roles. No duplicate execution was performed because the roles
> impose identical experimental conditions.**

Integration: TEMP не назначается «победителем» — POOL и TEMP обе
sufficient; выбор production semantics (если понадобится) —
отдельный decision experiment (стоимость, recovery latency,
collateral effects). Следующий шаг: Integration Gate (A1 →
strategy layer), принцип «implement the experimentally established
permission algebra, not introduce a new policy».

40 уникальных клеток (32 core-роли + 8 negative; U5a≡NEG-E6N —
общий носитель, роль core+negative); ноль нарушений; audit 40/40;
r1≡r2; R≡S. Слои v0.6.x не изменялись; strategy_aa не интегрируется
(до gate).

Дизайн: EVIDENCE_PERMISSION2C_DESIGN.md (FROZEN);
протокол: evidence_permission2c/PROTOCOL.md (FROZEN).

## 1. Результаты (r1≡r2; R≡S)

```
U1  SD-POOL:      exclusion → S3 → Explore(success) → apply(success)
U2  SD4-POOL:     серия 3 → exclusion → S3 → Explore → apply
                  (1 exclusion; dead-end не возникает)
U3  S6bV3-POOL:   sibling incompatible → empty → S3 → Explore
U4  N6bV3-POOL:   C5-контекст, живой мир → S3 → Explore
U5a E6N-POOL:     K excluded + sibling eligible → S3/Explore
                  НЕ возникают (роль core+negative)
U5b E6N-dbl:      2 exclusion (1 stress) → empty → S3 → Explore
U6a S6bV3-TEMP:   TEMP + empty → S3 → Explore; slot НЕ создан
U6b N6bV3-TEMP:   Explore не восстанавливает TEMP-K; слот не создан
NEG:              E6N-V3, E6S — explore не активирован (0/8)
```

Все explore-события — строго на шаг после `s3_detected` (causality
100%). K-невозврат: после Explore excluded K ∉ пула выбора
(post_explore checks True, 28/28 в explore-клетках). Новый
candidate — fix-aq-линия (≠ L); контур после Explore продолжается
обычным применением.

## 2. Вердикты

- **S3 → Explore** (когда exclusion опустошил eligible pool):
  активирован в U1/U2/U3/U4/U5b/U6a/U6b (28/28 клеток);
- **Нерефлекс:** при непустом pool (U5a, NEG-E6N-V3, NEG-E6S) —
  S3/Explore НЕ активированы (12/12); «после exclusion всегда
  Explore» — опровергнуто;
- **K-невозврат:** Explore не делает excluded K eligible
  (инвариант 5) и не создаёт TEMP slot (инвариант 6; U6a/U6b:
  sol/slot/attempt = 0);
- **U5b (boundary):** double exclusion → реальный empty pool →
  S3 → Explore; помечено stress; вне policy-claim;
- Инварианты 1–10 из DESIGN §2 — выполнены механически (0
  нарушений); exclusion-история сохранена; audit; append-only.

## 3. Алгебра прав (интегральная карта)

```
EVIDENCE
   ├── Explore            (EP-1: permitted verification)
   └── R/S                (EP-2A: permanent; AA-1: адресация)
        ├── HALT          (insufficient: уничтожает recovery)
        ├── POOL          (sufficient; recovery через sibling)
        └── TEMP          (sufficient; восстановление САМОГО K:
              slot → success → eligible
              slot → failure → excluded  [TEMP-F])
                        │
                        ▼
        no eligible candidate (EP-2C)
                        │
                        ▼
                      S3 → Explore — НО:
              excluded K не восстанавливается Explore;
              Explore не создаёт TEMP slot; новый candidate —
              новая линия. Права композиционно разделены.
```

## 4. Наблюдения

1. U6a (мёртвый мир): Explore (fix-aq) — единственный путь
   продолжения после exclusion; TEMP сам по себе не оживает (нет
   sign-of-life) — ровно как в EP-2B; S3 → Explore заполняет этот
   вакуум, не подменяя TEMP.
2. U3/U4: V3-контекст делает sibling неприменимым → пустота пула
   при живой записи sibling'а; Explore находит fix-aq-кандидата —
   «пустота eligible ≠ пустота стора».
3. U5a: наличие excluded K само по себе — не основание для
   Explore; граница «excluded ≠ empty» подтверждена.
4. U5b: even double-exclusion (stress) ведёт к корректной
   композиции S3 → Explore; правда boundary, не policy.

## 5. Открытые вопросы (слово профессора)

1. Статус EP-2C (CLOSED?) и формулировка finding'а.
2. Носитель U5a/ NEG-E6N (40 уникальных vs 44 роле-клеток) —
   достаточно ли пометки двойной роли; дубль-прогон (+4) не
   делался.
3. Следующий шаг: integration gate (A1 → strategy layer) — по
   слову; EP-2C завершён как последний композиционный слой.

## 6. Артефакты

EVIDENCE_PERMISSION2C_DESIGN.md (FROZEN), PROTOCOL.md,
ep2c_driver.py, ep2c_analyze.py, EP2C_cell_*.json (RAW ×40),
EP2C_ANALYSIS.txt, этот отчёт. Слои v0.6.x не изменялись.
