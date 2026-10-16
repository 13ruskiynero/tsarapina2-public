# TSARAPINA EVIDENCE-PERMISSION-2B (EP-2B): DESIGN (FROZEN 10.09.2026)

**Статус: FROZEN.** MP-1 RESOLVED: v1 (verification slot) — по слову
профессора; v2 отклонён (структурно недостижим), v3 отклонён (слишком
слаб — lineage-level semantics). Внесены: initiator definition,
состояния TEMP, инварианты slot, критерии, буквальная матрица и
числа. База: EP-2A CLOSED (HALT измерен; EF-5 CLOSED); AA-1 CLOSED;
EP-1 CLOSED. Слои v0.6.x frozen; A1-ветка — база; вмешательства
simulated; анализ после полного RAW.

## 1. Вопрос

> **What should exclusion mean for a previously verified candidate
> when the world can later recover?**

## 2. Semantics (три клетки)

```
HALT  — исключённый K: при выборе → эпизод отменяется (S3).
POOL  — K исключается из множества допустимых кандидатов suggest;
        работает ТОТ ЖЕ selection policy без K (pool-фильтр; НЕ
        halt-постфильтр).
TEMP/v1 — K исключается из suggest; sign-of-life открывает
        однократный verification slot (право ПРОВЕРИТЬ K); только
        success проверки восстанавливает eligibility. Sign-of-life
        НЕ восстанавливает K.
```

## 3. TEMP/v1: initiator, состояния, инварианты

**Initiator (recheck):** новое verified-success evidence той же
applicability lineage L, принадлежащее другому eligible candidate
K′ ≠ K, ЛИБО независимое verified applicability observation, которое
делает K потенциально применимым. (В текущем полигоне активируется
только путь K′-success; независимый канал отсутствует — заявлен в
semantics, не измеряется.)

**Состояния:**
```
ACTIVE ── R/S ──→ EXCLUDED ── sign-of-life ──→ VERIFICATION-ELIGIBLE
   ↑                                                  │
   │                                          apply K once
   │                                     ┌────────────┴───────────┐
   │                                  success                 failure
   └────────── ACTIVE ────────────────┘           EXCLUDED (без
                                                   автоматических
                                                   повторов)
```
**VERIFICATION-ELIGIBLE ≠ ACTIVE** (иная evidence ≠ permission).

**Инварианты (механические):**
```
verification_slot(K):
    requires: K currently excluded
              initiator is post-exclusion
              initiator ≠ K
              initiator belongs to same L
              slot consumed at most once
success(K) ⇒ slot(K) existed      (никаких успехов K «самих по себе»)
failure(K-attempt) ⇒ remains EXCLUDED; no auto-retries
```
Causality: `exclude → sign-of-life → slot → attempt → eligible` —
строго в этом порядке.

## 4. Критерии

- **Safety:** после exclusion K не применяется самопроизвольно
  (refs[0]==K до slot-attempt == 0).
- **Initiation:** slot открывается только допустимым sign-of-life
  (post-exclusion, K′≠K, same L).
- **Verification:** ровно один контролируемый attempt K на slot.
- **Recovery:** только verified-success attempt возвращает
  eligible(K)=true.
- **Failure:** неудача проверки — remains EXCLUDED, без повторов.
- **sufficient(right, C) :=** Safety(S-история) AND Recovery
  (N-история), раздельно R/S (форма EP-2A; повторения мёртвого
  действия — ВТОРИЧНАЯ метрика, не в sufficient).

## 5. Divergence set и буквальная матрица

```
Среды: S6bV3, E6S | E6N-V3, E6N | C6N | SD, NpD (контроль)
Триггеры: E6-среды — C5 (первый failure при конфликте, шаг 1);
          C6N — C6 (f→s→f, шаг 3); SD — C1 (шаг 1); NpD — C2 (шаг 2)
Права: R, S раздельно; реплики r1/r2

POOL: 14 units (7 сред × 2 права) × r1/r2 = 28 прогонов
      [SD/NpD — контрольные unit'ы: эмпирическое подтверждение
       POOL≡HALT на однокандидатных]
TEMP: 10 достижимых units (5 сред × 2 права; SD/NpD — НЕ
      прогоняются: формально недостижим recheck — нет K′,
      нет sign-of-life → TEMP≡POOL≡HALT) × r1/r2 = 20 прогонов
HALT: 0 новых (деривация EP-2A: HALT измерен на всех этих средах)

ИТОГО: 48 новых прогонов (56, если включить SD/NpD-TEMP-контроль
для полной симметрии — считается избыточным).
```

## 6. НЕ добавляется в B (запретный список)

S3 → Explore; evidence thresholds; trust score; h>3; lineage-wide
retract; tail exclusion; новая applicability semantics;
автоматическое создание нового K при recovery; авто-повторы
verification attempt.

## 7. Запреты

Без trust-чисел; без TTL/окон/счётчиков; без мутаций исторических
записей (append-only events: exclusion / slot / attempt / eligible);
слои v0.6.x не изменяются; strategy_aa не интегрируется; анализ
после полного RAW; «победители» не назначаются.

## 8. Запись событий (records)

Exclusion: `event=exclusion; step; knowledge_id; conf; trigger_ref`.
Sign-of-life: `event=sol; step; knowledge_id (K′); refs`.
Slot: `event=slot; step; knowledge_id (K); trigger_ref (exclusion)`.
Attempt: `event=attempt; step; knowledge_id; result (success/failure);
eligible_after`.
Проверки: `attempt.kid == exclusion.kid`;
`slot.trigger_ref == exclusion.event_id`; `sol.step > exclusion.step`;
`attempt.step > sol.step`; `slot consumed ≤ 1`.

## 9. Процедура

1. FROZEN (этот файл) → PROTOCOL.md (evidence_permission2b/) →
   ep2b_driver.py (база ep2_driver; режимы POOL/TEMP-v1; HALT —
   деривация) → preflight (юниты + смоуки P1: POOL-инъекция;
   P2: slot-инварианты) → RUN 48 → EP2B_ANALYSIS.txt →
   EVIDENCE_PERMISSION2B_REPORT.md.
2. После B — EP-2C (candidate absence → Explore), отдельно.

## 10. Артефакты

EVIDENCE_PERMISSION2B_DESIGN.md (этот файл, FROZEN),
evidence_permission2b/PROTOCOL.md, ep2b_driver.py, EP2B_ANALYSIS.txt,
EVIDENCE_PERMISSION2B_REPORT.md. Слои v0.6.x не изменяются.
