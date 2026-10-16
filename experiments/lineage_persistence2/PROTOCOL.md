# TSARAPINA LINEAGE-PERSISTENCE-2 (LP-2): PROTOCOL (FROZEN 07.09.2026)

База: LINEAGE_PERSISTENCE2_DESIGN.md (FROZEN 07.09.2026; ревью
профессора: FREEZE после шести уточнений, все приняты; прогоны
разрешены). Measurement-only; v0.6 (knowledge/update/observer/
strategy/storage) НЕ изменяется — recorder и ветки F1/F2 исполняются
in-process-патчами драйвера; audit sha256 слоёв до/после каждого
прогона; полигон без изменений. Ветки не называются «исправлениями».

**Явная формулировка (мир noise2):** noise2 НЕ является новым типом
мира и не вводит новый механизм. Меняется только envver — уже
наблюдаемый канал, который пишет драйвер. Сам failure остаётся тем
же n-based failure (те же lock-файлы, то же поведение tsasvc).

## 1. Вопросы (verdict раздельно)

- Q1 (дискриминатор F1/F2): состав и происхождение observations при
  одинаковом applicable_when, когда failure несёт наблюдение.
- Q2 (формат/структура): F0-S6a(=S1) vs F0-S6b — пустота failure
  фундаментальна или форматна. Вывод-потолок: «форматно-структурная
  граница текущего механизма».

## 2. База записи и ветки

Recorder (все ветки, in-process): knowledge.create обёрнут; для
не-success исхода (outcome из context записи) failure-знание получает
applicability_observations по frozen-формату (типы a/b, source=
"verified failure"). Recorder ветко-независим: «виденные V» — только
по verified-success членам линии (оригинальная prior_lineage).

- F0: v0.6-семантика lineage (pivot = последний член, включая
  failure с obs).
- F1 (failure-visible lineage): pivot = последний field-bearing;
  observations failure-членов переносятся в obs нового знания ТОЛЬКО
  как applicability_observations, НИКОГДА в applicable_when
  (дедупликация слиянием episode_refs по сигнатуре).
- F2 (failure-excluded lineage): failure-знания не входят в
  prior_lineage — их наблюдения недоступны acquisition через lineage.

## 3. Миры, последовательности, грид

w1 (E=absent, V=1, [a]) — success; wY (E=absent, V=2, [a]) — success;
noise (E=absent, V=1, [a,n]) — partial; noise2 (E=absent, V=2, [a,n])
— partial (тот же n-based failure; envver=2).

```
S0: w1, wY          S1: w1, noise, wY   (= S6a: failure@V1 → (b))
S2: noise, w1, wY   S3: w1, noise, noise, wY
S4: w1, w1, noise, wY   S5: noise, wY
S6b: w1, noise2, wY (failure@V2 → (a))
```

Грид: 3 ветки × 7 последовательностей (S0–S5, S6b; S6a ≡ S1) × r1/r2
= 42 прогона. Данные: data_lp2_<branch>_<seq>_<rep>/ (свежий стор на
каждый прогон). S6c — вне core, не запускается.

## 4. Регистрация (после КАЖДОГО шага; RAW)

- снапшот latest-версий knowledge стора (id, version, status, content,
  applicable_when, applicability_observations, experience_refs,
  lineage) — после каждого шага;
- на success-шагах ДО apply: prior_ids, fb_existed, pivot_id,
  pivot_has_aw; created_knowledge_id шага; на failure-шагах —
  recorder-наблюдения видны в снапшоте созданного знания;
- outcome шага; пробы после финального шага: suggest при w1, wY,
  noise (V=1), noise2 (V=2) — strategy_id, candidate command,
  knowledge_refs (selected knowledge_id), rationale.

## 5. Критерии

1. aw-чистота: V ∉ applicable_when(latest); honest Q1-срезы — норма;
   регистры: reopened_aw (V в aw при pivot без поля и fb-структуре),
   reopened_locus (тот же pivot-локалитет независимо от V), honest,
   mech (как LP-1, locus-метки).
2. obs-состав: записи observations latest-знания по происхождению:
   success-derived (без source) vs failure-derived (source=
   "verified failure"; тип (a): signal=V; тип (b): без signal,
   relation=outcome_disagreement).
3. Критерий успеха F1 (заморожен): failure-наблюдение сохраняется
   как evidence, НО не меняет applicable condition без достаточного
   verified-success основания: aw={E:absent}, obs V=[1,2] c обоими
   источниками после S6b — хорошо; aw={E:absent,V:2} после S6b —
   провал F1.
4. Детерминизм r1 ≡ r2; audit; пробы (вторично).

## 6. Ожидания (сверка в анализе; НЕ критерий прогона)

Q2: F0-S6a(=S1) — aw={E:absent,V:2} (V→cond; D2-obs перенесена) —
aw FAIL; F0-S6b — aw={E:absent} (V→obs prev-веткой) — aw PASS.
Q1: F1 — obs содержит failure-derived (D2 на S1/S3/S4; V-entry на
S6b) при aw={E:absent}; F2 — только success-derived при том же aw.
F0-S1/S3/S4: как AB-1 (aw FAIL) + D2-obs через pivot-carry.
Регрессия S2/S5: recorder молчит (нет success-базы) — как LP-1.

## 7. Вердикт (после RAW и анализа; раздельно Q2 и Q1)

Q2: подтверждено/нет: F0-S6a aw FAIL vs F0-S6b aw clean →
форматно-структурная граница механизма (не «failure пуст по
природе»); вывод не усиливать.
Q1: F1/F2 различаются на S1/S3/S4/S6b по составу observations при
одинаковом aw → дискриминатор установлен; не различаются → лемма
LP-1 расширяется на failure-obs (архитектурный вопрос остаётся).
F1-критерий: evidence-не-condition выполнен/нарушен.
«Победитель» не назначается; v0.6 остаётся FROZEN; выбор семантики —
слово профессора. Анализ — только после полного RAW (все 3 ветки).

## 8. Артефакты

PROTOCOL.md (этот файл, FROZEN), lp2_driver.py, lp2_analyze.py,
LP2_records_<branch>.json (RAW ×3), LP2_run_<branch>.log,
LP2_audit_<branch>.txt, LP2_ANALYSIS.txt,
LINEAGE_PERSISTENCE2_REPORT.md (после анализа). Слои v0.6 не
изменяются.
