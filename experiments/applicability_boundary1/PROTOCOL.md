# TSARAPINA APPLICABILITY-BOUNDARY-1 (AB-1): PROTOCOL (FROZEN 07.09.2026)

База: APPLICABILITY_BOUNDARY1_DESIGN.md (FROZEN 07.09). Measurement-
only; v0.6 (knowledge/update/observer/strategy) НЕ изменяется;
audit-hash слоёв до/после прогона; полигон без изменений.

## 1. Гипотеза (измеряется как есть, НЕ чинится)

failure-знание (без applicable_when) той же линии (sym, E, cmd)
становится prior[-1] для следующего acquisition → pcond={} →
переоткрытие условия из контекста последнего success: после
w1-s → noise-f → wY-s ожидается {E:absent, V:2} вместо {E:absent}
+ obs V [1,2].

## 2. Миры

w1: E=absent V=1 symptom a — fix-a ЛЕЧИТ (success-знание)
wY: E=absent V=2 symptom a — fix-a ЛЕЧИТ (success-знание)
noise: [a,n] E=absent V=1 — fix-a НЕ лечит (failure-знание, без поля)

Все шаги — канонический learn: env_set → collect → действие fix-a
(ctx_extra=E) → executor → evaluation → experience → update.apply.

## 3. Последовательности × реплики

S1: w1, noise, wY         S2: noise, w1, wY
S3: w1, noise, noise, wY  S4: w1, w1, noise, wY
(4 × r1/r2 = 8 прогонов)

## 4. Регистрация (после каждого шага; RAW)

- полный снапшот knowledge-версий стора: knowledge_id, version,
  status, content, applicable_when, applicability_observations,
  experience_refs, lineage addr (sym, ctx, cmd);
- outcome шага; после финального шага — eligibility-пробы: suggest
  при w1/wY/noise (obs_now = E/V мира): strategy_id, candidate
  command, knowledge_refs, rationale.

## 5. Критерий (жёсткий; DESIGN раздел 6)

latest-версия линии (a, absent, fix-a) после каждой
последовательности, где w1 и wY были verified-success:
- applicable_when == {E: absent};
- observations: V values_seen [1,2], relation=disagreement;
- V ∉ applicable_when (по всем версиям стора).

## 6. Вердикт (после RAW и анализа)

Гипотеза подтверждена (S1/S3/S4 FAIL, S2 PASS) = BOUNDARY
«persistence приобретённой структуры под interleaved failure
(после первого acquisition)»; v0.6 остаётся FROZEN; обработка —
отдельным решением. Не подтверждена = гипотеза о _prior_lineage
закрыта.

## 7. Артефакты

PROTOCOL.md (этот файл), ab1_driver.py, AB1_run.log, AB1_records.json
(RAW), AB1_audit.txt, ab1_analyze.py, AB1_ANALYSIS.txt,
APPLICABILITY_BOUNDARY1_REPORT.md (после вердикта).
