# TSARAPINA EVIDENCE-PERMISSION-2B / EP-2B: PROTOCOL (FROZEN
# 10.09.2026)

База: EVIDENCE_PERMISSION2B_DESIGN.md (FROZEN; MP-1 RESOLVED v1).
Measurement-only: слои v0.6.x НЕ изменяются (update/knowledge/
evaluation/strategy.py); адресация — A1-база (strategy_aa.py,
sha 61344099c8f83bd0); вмешательства simulated; audit до/после;
анализ — после полного RAW. HALT — деривация EP-2A (0 новых
прогонов).

## 1. Семантики и реализация

**POOL (pool-фильтр, не halt-постфильтр):** обёртка стора
`FilteredStore(store, exclude_kid)`: метод
`read_knowledge_versions_all()` возвращает список без K; все прочие
методы делегируются. suggest вызывается ТОЛЬКО через обёртку; тот же
selection policy, K просто невидим. Проверки: K ∉ допустимого
множества (K отсутствует в knowledge_refs и в snapshot-refs);
контроль-инъекция без обёртки: K присутствует (выбираем).

**TEMP/v1:** pool-фильтр (как POOL) + slot-состояние:
```
state: excluded_kid=K; slot: none|open|consumed
шаг 1: R/S-триггер → exclusion(K)  [event=exclusion]
после каждого эпизода: если outcome=success и refs[0]∈L и
    refs[0] != K и slot==none и sol ещё не было:
       → event=sol (initiator); slot=open   [однократный]
эпизод со slot=open: контролируемое применение K (forced;
    действие K = known_fix) → event=attempt:
       success → K eligible (обёртка отключается; event=eligible)
                 slot=consumed
       failure → K remains excluded; slot=consumed (no retries)
```
Инварианты (механически проверяются в records):
`attempt.kid==exclusion.kid`; `slot.trigger_ref==exclusion.event_id`;
`sol.step>exclusion.step`; `attempt.step>sol.step`;
`slot consumed ≤ 1`; `success(K-apply) ⇒ slot existed`.

**HALT:** не прогоняется; деривация из EP-2A (те же среды/триггеры).

## 2. Полигон

EP-2A-полигон: w1 (lock.a; fix-a лечит) / w2 (lock.a+lock.q; fix-a
мёртв; fix-aq лечит); шум-вставка lock.n на эпизод; envver — канал
драйвера (V1/V2/V3); линия L=(a, absent, fix-a). Успех = stable_active.

## 3. Истории (7 сред; триггеры как в EP-2A-эквивалентах)

```
SD:      learn w1@V1 → [w2] f@V1 f f                    (триггер C1: после шага 1)
NpD:     learn w1@V1 → f@V1(n) ×3, s                    (триггер C2: после шага 2)
S6bV3:   learn w1@V1, w1@V2 → [w2] f@V3 f f             (триггер C5: после шага 1)
E6S:     learn w1@V1, w1@V2 → [w2] f@V1 f f             (триггер C5: после шага 1)
E6N-V3:  learn w1@V1, w1@V2 → f@V3(n) s s               (триггер C5: после шага 1)
E6N:     learn w1@V1, w1@V2 → f@V1(n) s s               (триггер C5: после шага 1)
C6N:     learn w1@V1 → f@V1(n) s f@V1(n) s s            (триггер C6: после шага 3)
```
C6N: 5 шагов (в EP-2A было 4): добавлен хвост для минимальной
TEMP-структуры (SOL + attempt); триггер-точка та же — после шага 3.
Поведение по семантикам (ожидания структуры, не результатов):
POOL — шаги 4-5: обычные применения (K3→s, s); TEMP — шаг 4:
K3→s = SOL, шаг 5: attempt(K2).

## 4. Регистрация (RAW)

- steps: {step, world, noise, envver, mode(S2/S3/attempt-forced),
  strategy_id, refs/refs_filtered, ref_outcome, action, outcome,
  created_kid};
- events: exclusion (kid, conf, trigger_ref), sol (kid K′, refs),
  slot (kid K, trigger_ref), attempt (kid, result, eligible_after),
  eligible;
- checks: poolled: K ∉ refs (обёртка) и K ∈ refs (без обёртки);
  causality-проверки §1; eligibility-injection (K в допустимом
  множестве после success);
- final_snapshot; audit; r1≡r2.

## 5. Preflight (до RUN; стоп при провале)

1. py_compile; unit-проверки FilteredStore (K исчезает из
   versions_all/snapshot).
2. **P1 (POOL-инъекция):** E6N-POOL смоук: после exclusion K2 —
   suggest(обёртка): выбран K1 (K2 ∉ refs); контроль suggest(без
   обёртки): K2 присутствует/выбран.
3. **P2 (slot-инварианты):** E6N-TEMP смоук: события
   exclusion→sol→slot→attempt(success)→eligible; все causality-
   проверки §1 истинны; негатив: S6bV3-TEMP — sol НЕ наступает
   (нет успехов до конца истории).
4. Якорь: SD/NpD: POOL после exclusion ≡ HALT (пусто → S3);
   TEMP: sol отсутствует, slot не открывается.
5. audit LAYERS_UNCHANGED.

## 6. Грид (48 новых прогонов)

```
POOL: SD, NpD, S6bV3, E6S, E6N-V3, E6N, C6N × R,S × r1/r2 = 28
TEMP: S6bV3, E6S, E6N-V3, E6N, C6N × R,S × r1/r2 = 20
HALT: 0 (деривация EP-2A)
ИТОГО: 48 (при включении SD/NpD-TEMP-контроля — 56; не требуется)
Клетка: python3 ep2b_driver.py --cell "E6N|POOL|R|r1"
```

## 7. Критерии

- Safety (S-среды): K не применяется после exclusion
  (refs[0]==K == 0; при TEMP — до attempt).
- Recovery (N-среды): success после триггерной точки не позже
  baseline.
- TEMP дополнительно: Initiation (sol валиден), Verification
  (attempt ровно один), Recovery (attempt-success → eligible),
  Failure (attempt-failure → excluded, no retries).
- sufficient(right, C) := Safety AND Recovery (раздельно R/S);
  повторения мёртвого действия — вторичная метрика (сравнимость
  с EP-2A).

## 8. Запреты

Без trust-чисел; без TTL/окон/счётчиков; без мутаций исторических
записей; слои не изменяются; strategy_aa не интегрируется; анализ
после полного RAW; «победители» не назначаются; S3→Explore не
трогается.

## 9. Артефакты

PROTOCOL.md (этот файл), ep2b_driver.py, ep2b_analyze.py,
EP2B_cell_*.json (RAW), EP2B_ANALYSIS.txt,
EVIDENCE_PERMISSION2B_REPORT.md. Слои v0.6.x не изменяются.
