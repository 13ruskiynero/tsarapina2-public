# TSARAPINA EVIDENCE-PERMISSION-2B (EP-2B): ОТЧЁТ (10.09.2026)

**Статус: CLOSED (слово профессора, 10.09.2026).** Решения:
**POOL и TEMP обе зафиксированы как sufficient** на C5/C6 — без
выбора победителя, как НЕ взаимозаменяемые реализации:
*«POOL and TEMP are both sufficient under the tested C5/C6
conditions, but they provide different recovery semantics. TEMP is
the only tested semantics that restores the excluded candidate
itself.»* HALT — insufficient. POOL остаётся валидной semantics
(простота; в production отсутствие попытки воскресить старое знание
может быть преимуществом). TEMP failure branch — отдельный targeted
validation (TEMP-F), НЕ расширение грида. EF-5 остаётся валидным:
EP-2B показывает, что смена exclusion semantics меняет место и
характер recovery failure. Следующая последовательность: TEMP-F →
EP-2C → integration gate → A1 в strategy layer. Разделы 1–7
фиксируют результаты и не пересматриваются.
48 RAW (28 POOL + 20 TEMP), HALT — деривация EP-2A (0 новых).
Preflight: unit FilteredStore, P1 (pool-инъекция), P2 (slot-цепочка),
негатив S6bV3 (sol не наступает), якорь SD (≡HALT). Audit 48/48;
r1≡r2 24/24; L6-чек 212 записей / 0 нарушений. Слои v0.6.x не
изменялись; strategy_aa не интегрируется.

Дизайн: EVIDENCE_PERMISSION2B_DESIGN.md (FROZEN; MP-1=v1);
протокол: evidence_permission2b/PROTOCOL.md (FROZEN).

## 1. Результаты (r1; r1≡r2)

```
Среда    POOL (R, S)                              TEMP (R, S)
SD       exclusion → S3-цепь (пул пуст);          — (формально ≡HALT;
         rec=False; stop=0                          контролем служит POOL)
NpD      exclusion → S3-цепь (пул пуст);          —
         rec=False; stop=0
S6bV3    exclusion → пул пуст (K1 не покрывает    exclusion → то же;
         V3) → S3,S3; rec=False; stop=0            sol не наступает
E6S      K1 → f,f; rec=False; stop=2              K1 → f,f; sol не
                                                   наступает; stop=2
E6N-V3   K1 → success(s2); rec=True; stop=2       K1 → s(s2,SOL) →
                                                   attempt(K2) → s →
                                                   eligible; stop=1
E6N      K1 → success(s2); rec=True; stop=2       то же (полный цикл)
C6N      K3 → success(s4); rec=True; stop=2       K3 → s(s4,SOL) →
                                                   attempt(K2) → s →
                                                   eligible; stop=1
```

TEMP-цикл exclusion→sol→slot→attempt(success)→eligible: 10/10
клеток на E6N-V3/E6N/C6N; инварианты §1 PROTOCOL — все OK;
eligibility-injection: K возвращается в допустимое множество
(present=True). На S6bV3/E6S sol не наступает (нет verified-success
после exclusion) — детерминированно, как предсказано.

## 2. Сравнение с HALT (деривация EP-2A; проверено по RAW)

```
HALT:   E6-семейство и NpD после exclusion → S3-цепь;
        recovery=False; stop=0 (EP-2A: шаги = S3,S3).
POOL/TEMP: на E6N-V3/E6N/C6N recovery=True (мир восстанавливается,
        sibling применяется); на NpD ≡ HALT (пул пуст).
```

Итог: на однокандидатных средах HALT ≡ POOL ≡ TEMP (эквивалентность
подтверждена на POOL эмпирически; TEMP — формально структурно: sol
недостижим — нет K′). На multi-candidate средах POOL/TEMP
восстанавливают recovery, уничтоженный HALT.

## 3. Вердикты

- **Safety (K не применяется после exclusion, все семантики):
  True 48/48.** Механика исключения корректна во всех трёх клетках;
  auto_apply=0.
- **Recovery: POOL=True, TEMP=True** на E6N-V3/E6N/C6N (против
  HALT=False); на SD/NpD = False (≡HALT).
- **TEMP: Initiation/Verification/Recovery — выдержаны:**
  sol валиден (post-exclusion, K′≠K), attempt ровно один
  (attempt_once True), eligible только после verified-success
  attempt; failure-ветка attempt не активирована (все attempt в
  живом мире → success) — остаётся структурной (не измеренной);
  no-retries не потребовался.
- **sufficient(right, C) = Safety ∧ Recovery:**
  POOL: C5 ✓, C6 ✓ (S-стороны: S6bV3/E6S safety ✓; N-стороны:
  E6N-V3/E6N recovery ✓); контроли C1/C2 ✗ (recovery=False, ≡HALT).
  TEMP: C5 ✓, C6 ✓ (полный цикл + возврат eligibility).
- stop_repeats (вторичная): N-среды POOL=2, TEMP=1 (в TEMP третий
  эпизод — classified attempt, не авто-применение); E6S=2/2;
  S6bV3/контроли=0.

## 4. Различие POOL vs TEMP (для слова профессора)

Обе семантики проходят совместный критерий на multi-candidate
средах. Структурные отличия:
- POOL: исключённый K не возвращается никогда (recovery — через
  sibling K1); простая механика (один фильтр).
- TEMP: дополнительно возвращает eligibility K по evidence
  (sign-of-life → однократная проверка → success); это единственная
  из трёх семантик, в которой восстановление мира может вернуть
  САМ проверенный кандидат (а не только обходной путь).
«Победитель» не назначается.

## 5. Наблюдения

1. S6bV3-феномен: в V-дивергентной линии третий вектор (V3) делает
   sibling K1 неприменимым → после exclusion пул пуст → S3-цепь
   (ни повторений, ни восстановления). Exclusion + несовместимый
   вектор = система без кандидатов вообще.
2. E6S: в мёртвом мире sol недостижим (нет success) → TEMP
   вырождается в POOL. Sign-of-life требует живого мира — по
   определению.
3. «Мёртвые повторения» fix-a после exclusion сохраняются в S-средах
   (E6S: 2) — цена того, что sibling K1 сам мёртв; это свойство
   sibling'а, не exclusion.
4. Failure-ветка verification slot'а (attempt-failure → remains
   excluded) в текущих средах не наблюдалась — кандидат на
   отдельную среду.

## 6. Открытые вопросы (слово профессора)

1. Статус EP-2B/интерпретация: POOL и TEMP обе sufficient на
   C5/C6 — фиксировать обе? Приоритет TEMP (возврат K) vs POOL
   (простота)?
2. Нужна ли среда для failure-ветки attempt (verification failure)?
3. Следующий шаг: EP-2C (candidate absence → Explore) или
   интеграционные шаги (A1 gate) — по слову.

## 7. Артефакты

EVIDENCE_PERMISSION2B_DESIGN.md (FROZEN), PROTOCOL.md,
ep2b_driver.py, ep2b_analyze.py, check_l6b.py, EP2B_cell_*.json
(RAW ×48), EP2B_ANALYSIS.txt, этот отчёт. Слои v0.6.x не
изменялись.
