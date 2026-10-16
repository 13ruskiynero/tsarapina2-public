# TSARAPINA INTEGRATION GATE: PROTOCOL (FROZEN 10.09.2026)

База: INTEGRATION_GATE_A1_DESIGN.md (FROZEN; 8 решений + инварианты
§5). Measurement-only до PASS: слои v0.6.x НЕ изменяются; механизмы
реализуются в экспериментальном модуле (integration_gate/); после
gate PASS — перенос по слову → «v0.6.x+A1».

## 1. Coverage matrix (G → carrier; ПЕРВИЧНО, числа — из неё)

```
Gate                 Carrier (существующий сценарий)
G1  addressing       AA-1 failure lineage      → N1D-B
G2  R/S object       AA-1 / EP-2A             → E6N-POOL (R/S@C5)
G3  POOL             EP-2B                    → E6N-POOL
G4  TEMP slot        EP-2B                    → E6N-TEMP
G5  TEMP failure     TEMP-F                   → TempF-TEMP
G6  empty pool       EP-2C U1 (и U6b-TEMP)    → SD-POOL; N6bV3-TEMP
G7  Explore isol.    EP-2C U6                 → N6bV3-TEMP
G8  non-empty pool   EP-2C U5a                → E6N-POOL (тот же
                                               носитель, что G2/G3)
G9  append-only      весь EP-2C/TEMP-F        → walk по всем клеткам
G10 regression       v0.6.x anchor (R0) + R1 targeted
```

Старые carrier'ы НЕ перезапускаются дважды: каждый носитель
исполняется один раз на интегрированном модуле; роли G-проверок
навешиваются аналитически (§4). Дубликаты носителей исключены
(E6N-POOL несёт G2+G3+G8 одной серией прогонов).

## 2. Прогоны (числа из матрицы; предложение, фикс до RUN)

```
G-клетки (carrier × rights × r1/r2):
  c1 N1D-B        (G1; без прав)                 2
  c2 E6N-POOL     (G2+G3+G8; R,S)                4
  c3 E6N-TEMP     (G4; R,S)                      4
  c4 TempF-TEMP   (G5; R,S)                      4
  c5 SD-POOL      (G6; R,S)                      4
  c6 N6bV3-TEMP   (G7 (+G6-TEMP); R,S)           4
  G-клетки всего: 22
R1 targeted (доп. носители permission chain, вне G-набора):
  SD4-POOL (2), S6bV3-POOL (2)                   +4
R0 (полный v0.6.x anchor на модуле; сверка с
   GATE_V06X_records_v06x.json):
  S0..S5, S6b, P1, P2 × r1/r2                    18
ИТОГО прогонов гейта: 22 + 4 + 18 = 44
```

Компоненты механизмов на модуле: A1-addressing; exclusion eligibility
(POOL и TEMP как конфигурация `exclusion_semantics`); TEMP state/slot;
S3 detection; Explore dispatch; provenance/append-only; guards.
ВЫДАЧА прав — external (simulated триггеры, как в EP-линии): модуль
не решает, когда evidence заслуживает R/S (No-new-policy).

## 3. Регистрация и проверки (механические)

- события: exclusion/POOL|TEMP; s3_detected; explore; sol/slot/
  attempt/eligible (TEMP); stress-метки где применимо;
- проверки G1–G10 — механический walk (как в EP-2B/2C-анализе):
  addressing (failure-derived ∉ кандидатов при legacy aw=None),
  R/S-объект, POOL-эффект, slot-каузальность, failure→remains,
  S3→Explore, Explore isolation, no-S3/Explore при непустом pool,
  append-only, regression;
- R0: прогон 18 сценариев на модуле, сверка поведения (команды,
  strategy_id, траектории) с GATE_V06X_records_v06x.json — там, где
  новая механика не должна менять поведение;
- R1: targeted (acquisition/applicability/strategy v0.6 behavior/
  legacy aw=None/transition-event cases) на модуле.

## 4. PASS/FAIL (конъюнкция; fail-closed)

```
PASS ⇔ G1–G10 PASS ∧ audit clean ∧ L6 = 0 violations ∧
       append-only PASS ∧ regression anchor (R0+R1) PASS ∧
       determinism PASS ∧ R ≡ S PASS
Любое нарушение одного механического инварианта = FAIL,
независимо от остальных зелёных.
Отдельно: no new behavior outside the experimentally authorized
permission algebra.
```

## 5. Preflight (до RUN; стоп при провале)

```
1. py_compile модуля; unit: конфигурация exclusion_semantics
   (POOL/TEMP); guards.
2. G-смоуки: c1..c6 по одному прогону (r1): события и инварианты.
3. R0-смоук: 2 сценария из v06x-грида — сверка с baseline-записями.
4. audit LAYERS_UNCHANGED; модуль не трогает слои.
```

## 6. Запреты (к §5 DESIGN + протокольные)

No new policy; No implicit extension; HALT не интегрируется; не
выбирать POOL vs TEMP; не «улучшать» Strategy; без trust-чисел; без
TTL/окон/счётчиков; без мутаций исторических записей; анализ — после
полного RAW; гейт не превращается в EP-3; числа фиксируются до RUN.

## 7. Артефакты

PROTOCOL.md (этот файл), integration_gate/gate_module.py +
gate_driver.py, GATE_A1_cell_*.json (RAW), INTEGRATION_GATE_
ANALYSIS.txt, INTEGRATION_GATE_REPORT.md. До gate PASS слои v0.6.x
не изменяются.
