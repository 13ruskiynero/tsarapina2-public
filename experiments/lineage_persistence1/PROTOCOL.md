# TSARAPINA LINEAGE-PERSISTENCE-1 (LP-1): PROTOCOL (FROZEN 07.09.2026)

База: LINEAGE_PERSISTENCE1_DESIGN.md (FROZEN 07.09.2026; ревью
профессора: «LP-1 FREEZE ... Прогоны разрешены»). Measurement-only;
v0.6 (knowledge/update/observer/strategy/storage) НЕ изменяется —
ветки F1/F2 исполняются in-process-патчем драйвера; audit sha256
слоёв до/после каждого прогона; полигон без изменений. Ветки внутри
протокола не называются «исправлениями»: это операционализации
persistence (F1: field-bearing pivot; F2: failure-excluded lineage).

## 1. Вопрос и ветки

Вопрос (DESIGN р.1): какая семантика lineage сохраняет приобретённую
applicability-структуру через промежуточное failure-знание?

- F0: v0.6 baseline — без изменений (контроль воспроизводимости AB-1).
- F1 (field-bearing pivot): в _acquire pivot = последний член prior,
  несущий applicable_when; нет field-bearing членов → честный срез.
  Реализация: обёртка update._acquire (временный фильтр _prior_lineage
  на время вызова; после — восстановление).
- F2 (failure-excluded lineage): _prior_lineage не возвращает знания
  по не-success опыту (outcome из context записи; noise → partial).
  Реализация: замена update._prior_lineage (оригинал сохранён).

## 2. Миры и последовательности

w1 (E=absent, V=1, symptom a): fix-a ЛЕЧИТ (success-знание с полем)
wY (E=absent, V=2, symptom a): fix-a ЛЕЧИТ (success-знание с полем)
noise ([a,n], E=absent, V=1): fix-a НЕ лечит (outcome=partial;
знание БЕЗ applicable_when — Q5-эквивалент failure)

Шаги — канонический learn: env_set → collect → действие fix-a
(ctx_extra=E) → executor → evaluation → experience → update.apply.

S0: w1, wY          (контроль без failure)
S1: w1, noise, wY   S2: noise, w1, wY
S3: w1, noise, noise, wY   S4: w1, w1, noise, wY
S5: noise, wY       (предел: нет field-bearing prior)

Грид: 3 ветки × 6 последовательностей × r1/r2 = 36 прогонов.
Данные: data_lp1_<branch>_<seq>_<rep>/ (свежий стор на каждый прогон).

## 3. Регистрация (после КАЖДОГО шага; RAW)

- снапшот latest-версий knowledge стора (id, version, status, content,
  applicable_when, applicability_observations, experience_refs,
  lineage) — промежуточные дефекты не прячутся финальным состоянием;
- на каждом success-шаге ДО apply: prior_ids (активная семантика
  ветки), fb_existed (есть field-bearing член), pivot_id,
  pivot_has_aw; created_knowledge_id шага;
- outcome шага; после финального шага — eligibility-пробы suggest при
  w1/wY/noise (obs_now = E/V): strategy_id, candidate command,
  knowledge_refs (selected knowledge_id), rationale.

## 4. Критерий (DESIGN р.5; терминология: honest ≠ reopened)

- honest: версия с V ∈ aw, созданная при prior БЕЗ field-bearing
  членов (пустой prior или только знания без поля) — Q1-норма;
- reopened (дефект): версия с V ∈ aw, созданная при prior С
  field-bearing членами, но pivot без applicable_when (структура
  обойдена); регистр mech_reopen (путь reopen без fb-членов) —
  НЕ дефект, фиксируется отдельно;
- **главный критерий: reopened == 0 в каждой последовательности
  каждой ветки**; отдельно: honest-счётчик, observations, lineage
  history, selected knowledge_id; latest-уровень (S0–S4): aw=={E:
  absent}, obs V[1,2] disagreement, V ∉ aw(latest).

## 5. Ожидания (сверка в анализе; НЕ критерий прогона)

F0: S1/S3/S4 — reopened 1 (latest {E:absent,V:2}, obs ∅);
S2 — w1-шаг mech_reopen (результат ≡ honest {E:absent,V:1}), wY —
восстановление; S0/S2 latest PASS; S5 — honest {E:absent,V:2}.
F1/F2: reopened 0 везде; S1/S3/S4 latest PASS ({E:absent}+obs
V[1,2]); S0/S2/S5 ≡ F0. F1 ≡ F2 на всех прогонах (лемма 2.1 —
предсказание). Пробы w1 на S1/S3/S4: F0 — старая узкая версия,
F1/F2 — свежайшая широкая (selected knowledge_id различается при
одинаковом S2 fix-a).

## 6. Вердикт (после RAW и анализа)

- F0 воспроизвёл AB-1 (+S0/S5-контроль) → грид валиден;
- F1/F2 дали reopened=0 на S1/S3/S4 → семантика восстанавливает
  перенос инварианта; latest-уровень PASS;
- F1 ≡ F2 подтверждена/опровергнута (лемма 2.1);
- honest-след (V в Q1-срезах) — норма, фиксируется;
- v0.6 остаётся FROZEN; выбор семантики — слово профессора, отдельным
  шагом; «победитель» в отчёте LP-1 не назначается.

## 7. Артефакты

PROTOCOL.md (этот файл, FROZEN), lp_driver.py, lp_analyze.py,
LP1_records_<branch>.json (RAW ×3), LP1_run_<branch>.log,
LP1_audit_<branch>.txt, LP1_ANALYSIS.txt, LINEAGE_PERSISTENCE1_
REPORT.md (после анализа). Слои v0.6 не изменяются.
