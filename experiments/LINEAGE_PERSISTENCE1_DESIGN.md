# TSARAPINA LINEAGE-PERSISTENCE-1 (LP-1, AB-1-FIX): DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026).** Ревью профессора: «LP-1 FREEZE
после этих трёх уже внесённых уточнений. Прогоны разрешены.»
Три уточнения (S0-контроль, лемма F1≡F2 как предсказание, S5-предел)
входили в DRAFT; формальные правки ревью внесены ниже (терминология
honest/reopened, главный критерий, переименование веток). База:
AB-1 CLOSED (APPLICABILITY_BOUNDARY1_REPORT.md раздел 6); v0.6 FROZEN
(INTEGRATION_V06, GATE 24/24) — эталон, ветка F0.

Эксперимент, а не починка: проверяются ДВЕ ОПЕРАЦИОНАЛИЗАЦИИ
persistence на том же boundary. Внутри протокола ветки НЕ называются
«исправлениями»/fixes: до прогона не установлено, что та или иная
семантика является правильной. «Победитель» по итогам НЕ назначается.

## 1. Вопрос

> Какая семантика lineage должна сохранять приобретённую
> applicability-структуру через промежуточное failure-знание?

AB-1 установил: acquisition переносит инвариант через prior[-1], не
различая знания с applicable_when и без него; failure-знание (без
поля) как последний член линии → переоткрытие условия из контекста
последнего success ({E:absent,V:2} вместо {E:absent} + obs V[1,2]).
LP-1 измеряет, какая семантика prior восстанавливает ACQ-1-инвариант
на S1–S4, и фиксирует, какой ценой (watch: не теряется ли сигнал
failure).

## 2. Ветки (операционализации persistence; НЕ «правильное решение»)

- **F0 = v0.6 baseline (FROZEN, без изменений).** Контроль
  воспроизводимости AB-1 и точка сравнения.
- **F1: field-bearing pivot.** Правило выбора last в _acquire:
  pivot = последний член prior, РЕАЛЬНО несущий applicable_when
  (знания без поля пропускаются как pivot; в перечислении остаются).
  Если field-bearing членов нет — ветка «пусто» (честный срез,
  update.py:137-139).
- **F2: failure-excluded lineage.** _prior_lineage не возвращает
  знания, созданные по не-success опыту (outcome из context записи
  знания; noise → partial). Для verified-success семантика не
  меняется. Failure-знание не является членом lineage-перечисления.

Обе ветки исполняются БЕЗ изменения слоёв: драйвер патчит семантику
в памяти процесса (F1 — обёртка _acquire; F2 — замена
_prior_lineage); файлы v0.6 остаются байт-в-байт (audit sha256
до/после каждого прогона — инвариант AB-1).

### 2.1 Лемма эквивалентности F1 ≡ F2 в полигоне (ПРЕДСКАЗАНИЕ, не решение)

Для линии (sym, E, cmd) с E, наблюдаемым в ctx_extra: каждый
verified-success член линии несёт applicable_when (E ∈ facts →
aw = dict(facts) ≠ ∅); каждый член с aw=None создан не-success'ом
(apply зовёт _acquire только при outcome == "success"). Следовательно
prior_F1 == prior_F2 на всём пространстве линий текущего полигона:
**ожидание — записи F1 и F2 идентичны на всех последовательностях.**

S0–S5 НЕ должны искусственно различать F1 и F2. Это полезное
отрицательное предсказание: LP-1 либо подтвердит эквивалентность
F1/F2 в данном полигоне, либо найдёт контрпример. Если подтвердит —
выбор между ними НЕ является эмпирически разрешимым в LP-1, и тогда
отдельно обсуждается архитектурная семантика: F1 — failure остаётся
членом перечисления lineage, но pivot берётся от последнего
field-bearing knowledge; F2 — failure вообще не является членом
prior_lineage. Это две разные модели истории, даже если текущая
функция выбора выдаёт одинаковый результат. Дискриминирующий
сценарий лежит ВНЕ полигона (член линии с aw=None, не являющийся
failure, либо failure-член с наблюдениями) — открытый вопрос.

## 3. Миры и последовательности

