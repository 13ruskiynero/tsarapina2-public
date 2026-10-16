# TSARAPINA EVIDENCE-PERMISSION-2C / EP-2C: PROTOCOL (FROZEN
# 10.09.2026)

База: EVIDENCE_PERMISSION2C_DESIGN.md (FROZEN). Measurement-only:
слои v0.6.x не изменяются; адресация — A1 (strategy_aa.py, sha
61344099c8f83bd0); Explore-эпизод и R/S — simulated (EP-1/AA-1-
механики); audit до/после; анализ — после полного RAW.

## 1. Механики

**Explore-эпизод (EP-1-стиль):** при S3-детекции (strategy
suggest → S3 при ПУСТОМ eligible pool ПОСЛЕ exclusion-события)
следующий эпизод контура исполняется как exploration — forced
fix-aq (allowlist EP-1). События: `s3_detected(step)`, затем
`explore(step, action=fix-aq, outcome, new_candidate)`. Explore-эпизод
НЕ является sign-of-life (не член L; mode="explore").

**R/S:** AA-1-семантика (K = последний verified-success член;
исключение из prior_lineage-чтений (R) и suggest (S); POOL-фильтр —
обёртка чтения кандидатов). Permanent в горизонте.

**U5b-стресс (boundary, вне policy):** после exclusion(K2) —
немедленное второе exclusion-событие на sibling K1 (``stress=true``
в записи); обе записи неизменны; проверяется только нулевая
eligible population.

**TEMP (U6a/U6b):** как EP-2B (pool-фильтр + slot-инварианты).
Спецификация: SOL требует success члена L (не fix-aq-линии) и
mode="S2"; explore-эпизод slot не открывает.

## 2. Среды (unit → конструкция шагов фазы)

```
U1  SD-POOL:      [f@V1 w2 | S3 | exp | s]         (4)
U2  SD4-POOL:     [f,f,f@V1 w2 | S3 | exp | s]     (6)
U3  S6bV3-POOL:   [f@V3 w2 | S3 | exp | s@V3]      (4)
U4  N6bV3-POOL:   [f@V3(n) w1 | S3 | exp | s@V3]   (4)
U5a E6N-POOL:     [f@V1(n) w1 | s | s]             (3)
U5b E6N-POOL-dbl: [f@V1(n) w1 | S3 | exp | s]      (4; 2 exclusion)
U6a S6bV3-TEMP:   [f@V3 w2 | S3 | exp | s@V3]      (4)
U6b N6bV3-TEMP:   [f@V3(n) w1 | S3 | exp | s@V3]   (4)
NEG-E6N:          [f@V1(n) w1 | s | s]             (3)
NEG-E6N-V3:       [f@V3(n) w1 | s@V1 | s@V1]       (3)
NEG-E6S:          [f@V1 w2 | f@V1 w2 | f@V1 w2]    (3)
learn: E6-family/N6bV3/U5*/U6b/NEG-E6N(±V3): w1@V1, w1@V2;
       SD/SD4/U1/U2/NEG-E6S: w1@V1.
S-шаги без пометки — suggest-driven; (n) — шум lock.n.
```

## 3. Клетки и арифметика

```
UNIT|SEM|RIGHT|rep; UNIT ∈ {U1,U2,U3,U4,U5a,U5b,U6a,U6b,
                            NEG-E6N,NEG-E6N-V3,NEG-E6S}
CORE (U1..U6b): 8 × R,S × r1/r2 = 32
NEGATIVE:       3 × R,S × r1/r2 = 12
Роле-клетки: 44; U5a ≡ NEG-E6N (общий носитель) → уникальных
прогонов 40. Роль пишется в records («core», «negative»,
«core+negative»).
```

## 4. Регистрация (RAW)

steps (mode S2/S3/explore/attempt, refs/ref_outcome, outcome);
events: exclusion (роль, trigger_ref), exclusion-stress (U5b),
s3_detected, explore (action/outcome/new_candidate), sol/slot/
attempt/eligible (TEMP); checks: pool-инъекции (poolled_excl /
unpoolled_has), post-explore K-невозврат; line_trace;
final_snapshot; audit; r1≡r2.

## 5. Инварианты (testable; из DESIGN §2)

```
после exclusion K не применяется; S3 только при пустом pool;
S3→explore causality; K не становится eligible из-за Explore
(после explore: K ∉ FilteredStore-refs; slot нет);
slot_created_by_explore=False (U6a/U6b);
new candidate ∈ fix-aq-линии (≠ L);
exclusion-история сохранена (число exclusion-событий: U5b=2,
остальные=1); audit; L6; append-only.
NEG: 0 s3_detected, 0 explore; выбор — обычный sibling.
```

## 6. Preflight (до RUN; стоп при провале)

```
1. py_compile; unit: FilteredStore multi-exclusion (U5b).
2. U1-смоук: exclusion → S3 → explore(success) → apply.
3. U4-смоук (живой мир): то же.
4. U5a/NEG-E6N-смоук: 0 explore; sibling применяется.
5. U6b-смоук: explore НЕ создаёт slot; K остаётся excluded.
6. U5b-смоук: 2 exclusion; S3 → explore.
7. audit LAYERS_UNCHANGED.
```

## 7. Вердикт (после RAW; форма EP-2B)

```
explore_activated по средам; causality; инварианты §5;
negative-слой чист; U5b — boundary-результат (не policy-claim);
r1≡r2; sufficient-формулировки НЕ применяются (EP-2C — композиция,
не нового evidence-права); итог — интеграл «алгебры прав» (§2
DESIGN).
```

## 8. Запреты

Не переоткрывать Explore; не смешивать с TEMP verification; без
trust-чисел; без TTL/окон/счётчиков; без мутаций исторических
записей; слои не изменяются; strategy_aa не интегрируется; анализ —
после полного RAW; U5b — boundary.

## 9. Артефакты

PROTOCOL.md (этот файл), ep2c_driver.py, ep2c_analyze.py,
EP2C_cell_*.json (RAW), EP2C_ANALYSIS.txt,
EVIDENCE_PERMISSION2C_REPORT.md. Слои v0.6.x не изменяются.
