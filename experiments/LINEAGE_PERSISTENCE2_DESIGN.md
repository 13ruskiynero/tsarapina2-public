# TSARAPINA LINEAGE-PERSISTENCE-2 (LP-2): DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026).** Ревью профессора: FREEZE после
шести уточнений (см. раздел 9 — все приняты). Прогоны разрешены.
База: LP-1 CLOSED (LINEAGE_PERSISTENCE1_REPORT.md; F1 ≡ F2 12/12,
F0 воспроизводит AB-1); v0.6 FROZEN (GATE 24/24) — эталон; слои v0.6
не изменяются (все варианты — in-process-патчи драйвера). F1 НЕ
объявлен победителем заранее: архитектурное предпочтение
зафиксировано, LP-2 должен иметь возможность его опровергнуть.

## 0. Карта (статусы)

```
ACQ-1  → applicability structure can be acquired
v0.6   → acquired structure affects behavior
AB-1   → BOUNDARY: intermediate failure can break lineage persistence
LP-1   → F1: field-bearing pivot | F2: failure-excluded prior
         → 12/12 equivalent (в текущем полигоне)
         → ARCHITECTURAL QUESTION (приоритет F1 — предпочтение,
           НЕ экспериментальный факт)
LP-2   → failure carrying applicability information (этот дизайн,
         FROZEN) — дискриминатор F1/F2 + вопрос формата
```

## 1. Вопросы (verdict — РАЗДЕЛЬНО, раздел 7)

**Q1 (дискриминатор F1/F2):** различаются ли ветки, когда
failure-знание несёт applicability-наблюдение? Проверяется ТОЛЬКО
состав и происхождение applicability_observations при одинаковом
applicable_when.

**Q2 (формат/структура):** пустота failure для acquisition —
фундаментальное свойство или следствие бедного формата записи?
Проверяется парой F0-S6a(=S1) против F0-S6b. Вывод-потолок:
«форматно-структурная граница текущего механизма»; НЕ делать вывод
«failure пуст по природе».

Три различные вещи (не смешивать): knowledge content; applicable_when;
applicability_observations. Disagreement не должен автоматически
становиться condition (ACQ-1).

## 2. Ветки (операционализации; НЕ «исправления»)

Общая база записи (одинакова во ВСЕХ ветках): **failure-observation
recorder** — in-process-патч knowledge.create (через update.apply для
не-success исхода): failure-знание получает applicability_observations
по frozen-формату (раздел 3). Recorder ветко-независим: множество
«виденных V» строится только по verified-success членам линии (есть
во всех ветках). Расхождение веток — ТОЛЬКО семантика lineage:

- **F0**: v0.6-семантика: pivot = последний член prior, включая
  failure-знание с наблюдениями. Контроль: что делает дефект AB-1,
  когда failure перестал быть пустым.
- **F1 (failure-visible lineage)**: pivot = последний field-bearing
  член (LP-1 F1). Оговорка профессора (принята): failure остаётся в
  lineage, но его observations могут переноситься в новое знание
  ТОЛЬКО как applicability_observations, НИКОГДА не становясь
  applicable_when. Перенос: obs-записи failure-членов линии
  переносятся в obs нового знания (КАК ЕСТЬ, с source; дедупликация
  слиянием episode_refs по сигнатуре без episode_refs), если их
  signal не вошёл в condition. Так не смешиваются «что делает знание
  применимым» и «что система наблюдала о границе применимости».
- **F2 (failure-excluded lineage)**: failure-знания не входят в
  prior_lineage (LP-1 F2) — их наблюдения структурно недоступны
  acquisition через lineage; физически знания остаются в сторе.

## 3. Frozen-формат failure-наблюдения (подтверждён профессором)

Оба типа с полем `"source": "verified failure"`; recorder идентичен
во всех ветках:

- **(a) V-change (D1-негатив)** — envver эпизода ∉ множеству V,
  виденных в линии по SUCCESS-членам (aw/obs), и множество непусто:
  ```
  {"signal": "V",
   "values_seen": [<виденные success-ами V> + <текущий V>],
   "relation": "disagreement",
   "source": "verified failure",
   "episode_refs": [<текущий опыт>]}
  ```
