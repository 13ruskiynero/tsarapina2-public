# TSARAPINA INTEGRATION V0.6: DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026; слово профессора: «Решения приняты.
Дизайн FREEZE»).**
Инженерия разрешена: baseline strategy_v05_baseline.py →
knowledge/update/observer/strategy → gate G1-G4. Изменений после
FREEZE нет; решения Q1-Q6 и семантика полей — в разделах 2 и 6.
База: Strategy v0.5 FROZEN (INTEGRATION_V05_REPORT.md; baseline-копия
strategy/strategy_v05_baseline.py, конвенция v0.4); ACQ-1 PASS
(APPLICABILITY_ACQUISITION1_REPORT.md) — этот гейт интегрирует
приобретённую структуру применимости (механизм A2) в рабочий цикл.

## 1. Вопрос

> Если встроить приобретённую структуру (applicable_when + D1/D2-
> наблюдения) обратно в рабочий цикл, изменит ли она поведение
> Царапины именно там, где должна (E-условие гейтит применение), и
> не разрушит ли уже полученные свойства (регрессия, эквивалентность
> на старых задачах, персистентность, provenance)?

Гейт НЕ проверяет «работает ли acquisition» (ACQ-1 измерил: работает).
Гейт проверяет, что поле в Knowledge — не «красивое поле в SQLite»,
а реально используемый механизм адресации с сохранением всех свойств.

## 2. Объём изменений (инженерия по слову профессора; основной код,
как gate_v04/v05)

1. **knowledge/knowledge.py**: SCHEMA_VERSION "0.1" → "0.2";
   create() принимает optional:
   - applicable_when: dict {имя_факта: значение} — инвариант
     verified-success истории на момент создания знания;
   - applicability_observations: list [{signal, values_seen,
     relation: "disagreement", episode_refs}] — расхождения D1/D2.
   Версии копируют поля (append-only; retract/restore/conflict поле
   не теряют); provenance_walk включает оба поля.
2. **update/update.py**: acquisition-шаг в apply() для
   verified-success: A2-механика из ACQ-1 (acq1_mechanism: инвариант
   значений по same-address verified-success знаниям истории + факты
   текущего опыта) → applicable_when / applicability_observations.
   Failure-знания поля не получают (acquisition — по успехам).
   Пустое поле {} НЕ пишется: если инварианта нет — поле отсутствует
   (молчание acquisition).
3. **observer/observer.py**: collect() включает envver-наблюдение
   (polygon_sensor.sensor_envver; pre-action; provenance raw_ref) —
   следствие CS-1 («добавление наблюдаемого факта в Observer»).
   V становится фактом опыта, acquisition видит его с provenance.
4. **strategy/strategy.py → v0.6**: suggest, выбор exact-знания:
   если knowledge.applicable_when присутствует — сверка с текущими
   наблюдениями (E — через ctx_now, как сегодня; схема расширяема);
   не выполнено → S3 (context_mismatch-семантика — как текущий
   ctx-фильтр); поле отсутствует → legacy-путь v0.5 (ctx из args
   действия) БЕЗ изменений. strategy_version "0.6".

Запрещённая семантика поля (ACQ-1, раздел 5): applicable_when и
observations содержат только наблюдаемые факты/значения/relation.
Никаких «V irrelevant», «V noise», «E is true cause», «E guarantees»,
имён миров, GT.

## 3. Четыре группы гейта (gate_v06.py)

### G1. Backward compatibility
- повтор GATE_V05 часть A на v0.6: 11/11 PASS (T1 ctx=absent→fix-a;
  T2 ctx=present→fix-a2; T3 6/6; SWAP; DET; T4a A; T4b AB; T4c C-SEB
  8 действ.; T4c2 S2 fix-c; T4d S3; T4e legacy без ctx);
- повтор часть B (TE): 14/14 PASS (KNOWN/AB/SEBC/SEBC2/S3/DET/STALE/
  SINGLE/ALT/DOUBLE/MIX/M4);
- юнит-наборы 9/9 (tests/test_{observer,experience,knowledge,strategy,
  llm_adapter,executor,evaluation,update,aggregation}.py);
- audit-hash: изменены ТОЛЬКО knowledge/update/observer/strategy
  (сверка с v0.5-копиями остальных слоёв).

### G2. Behavioral equivalence (старые задачи; knowledge создано
штатным learn с ≥2 verified-success: applicable_when={E:absent},
obs V[1,2])
- return A (learn w1 ×2) → задача A: S2, 1 действие;
- AB (learn ab) → S2 fix-ab, 1 действие;
- C → exploration → fix-c → S2 (SEB-путь не изменён);
- сравнение с baseline v0.5 (strategy_v05_baseline.py) на тех же
  сценариях: strategy_id, команда, число действий идентичны.
  applicable_when НЕ меняет поведение там, где v0.5 уже работала.

### G3. Acquisition persistence
- learn w1 → wY в процессе A; Store закрыт; процесс B: знание читается
  с applicable_when={E:absent} и applicability_observations
  (V [1,2], episode_refs) — поле переживает новый процесс;
- provenance-цепочка: applicable_when → knowledge.experience_refs →
  experience.observations (raw_ref) → raw — механический walk
  (provenance_walk расширен);
- версии: v1 (первый успех, без поля или с полем-срезом) НЕ мутирует
  при появлении v2 с наблюдениями; retract/restore сохраняют поля;
- acquisition-наблюдения несут episode_refs (P6-конвенция ACQ-1).