Миры — как AB-1 (полигон без изменений): w1 (E=absent, V=1, symptom a,
fix-a лечит); wY (E=absent, V=2, fix-a лечит); noise ([a,n], E=absent,
V=1, fix-a НЕ лечит, outcome=partial — знание без applicable-поля,
Q5-эквивалент failure). Шаги — канонический learn-путь (env_set →
collect → fix-a с ctx_extra=E → executor → evaluation → experience →
update.apply).

```
S0: w1 → wY          (КОНТРОЛЬ без failure; отсутствовал в AB-1 —
                      декомпозиция store-следа: honest vs reopened)
S1: w1 → noise → wY        (основной; failure между success)
S2: noise → w1 → wY        (failure ДО первого success; самовосстановление)
S3: w1 → noise → noise → wY   (двойной failure)
S4: w1 → w1 → noise → wY       (failure после повторных success)
S5: noise → wY           (предел: нет field-bearing prior — нет
                      приобретённого инварианта, который можно
                      сохранить; F0 = F1 = F2 ожидаемо)
```

Грид: 3 ветки (F0/F1/F2) × 6 последовательностей (S0–S5) × r1/r2 =
36 прогонов. Реплики r1/r2 — конвенция (детерминизм; r1 ≡ r2).

## 4. Регистрация (после КАЖДОГО шага; RAW)

- Полный снапшот latest-версий knowledge стора (knowledge_id, version,
  status, content, applicable_when, applicability_observations,
  experience_refs, lineage) — как AB-1; снапшот ПОСЛЕ КАЖДОГО шага —
  промежуточный дефект нельзя спрятать успешным финальным состоянием
  (append-only trace сохраняется полностью);
- для каждого success-шага: состав prior (active-версии линии на
  момент ДО apply), флаг fb_existed (в prior есть член с
  applicable_when), pivot (id), pivot_has_aw; created_knowledge_id
  шага;
- outcome шага; после финального шага — eligibility-пробы suggest при
  w1/wY/noise: strategy_id, candidate command, **selected knowledge_id**,
  rationale (как AB-1).

## 5. Критерий (ревью профессора; терминология зафиксирована)

> **Honest applicability snapshot ≠ reopened applicability snapshot.**

- **honest (Q1-норма, НЕ дефект):** версия с V ∈ applicable_when,
  созданная при prior БЕЗ field-bearing членов (пустой prior — честный
  срез update.py:137-139; либо prior только из знаний без поля —
  срез эквивалентен honest, результат тот же). V в honest-версии —
  норма: `aw = dict(facts)` первого verified-success честно включает V.
- **reopened (дефект AB-1):** версия с V ∈ applicable_when, созданная
  при prior, СОДЕРЖАЩЕМ field-bearing члены, но pivot (last) взят от
  знания БЕЗ applicable_when — структура обойдена, инвариант не
  перенесён. Переоткрытие из-за failure-pivot.
- **mech_reopen (путь кода, регистр):** шаг, где pivot существовал и
  pivot_has_aw=False, но field-bearing членов в prior не было
  (S2-w1 в F0; S5-wY в F0) — путь кода reopen, результат ≡ honest.
  Фиксируется отдельно, дефектом НЕ является (проверяем не отсутствие
  V вообще, а отсутствие reopening из-за failure-pivot при
  существующей структуре).

**Главный критерий: 0 reopened versions (caused by a prior without
applicability field, при существовавшей field-bearing структуре) —
в каждой последовательности каждой ветки.**

Отдельно измеряются: (1) honest applicability versions (счётчик);
(2) reopened applicability versions (счётчик); (3)
applicability_observations; (4) lineage history; (5) selected
knowledge_id. Буквальный критерий AB-1 «V ∉ aw по всему стору»
ожидаемо FAIL даже на S0/F0 (honest-срез несёт V) — фиксируется в
анализе как недефектный след, дискриминатором не является.

## 6. Предсказания (НЕ результаты; счётчик reopened; mech_reopen — в скобках)

