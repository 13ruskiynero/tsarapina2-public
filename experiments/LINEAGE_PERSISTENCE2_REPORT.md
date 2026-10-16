# TSARAPINA LINEAGE-PERSISTENCE-2 (LP-2): ОТЧЁТ (07.09.2026)

Дизайн: LINEAGE_PERSISTENCE2_DESIGN.md (FROZEN 07.09, ревью
профессора: 6 уточнений приняты); протокол: lineage_persistence2/
PROTOCOL.md (FROZEN). Прогон: 3 ветки (F0/F1/F2) × 7 последова-
тельностей (S0–S5, S6b; S6a ≡ S1 по построению) × r1/r2 = **42
прогона** → LP2_records_<branch>.json (RAW) → lp2_analyze.py →
LP2_ANALYSIS.txt (анализ только после полного RAW). **v0.6 НЕ
изменялась** (audit sha256 до/после: LAYERS_UNCHANGED=True ×3;
recorder и ветки — in-process-патчи). Полигон без изменений
(noise2 — тот же n-based failure, менялся только envver — уже
наблюдаемый канал). Детерминизм: r1 ≡ r2 на всех 21 паре.

## 1. Что измерялось

Recorder (все ветки): failure-знание получает observations по
frozen-формату: (a) V-change (signal=V, values_seen, relation=
disagreement) — envver эпизода вне значений V, виденных success-ами;
(b) outcome_disagreement (без signal, condition, verdict) — вектор
полностью совпал с aw последнего field-bearing знания. Оба с
source="verified failure". Ветки: F0 — v0.6-семантика; F1 —
field-bearing pivot + перенос failure-obs в obs нового знания
(никогда в aw); F2 — failure-excluded lineage.

## 2. Результаты (r1; r2 идентичен)

```
ветка   S0          S1(=S6a)    S2          S3          S4          S6b
       awC/lv rAw/rL h f/s  (аналогично по столбцам: awC/lv rAw/rL h f/s)
F0     True/PASS 0/0 1 0/1   False/FAIL 1/1 1 1/0   True/PASS 0/0 1 0/1
       False/FAIL 1/1 1 1/0  False/FAIL 1/1 1 1/0   True/PASS 0/1 1 1/0
F1     True/PASS 0/0 1 0/1   True/PASS 0/0 1 1/1    True/PASS 0/0 1 0/1
       True/PASS 0/0 1 1/1   True/PASS 0/0 1 1/1    True/PASS 0/0 1 1/1
F2     True/PASS 0/0 1 0/1   True/PASS 0/0 1 0/1    True/PASS 0/0 1 0/1
       True/PASS 0/0 1 0/1   True/PASS 0/0 1 0/1    True/PASS 0/0 1 0/1
```

(столбцы по порядку: S0, S1, S2, S3, S4, S6b; под каждым — строка
awC/lv rAw/rL h f/s, где awC=aw_clean, lv=latest-уровень, rAw=
reopened_aw, rL=reopened_locus, h=honest, f/s=failure/success-
derived obs; S5 — состояние {E:absent,V:2} honest во всех ветках,
критерий не применяется.)

Ключевые строки latest-знания:

- **F0-S1 (=S6a)**: aw={E:absent, V:2} — V вернулся в condition;
  obs=[D2-запись fail_b] перенесена через pivot-carry. aw_clean=
  False. Дефект AB-1 сохранён, несмотря на recorder: у failure
  (совпавший вектор) не было attributable-сигнала.
- **F0-S6b**: aw={E:absent} — V ушёл в obs (prev-ветка _acquire:
  pivot=failure без поля, но pobs содержит запись signal=V);
  aw_clean=True; obs: V-запись failure-derived (fail=1, success=0);
  reopened_locus=1 при reopened_aw=0 — локалитет pivot'а и дефект
  РАЗОШЛИСЬ.
- **F1 (S1/S3/S4/S6b)**: aw={E:absent} чист везде; obs содержит и
  success-derived (дивергенция V[1,2]), и failure-derived (D2 на
  S1/S3/S4; V-change на S6b) — fail=1, success=1.
- **F2 (S1/S3/S4/S6b)**: aw={E:absent} чист; obs — только
  success-derived (fail=0).

## 3. Вердикт (раздельно Q2 и Q1)

**Q2 (формат/структура) — ПОДТВЕРЖДЕНО:**
F0-S6a(=S1) aw_clean=False (V снова в condition) против F0-S6b
aw_clean=True (V остался в observations) при одном и том же
failure (n-based), одном и том же положении (между success-ами) и
единственном отличии — наличии attributable applicability signal в
failure-записи. Вывод (не сильнее): **поведение F0 зависит не от
того, что запись является failure, а от наличия attributable
applicability signal в этой записи — форматно-структурная граница
текущего механизма.** «Пустота failure» не фундаментальна: failure с
атрибутируемым сигналом (V-change) меняет динамику даже в F0 без
смены семантики lineage; failure без attributable-сигнала (совпавший
вектор, D2) остаётся пустым для условия — и дефект AB-1 сохраняется.
Уточнение механики: дефект AB-1 = переоткрытие через pivot, который
не несёт ни условия, ни attributable-наблюдения; recorder (a)
нейтрализует переоткрытие, когда сигнал атрибутируем (V→obs
prev-веткой), recorder (b) — нет.