### G4. Applicability actually used
- **G4a (V не становится условием; усилено при FREEZE)**: после learn
  w1+wY: latest-версия линии имеет applicable_when == {E: absent}
  (assert, не «содержит» — равенство) и observations V [1,2];
  задача при E=absent и V=1 → S2, 1 действие, success; задача при
  E=absent и V=2 → S2, 1 действие, success. V не обязателен при
  одинаковом E (disagreement не «победил»);
- **G4b (E реально гейтит; усилено)**: то же knowledge; задача при
  E=present и ЛЮБОМ V из зарегистрированного disagreement (V=1 и
  V=2 по отдельности): НЕ S2 — S3 (вне контекста); старое знание не
  применяется вслепую;
- **G4c (поле, а не артефакт args)**: синтетические записи (как в
  gate_v05): (i) knowledge с applicable_when={E:absent} и БЕЗ
  ctx_extra в args (legacy-форма) — ведёт себя как ctx-знание
  (поле управляет); (ii) knowledge без поля, ctx=absent — legacy-путь
  без изменений; (iii) assert: ни одно знание с V в obs_d1 не
  содержит V в applicable_when.
- noise (E=absent,V=1, failure): D2-семантика — поле не меняется,
  различение не требуется (BOUNDARY).

## 4. Миры (физика ACQ-1/AS-2; полигон без изменений)

w1 (E=absent,V=1, лечится) — learn-мир; wY (absent,2, лечится) —
learn-мир (V-расхождение); w2 (present,2), wX (present,1) — не
лечатся (E-гейт); noise (absent,1) — не лечится (BOUNDARY, D2).

## 5. Запреты

- applicable_when без скрытой семантики (раздел 2, п.4);
- пустое applicable_when не пишется; V из disagreement не входит в
  условие (assert G4c-iii);
- версии не мутируют; старые версии не переписываются;
- пороги/trust/GT/causal inference в acquisition не появляются
  (запреты ACQ-1 наследуются);
- в сценариях G1/G2 поведение не «улучшается» — только сохраняется
  (эквивалентность);
- различение noise не требуется (граница Observer'а).

## 6. Решения (утверждены при FREEZE 07.09)

1. **Q1 — момент появления applicable_when**: писать с первого
   verified-success как честный срез текущего состояния; новые
   verified-success создают новые append-only версии; при выборе
   используется наиболее свежая версия линии знания (recency, v0.5-
   семантика). **Уточнение (профессор): V НЕ входит в идентичность
   knowledge-line после классификации A2 как disagreement.** Линия:
   (symptom=a, стабильное applicable=E=absent, observations: V
   1↔2). Промежуточная узкая версия не переписывается; следующая
   версия может нести более широкое условие; старые версии остаются
   историей (append-only, provenance).
2. **Q2 — envver в Observer: ДА.** Observer только наблюдает
   (environment_version = ...), без интерпретации «мир изменился».
3. **Q3 — E приходит через ctx_extra: ДА** (механизм живого A0,
   подтверждён baseline; второй канал доставки E не вводится).
4. **Q4 — D/N в реальном контуре не наблюдаются: ДА.** Внутри
   acquisition ничего не симулируется ради симметрии; отсутствие N
   на learn-моменте — факт полигона (HIDDEN n).
5. **Q5 — acquisition в update.apply: ДА.** Experience → Evaluation
   → Update → Knowledge + acquisition; **только verified-success**.
   Failure не формирует applicability condition.
6. **Q6 — legacy**: если applicable_when отсутствует — старый
   v0.5-путь (поле = расширение, не обязательная форма).

Семантика полей (зафиксирована): applicable_when содержит ТОЛЬКО то,
что acquisition считает устойчивым условием применимости (E=absent);
applicability_observations — то, что наблюдалось, но НЕ получило
статуса условия (V: 1→2, relation=disagreement, episode_refs).
Наличие observations НЕ означает «Царапина знает, что V означает» —
это запись неопределённости.

Инженерные правила (при FREEZE):
- acquisition пишет поле только при verified-success и наличии
  ctx_extra (E) в args действия опыта; без E — legacy-знание,
  поле не пишется (T4e-совместимость);
- V-наблюдение acquisition берёт из опыта: envver-факт появляется в
  observations ТОЛЬКО если /run/tsasvc.envver существует на момент
  collect (реальный внешний источник; без файла сенсор молчит —
  CA-1/TE-миры не получают V-фактов, их знания остаются E-формы);
- пустое applicable_when не пишется (молчание acquisition);
- failure/noise-знания полей не получают и линию не меняют (D2).

## 7. Процедура

1. DRAFT → ревью → FREEZE (слово профессора).
2. Baseline: strategy/strategy_v05_baseline.py = копия v0.5 (артефакт
   сравнения; не импортируется).
3. Инженерия по разделу 2 (knowledge → update/observer → strategy) —
   после FREEZE.
4. Гейт: experiments/gate_v06.py (G1: повтор gate_v05 частей A+B и
   юнитов; G2: эквивалентность vs baseline; G3: персистентность
   (2 процесса) + provenance-walk; G4a/b/c) + audit-hash слоёв.
5. Сырые GATE_V06_run*.txt → анализ → REPORT.
6. PASS → v0.6 FROZEN (strategy_v06); FAIL → откат к v0.5 (baseline
   остаётся рабочей), граница фиксируется.

## 8. Артефакты

INTEGRATION_V06_DESIGN.md (этот файл, DRAFT), strategy/
strategy_v05_baseline.py (v0.5), изменённые knowledge.py/update.py/
observer.py/strategy.py (v0.6), experiments/gate_v06.py, GATE_V06_
run*.txt, gate_v06_data/, INTEGRATION_V06_REPORT.md.