- **(b) outcome_disagreement (D2, ACQ-1)** — вектор эпизода (E, V)
  ПОЛНОСТЬЮ совпал с applicable_when последнего field-bearing знания
  линии, вердикт != success (сигнала-расхождения нет):
  ```
  {"relation": "outcome_disagreement",
   "condition": {<aw последнего field-bearing знания>},
   "verdict": "<outcome>",
   "source": "verified failure",
   "episode_refs": [<текущий опыт>]}
  ```

Приоритет: (a) если V новый (и база непуста); иначе (b) если полное
совпадение с aw; иначе записи нет (failure до первого success или без
базы — честно пуст, как LP-1). Пара (a)/(b) разделяет: failure с
атрибутируемым applicability-related сигналом против failure только с
фактом расхождения outcome.

## 4. Миры и последовательности

Миры — как LP-1 + шумовой шаг с envver=2. **Явная формулировка
(протокол): noise2 НЕ является новым типом мира и не вводит новый
механизм. Меняется только envver — уже наблюдаемый канал, который
пишет драйвер. Сам failure остаётся тем же n-based failure (те же
lock-файлы, то же поведение tsasvc). Полигон не изменяется.**

```
w1:  E=absent, V=1, [a]     — success
wY:  E=absent, V=2, [a]     — success
noise:  E=absent, V=1, [a,n] — partial (n-based failure)
noise2: E=absent, V=2, [a,n] — partial (тот же n-based failure)
```

Последовательности (core; S6c — ВНЕ core, не запускается):

```
S0: w1 → wY            (контроль без failure)
S1: w1 → noise → wY    (= S6a: failure@V1, совпал с aw → запись (b);
                        имя S6a закреплено за парой в Q2; S6a ≡ S1)
S2: noise → w1 → wY    (failure до первого success — recorder молчит)
S3: w1 → noise → noise → wY   (двойной failure@V1 → две записи (b))
S4: w1 → w1 → noise → wY
S5: noise → wY         (предел)
S6b: w1 → noise2 → wY  (failure@V2 с изменением V 1→2 → запись (a))
```

Грид: 3 ветки × 7 последовательностей (S0–S5, S6b; S6a ≡ S1) × r1/r2
= **42 прогона**. Анализ — только после полного RAW.

## 5. Регистрация (после КАЖДОГО шага; RAW)

Полный снапшот knowledge-версий стора после каждого шага
(append-only); на success-шагах ДО apply: prior_ids, fb_existed,
pivot_id, pivot_has_aw, created_knowledge_id; на failure-шагах:
записанные recorder'ом наблюдения (тип a/b); outcome шага. Пробы
после финального шага: suggest при w1, wY, noise (V=1), noise2 (V=2):
strategy_id, candidate command, selected knowledge_id (с aw),
rationale.

## 6. Измерения

1. **aw-чистота**: V ∉ applicable_when(latest); V ∉ aw версий,
   созданных при существовавшей field-bearing структуре (honest
   Q1-срезы — норма; регистры honest/reopened/mech как LP-1 —
   locus-метки).
2. **obs-состав (ядро)**: записи observations по происхождению:
   success-derived (без source; дивергенция/перенос по success-цепи)
   vs failure-derived (source=verified failure; типы (a)/(b));
   values_seen; relation; episode_refs.
3. **Критерий успеха F1 (заморожен заранее)**: failure-наблюдение
   сохраняется как EVIDENCE, но НЕ меняет applicable condition без
   достаточного verified-success основания:
   - хорошо: aw={E: absent}; obs: V=[1,2] c источниками verified
     success И verified failure (после S6b);
   - провал F1: aw={E: absent, V: 2} после S6b — failure снова стал
     condition (assert: у F1 V не может войти в aw через failure —
     конструкция исключает, критерий проверяется).
4. Детерминизм r1 ≡ r2; audit sha256 до/после; пробы (вторично).

## 7. Предсказания (НЕ результаты; verdict раздельно)