**Q1 (дискриминатор F1/F2) — УСТАНОВЛЕН:**
На S1/S3/S4/S6b при ИДЕНТИЧНОМ applicable_when ({E:absent}) ветки
различаются по составу observations: F1 сохраняет failure-derived
записи (D2/V-change с source=verified failure), F2 их структурно не
видит (только success-derived). F1 ≡ F2 сохраняется там, где
failure-наблюдений нет (S0/S2/S5) — лемма LP-1 расширена: ветки
неразличимы тогда и только тогда, когда failure пуст для
acquisition. **Критерий успеха F1 (evidence, не condition) —
ВЫПОЛНЕН:** после S6b aw={E:absent} (не изменился), obs содержит V=
[1,2] с обоими источниками (success-derived + verified failure);
провального исхода (aw={E:absent,V:2}) не возникло ни на одном
прогоне F1. «Победитель» НЕ назначается: дискриминатор подтверждает
архитектурное различие двух моделей истории, выбор семантики —
слово профессора.

**Ответ на научный вопрос (может ли отрицательный опыт быть
носителем applicability-структуры, не становясь источником
condition):** да — в F1 failure-derived наблюдения сохраняются в
applicability_observations (структура) и никогда не входят в
applicable_when (условие); в F0 при attributable-сигнале то же
происходит спонтанно через prev-ветку (V→obs), но без сохранения
источника; в F2 эта возможность исключена по построению. Разделение
knowledge content / applicable_when / applicability_observations
выдержано: отрицательный опыт пишет в третий слой, не во второй.

## 4. Регрессия и поведение

- F0-S1/S3/S4 воспроизводят aw-дефект AB-1 (теперь с D2-obs в
  истории); F0-S0/S2 чисты; S2/S5: recorder молчит (нет success-
  базы для наблюдения) — как LP-1. S0/S5 honest-следы сохранены.
- Пробы: всюду S2 fix-a (поведенческая неразличимость сохранена);
  selected knowledge_id: F0-S1 — w1/noise-пробы выбирают failure-
  знание (aw=None, legacy-путь; корригенда LP-1 подтверждена и под
  recorder-базой); noise2-проба на F0-S1 выбирает узкое
  {E:absent,V:2}; в F1/F2 все четыре мира выбирают свежайшее
  широкое {E:absent}+obs.
- Audit: слои v0.6 не изменялись (3/3); детерминизм r1≡r2 (21/21).

## 5. Артефакты

LINEAGE_PERSISTENCE2_DESIGN.md (FROZEN), lineage_persistence2/
PROTOCOL.md (FROZEN), lp2_driver.py, lp2_analyze.py,
LP2_records_F0/F1/F2.json (RAW, 14 прогонов каждый), LP2_run_
<branch>.log, LP2_audit_<branch>.txt (LAYERS_UNCHANGED=True ×3),
LP2_ANALYSIS.txt, LINEAGE_PERSISTENCE2_REPORT.md (этот файл). Слои
v0.6 не изменялись.

**Следующий шаг (по слову профессора):** выбор семантики lineage
(F1 failure-visible vs F2 failure-excluded) на основании установлен-
ного дискриминатора и архитектурного предпочтения F1 — либо решение
о выпуске v0.6.x. v0.6 остаётся FROZEN до этого слова.

## 6. Слово профессора (архитектурный выбор, 07.09.2026)

**Выбрана F1 (failure-visible lineage) как архитектурная семантика.**
Основание: LP-2 установил, что F1 сохраняет failure-derived evidence
в applicability_observations, оно не превращается в applicable_when,
F2 намеренно отбрасывает эту информацию из acquisition lineage;
при пустом failure ветки эквивалентны, при информативном — расходятся
именно там, где это важно. Семантика: failure может писать в канал
applicability evidence, не имея права самовольно переписывать канал
condition («evidence не является condition»). Разделение:

```
knowledge content
 ├── applicable_when:          что должно быть истинно для применения
 └── applicability_observations: что опыт сообщил о границе применимости
```

**Открытый архитектурный хвост (зафиксирован):** нюанс F0-S6b —
форма applicability может быть правильной, но provenance этой формы —
неправильной или неполной (V-obs failure-derived при success=0).
Следующий уровень качества: система должна позволять восстановить,
ПОЧЕМУ aw стало таким. Вопрос остаётся открытым для integration-фазы.

**Порядок (слово профессора):** v0.6 НЕ меняется. Сначала LP-3
(FAILURE-EVIDENCE-PERSISTENCE) — контроль сохранности выбранной
семантики через несколько поколений lineage; затем отдельный
архитектурный integration design (L1–L5: семантика prior_lineage как
релевантной истории; pivot = последнее field-bearing verified-success
знание; failure-доступность lineage с переносом только в obs;
provenance без потери источника; append-only) + integration gate;
только после него новая версия (v0.6.x).
