# TSARAPINA APPLICABILITY-ACQUISITION-1 (ACQ-1): ОТЧЁТ (07.09.2026)

Дизайн: APPLICABILITY_ACQUISITION1_DESIGN.md (FROZEN 07.09); протокол:
applicability_acquisition1/PROTOCOL.md (FROZEN). Этапы: A0 read-only
recorder (подтверждён профессором) → grid 6 конфигураций × r1/r2 →
perms 6 порядков × A1/A2 × r1/r2 → P1-P7 → GATE_V05 (P7).
v0.5 и слои НЕ изменялись (audit sha256 на каждом прогоне +
повторный GATE_V05: PASS). Сырьё: ACQ0_records.json, ACQ1_records.json
(12 прогонов), ACQ1_PERM_records.json (24 прогона), ACQ1_ANALYSIS.txt.

## 1. A0 (baseline verification; отдельный отчёт в ANALYSIS A0)

Живой v0.5 воспроизвёл модель дизайна: Knowledge (14 полей) без
applicable_when; адрес вычисляется strategy из problem/args:
(symptom=[a], ctx=E, fix-a); V наблюдается (wY: E=absent, V=2,
success), но в адрес/знание НЕ приобретается; E в ctx выбирает
оператор. A0 PASS как baseline.

## 2. Физика полигона и решение по controls (зафиксировано ДО grid)

Тест физики: [a] лечится; [a]+n НЕ лечится (политика HIDDEN n,
CS-1); [a]+dbg и [a]+pulse лечатся. Следствие: N (lock.n) на
learn-момент неинъецируем (момент перестаёт быть verified success).
Решение профессора (07.09): N = измерение (n_obs), не кандидат;
шумовая граница сохранена; D/P — controls-кандидаты на learn-
моментах (D: присутствие по плану [нет, есть, нет, есть]; P:
пульс-писатель в окне двойного чтения). Телеметрия observer.collect
(df/meminfo/load) — кандидаты continuous (A0-наблюдение сохранено).

## 3. Результаты grid (6 конфигураций × r1/r2; детерминированы)

```
конфигурация     condition            D1                  D2
A0_clean/-ctl    (нет механизма)      -                   -
A1_clean         {E: absent, V: '2'}  0                   0
A1_controls      {E: absent, V: '2', D: True}  0          0
A2_clean         {E: absent}          V: [1,2]            noise
A2_controls      {E: absent}          V: [1,2], D: [F,T]  noise
```

- A1 (recency-коммит) — отрицательный контроль структуры:
  * перекоммичивает V (последний успех wY → V=2): P3 FAIL — LS на w1
    (w1: E=absent,V=1 не совпадает); на wY — VA;
  * controls: D (стабильный decor момента) попадает в условие —
    P2 FAIL; P3: LS на w1 И wY (D=True не совпадает с пробой).
  Ожидаемый FAIL подтверждён: per-moment фильтр без кросс-эпизодной
  структуры не различает инвариант (E) от случайного совпадения (V,
  D).
- A2 (инвариант verified-success + D1/D2):
  * условие = {E: absent} на всех конфигурациях и репликах;
  * V (значения {1,2} при неизменном E и успехе) → D1-наблюдение
    relation=disagreement, из условия исключён;
  * D (controls: {absent, present}) → D1-наблюдение, исключён;
  * P (пульс) и телеметрия (continuous) отсеяны уже фильтром
    (rejected: unstable / continuous);
  * S — relevance-ключ, в applicability не входит.

## 4. Критерии P1-P7

- P1 Completeness: E и V в acquisition-записи каждого learn-момента —
  PASS (A1/A2 × clean/controls × r1/r2).
- P2 Selectivity: N/D/P/T_* не в condition; S не applicability —
  PASS на A2 (clean/controls); FAIL на A1_controls (D в condition) —
  ожидаемое измерение уровня.
- P3 Address sufficiency (пробы w1/w2/wX/wY; noise вне P3):
  A1_clean: w1=LS (V-перекоммит) — FAIL; A1_controls: w1=LS, wY=LS
  (V+D) — FAIL; A2 (обе конфигурации): w1=VA, w2=VS, wX=VS, wY=VA —
  0 ошибок — PASS.
- P4 Stability: (a) r1≡r2 по нормализованной проекции на всех 6
  конфигурациях — PASS; (b) 6 перестановок learn-порядка × r1/r2:
  A1 — 2 разных финальных условия (порядкозависимость, последний
  успех определяет V) — FAIL (ожидаемо); A2 — 1 условие {E:absent}
  ×12 — PASS. Кросс-hold-out r1↔r2 обеспечивается P4a-идентичностью
  (условие r1 на пробах r2 тождественно).
- P5 Conflict honesty: D1-факты (V, D) не возвращаются в условие;
  победитель не назначается; D2 (noise-проба: вектор (0,0) совпал с
  условием, вердикт failure) → observation relation=
  outcome_disagreement, условие НЕ изменено — PASS (A2).
- P6 Provenance: каждая applicable-запись несёт episode_id; цепочка
  applicable → episode → observations (raw_ref) → raw восстановлена
  механически (store read_raw: A2_clean 5/5, A2_controls 10/10) —
  PASS.
- P7 Regression: audit sha256 слоёв до/после каждого прогона —
  unchanged (все 36 прогонов); повторный INTEGRATION GATE v0.5:
  PASS (T2/T3/SWAP/DET/T4a-T4e) — v0.5 не изменена.

## 5. Вердикт

**A2 (кандидат зоны): PASS по P1-P7. A1: ожидаемый FAIL подтверждён
(контроль структуры). A0: baseline PASS.**

> ACQ-1: PASS. Механизм acquisition, получающий только наблюдаемые
> факты и вердикты (без имён миров, GT, порогов, trust), из
> последовательности verified-success эпизодов приобретает условие
> E=absent; расходящиеся сигналы (V между w1/wY; D в controls)
> фиксируются как disagreement-наблюдения, а не разрешаются;
> noise-проба с совпавшим вектором даёт outcome_disagreement без
> изменения условия; шумовая граница Observer'а сохранена.

Содержательный итог для зоны: «умнее» означает не додумать ответ, а
не записать того, что опыт не установил: A2 не выбирает между
E=absent и V=1/2 — он удерживает инвариант и регистрирует
расхождение. Это ровно тот случай, где структура приобретается из
опыта, а не подсказывается.

## 6. Артефакты

APPLICABILITY_ACQUISITION1_DESIGN.md (FROZEN), applicability_
acquisition1/PROTOCOL.md (FROZEN), acq0_recorder.py, acq0_analyze.py,
ACQ0_records.json, ACQ0_audit.txt, ACQ0_ANALYSIS.txt, acq1_driver.py,
acq1_mechanism.py, acq1_analyze.py, ACQ1_records.json (12 прогонов),
ACQ1_PERM_records.json (24 прогона), ACQ1_run.log, ACQ1_ANALYSIS.txt,
APPLICABILITY_ACQUISITION1_REPORT.md (этот файл). Слои и Strategy
v0.5 не изменены.

**Следующий шаг (по слову профессора): интеграционный гейт v0.6 —
Strategy/Knowledge integration (applicable_when как поле знания) —
отдельным экспериментом.**