По чтению update.py:_acquire (при pivot без поля: факт V → в cond,
ЕСЛИ в pobs pivot'а нет записи signal=V; иначе → в obs prev-веткой).

**Q2 — формат/структура (F0):**
```
S6a(=S1): failure@V1, запись (b) без signal:
  F0: pivot=failure → V-записи signal=V нет → V→cond →
      latest aw={E:absent,V:2} → aw-чистота FAIL
      (дефект AB-1 сохраняется: формат не спасает — сигнала нет);
      D2-запись переносится в obs (signal ∉ diverged).
S6b: failure@V2, запись (a) с signal=V:
  F0: pivot=failure → prev-obs signal=V ЕСТЬ → V→obs (merge) →
      latest aw={E:absent} → aw-чистота PASS
      (формат смягчает дефект без смены семантики lineage);
      V-obs failure-derived (success-дивергенции не было).
Q2-вывод (если подтвердится): поведение F0 зависит не от того, что
запись — failure, а от наличия attributable applicability signal в
этой записи → форматно-структурная граница механизма. Не сильнее.
```

**Q1 — F1 vs F2 (состав obs при одинаковом aw):**
```
S6a(=S1)/S3/S4 (D2-записи на failure-членах):
  F1: aw={E:absent} (PASS), obs = V[1,2] success-derived + D2-записи
      failure-членов;
  F2: aw={E:absent} (PASS), obs = V[1,2] success-derived только.
S6b (запись (a)):
  F1: aw={E:absent}, obs: V-запись success-derived + V-запись
      failure-derived (два источника);
  F2: aw={E:absent}, obs: V-запись success-derived только.
→ если подтвердится: настоящий эмпирический discriminator между
двумя семантиками (в LP-1 их было не различить).
```

Регрессия S0–S5: aw-ожидания как LP-1 (F0: S1/S3/S4 aw FAIL; F0-S2/S5
как LP-1; F1/F2 aw чист); obs-состав — новый (F1 несёт failure-записи,
F2 нет; F0-S1/S3/S4 несёт D2 через pivot-carry при aw-FAIL).

## 8. Запреты

- Слои v0.6 не изменяются: recorder и ветки — in-process-патчи;
  audit sha256 до/после каждого прогона;
- полигон без изменений; noise2 — не новый класс мира (раздел 4);
- «победитель» не назначается: F1 имеет архитектурный приоритет, но
  LP-2 должен мочь его опровергнуть; ветки не называются
  «исправлениями»;
- без GT; после FREEZE ничего не меняется; анализ — после полного RAW.

## 9. Ревью профессора (FREEZE-условия; все приняты)

1. Формат (a)/(b) оставить — принято (раздел 3).
2. F1: failure остаётся в lineage; observations переносятся только в
   applicability_observations, никогда в applicable_when — принято
   (раздел 2).
3. noise2 разрешён как изменение только уже наблюдаемого envver, без
   нового класса мира — принято, формулировка в разделе 4.
4. S6c вывести из core, оставить optional — принято (не запускается).
5. В verdict раздельно: Q2 (форматная/структурная информативность
   failure, F0-S6a vs F0-S6b) и Q1 (F1 vs F2 по сохранению
   failure-derived observations) — принято (раздел 7).
6. F1 не объявлять победителем заранее; LP-2 должен иметь
   возможность его опровергнуть — принято (раздел 8).

## 10. Процедура

1. DRAFT → ревью → **FREEZE (07.09.2026; 6 уточнений приняты)** —
   выполнено.
2. lineage_persistence2/PROTOCOL.md (frozen).
3. lp2_driver.py: learn как lp_driver + recorder (a/b) + ветки
   (in-process) + регистрация + пробы (w1/wY/noise/noise2) + audit.
4. RUN: 3 × 7 × 2 = 42 прогона → LP2_records_<branch>.json (RAW).
   Анализ — только после полного RAW.
5. lp2_analyze.py → LP2_ANALYSIS.txt: aw-чистота, obs-состав по
   источникам, критерий успеха F1, Q1/Q2-verdict раздельно, регистры,
   r1≡r2, F1/F2-сравнение (S1/S3/S4/S6b — ожидаемо РАЗЛИЧАЮТСЯ).
6. LINEAGE_PERSISTENCE2_REPORT.md; v0.6 остаётся FROZEN.

## 11. Артефакты

LINEAGE_PERSISTENCE2_DESIGN.md (этот файл, FROZEN),
lineage_persistence2/PROTOCOL.md (frozen), lp2_driver.py,
lp2_analyze.py, LP2_records_<branch>.json (raw), LP2_run_<branch>.log,
LP2_audit_<branch>.txt, LP2_ANALYSIS.txt,
LINEAGE_PERSISTENCE2_REPORT.md. Слои v0.6 не изменяются.