```
сценарий            F0                      F1                        F2
S0 w1→wY            honest (0)              honest (0)                honest (0)
S1 w1→f→wY          reopened (1)            0 reopened (0)            0 reopened (0)
S2 f→w1→wY          промежут. reopen        0 после первого           0 после первого
                    возможен (w1: mech=1,   field-bearing pivot       field-bearing pivot
                    defect=0; wY: 0)        (0)                       (0)
S3 двойной failure  reopened (1)            0 reopened (0)            0 reopened (0)
S4 s→f→s            reopened (1)            0 reopened (0)            0 reopened (0)
S5 noise→wY         honest snapshot (0)     honest snapshot (0)       honest snapshot (0)
```

- S2-уточнение: на промежуточном w1-success в F0 может появиться
  {E:absent,V:1} — это честный первый acquisition после failure
  (prior без field-bearing членов): результат идентичен honest-срезу;
  проверяется не отсутствие V, а отсутствие reopened из-за failure-
  pivot. В F1/F2 после первого field-bearing pivot — 0.
- S5: во всех ветках honest snapshot {E:absent,V:2} — до двух
  verified-success с расходящимся V нет приобретённого инварианта,
  который можно сохранить; «починка», сохраняющая структуру там, где
  она не приобреталась, была бы абсурдом.
- F1 ≡ F2 на всех 36 прогонах (лемма 2.1) — проверяется прогоном.
- Latest-уровень (как AB-1, S0–S4): F0 — S1/S3/S4 FAIL
  ({E:absent,V:2}, obs ∅), S0/S2 PASS; F1/F2 — S1/S3/S4 PASS
  ({E:absent}+obs V[1,2]).
- Пробы w1 на S1/S3/S4: F0 → старая узкая версия ({E:absent,V:1});
  F1/F2 → свежайшая широкая ({E:absent}+obs) — разные selected
  knowledge_id при одинаковом S2 fix-a.
- Watch (информационная значимость failure): в текущем полигоне
  failure-запись структурно бедна (нет applicable-поля, нет
  наблюдений D2) — требовать от F1/F2 сохранения этой информации
  было бы нечестно относительно объекта эксперимента. Измеримо:
  failure-знания остаются в сторе (append-only), опыт-цепочка
  P6-восстановима. Семантическая проверка «failure информационно
  значим» требует варианта записи failure-наблюдений (D2
  outcome_disagreement, acq1_mechanism) — OPEN QUESTION вне core-grid.

## 7. Запреты

- Слои v0.6 (knowledge/update/observer/strategy/storage) НЕ изменяются:
  F1/F2 — только in-process патч драйвера; audit sha256 до/после
  каждого прогона (инвариант AB-1);
- «победитель» F1/F2 по итогам НЕ назначается; ветки не называются
  «исправлениями»; выбор семантики — слово профессора;
- без GT в механизме; полигон без изменений;
- критерии, последовательности и ветки после FREEZE не меняются.

## 8. Процедура

1. DRAFT → ревью профессора → **FREEZE (07.09.2026; прогоны
   разрешены)** — выполнено.
2. lineage_persistence1/PROTOCOL.md (frozen).
3. lp_driver.py: канонический learn (как ab1_driver), ветки F0/F1/F2
   (in-process patch), регистрация снапшотов + prior/pivot/fb_existed
   на success-шаг, eligibility-пробы, audit-hash до/после.
4. RUN: 3 ветки × 6 последовательностей × r1/r2 = 36 прогонов →
   LP1_records_<branch>.json (RAW).
5. lp_analyze.py → LP1_ANALYSIS.txt: критерий раздела 5 (reopened=0)
   по каждой последовательности и ветке; регистры honest/reopened/
   mech_reopen; latest-уровень; сверка F1 ≡ F2; поведенческие маркеры.
6. LINEAGE_PERSISTENCE1_REPORT.md: что каждая семантика сохраняет и
   какой ценой; v0.6 остаётся FROZEN до решения профессора.

## 9. Артефакты

LINEAGE_PERSISTENCE1_DESIGN.md (этот файл, FROZEN),
lineage_persistence1/PROTOCOL.md (frozen), lp_driver.py,
lp_analyze.py, LP1_records_<branch>.json (raw), LP1_run_<branch>.log,
LP1_audit_<branch>.txt, LP1_ANALYSIS.txt,
LINEAGE_PERSISTENCE1_REPORT.md. Слои v0.6 не изменяются.
