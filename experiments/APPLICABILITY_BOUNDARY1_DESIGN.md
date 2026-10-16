# TSARAPINA APPLICABILITY-BOUNDARY-1 (AB-1): DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026; слово профессора: «AB-1 FREEZE»).**
Прогон разрешён: PROTOCOL → ab1_driver → 4 последовательности ×
r1/r2 → RAW → ANALYSIS → REPORT. **Запрет: v0.6 (knowledge/update/
observer/strategy) НЕ изменяется до вердикта** — подозреваемый
механизм измеряется как есть. Measurement-only; полигон без
изменений.
База: Strategy v0.6 FROZEN (INTEGRATION_V06_REPORT.md; GATE 24/24),
ACQ-1 PASS.

## 1. Вопрос

> Сохраняется ли ACQ-1-инвариант приобретённой структуры
> (stable condition = E; variable signal = V; relation = disagreement;
> V НЕ в applicable_when), если между verified-success одной линии
> вклинивается failure-эпизод?

ACQ-1/G4 установили: V изменяется при сохранённом E → V остаётся
наблюдением disagreement и не попадает в applicable_when. AB-1
проверяет, не разрушает ли промежуточный failure уже приобретённую
структуру (память структуры при конфликтующем событии).

## 2. Гипотеза-механизм (подозреваемый, НЕ чинить)

update.apply создаёт знание на КАЖДЫЙ вердикт: failure-знания —
без applicable_when (Q5: поля только у verified-success). Механика
acquisition при новом success берёт prior линии (sym, E, cmd) =
последнее по времени активное знание (status active/conflicted),
включая failure-знания. Если последнее знание линии — failure (без
поля), то pcond={} и obs=[] → A2 «переоткрывает» условие из контекста
последнего success:

```
w1 success   → k1: applicable_when={E:absent, V:1}
noise failure→ k2: (без поля)              ← prior[-1] для следующего
wY success   → k3: applicable_when={E:absent, V:2}?  вместо
                 {E:absent} + obs V [1,2] disagreement
```

То есть failure ломает непрерывность переноса инварианта: V
возвращается в условие, observations теряются.

## 3. Миры (физика ACQ-1; полигон без изменений)

w1 (E=absent, V=1, symptom a) — fix-a ЛЕЧИТ (verified success)
wY (E=absent, V=2, symptom a) — fix-a ЛЕЧИТ (verified success)
noise ([a,n], E=absent, V=1, symptom a) — fix-a НЕ лечит (failure;
HIDDEN n — сигналы как w1; BOUNDARY-мир, здесь только как источник
failure)

Все шаги — канонический learn-путь (env_set → collect → действие
fix-a с ctx_extra=E → execute → evaluation → update.apply): w1/wY
дают success-знания, noise даёт failure-знание (без поля).

## 4. Последовательности (4; различают эффект failure от позиции)

```
S1: w1-s → noise-f → wY-s         (основной; failure между success)
S2: noise-f → w1-s → wY-s         (failure ДО первого success)
S3: w1-s → noise-f → noise-f → wY-s   (двойной failure)
S4: w1-s → w1-s → noise-f → wY-s      (failure после повторных success)
```

Реплики r1/r2 (конвенция).

## 5. Регистрируемое (после КАЖДОГО шага, по каждой новой версии)

- knowledge: knowledge_id, version, status, content, lineage
  (sym, E, command), applicable_when, applicability_observations
  (полные: signal, values_seen, relation, episode_refs),
  experience_refs;
- provenance последней версии: Knowledge → Experience → Fact → Raw
  (walk; applicable_when в цепочке);
- eligibility-пробы ПОСЛЕ финального шага каждой последовательности:
  suggest при мире w1, wY, noise (obs_now = E/V текущего мира):
  strategy_id, candidate command, knowledge_refs (какое знание
  выбрано), rationale rule.

## 6. Критерий (жёсткий; сохранение ACQ-1-инварианта)

Для каждой последовательности, где w1 и wY были verified-success:

**latest-версия линии (a, absent, fix-a):**
- applicable_when == {E: absent} (равенство);
- applicability_observations содержат V с values_seen [1,2] и
  relation=disagreement;
- V отсутствует в applicable_when (assert по всем версиям стора —
  наследие G4c-iii).

Поведенческий маркер (вторичный): eligibility-пробы w1/wY — S2
fix-a (какое знание выбрано — chosen knowledge_id: свежайшее с полем
против компенсации старыми версиями); noise — фиксируется (S2 —
слепота, ожидаемая граница; не FAIL-маркер).

## 7. Ожидания (предсказания, НЕ результаты)

- S1: k3 получает applicable_when={E:absent, V:2}, observations
  пусты → критерий FAIL (гипотеза подтверждается: failure после
  success с полем ломает перенос);
- S3: аналогично S1 (двойной failure) → FAIL;
- S4: prior[-1] после noise-f = failure → переоткрытие → FAIL;
- S2: на w1-s prior пуст → {E:absent,V:1} (честный срез первого
  успеха, Q1 — норма); на wY-s prior[-1] = w1-знание С полем →
  V-дивергенция → {E:absent} + obs V [1,2] → критерий PASS.
  Если так: failure ломает структуру только ПОСЛЕ первого успеха
  (эффект позиции, не «failure вообще»).

## 8. Запреты

- НЕ чинить _prior_lineage / update / strategy до вердикта
  (профессор: «подозреваемый механизм должен быть измерен как есть»);
- v0.6 и слои не изменяются (audit-hash до/после прогона);
- без GT в механизме (критерий — структурный, не переопределение
  ground truth);
- полигон без изменений; noise-различение не требуется.

## 9. Процедура

1. DRAFT → ревью → FREEZE (слово профессора).
2. applicability_boundary1/PROTOCOL.md (frozen).
3. ab1_driver.py: канонический learn (как gate_v06.learn), шаги
   последовательностей, регистрация версий, eligibility-пробы;
   audit-hash слоёв до/после.
4. RUN: 4 последовательности × r1/r2 → AB1_records.json (RAW, до
   анализа).
5. ab1_analyze.py → AB1_ANALYSIS.txt: критерий раздела 6 по каждой
   последовательности; вердикт: гипотеза подтверждена = BOUNDARY
   «persistence приобретённой структуры под interleaved failure»
   (v0.6 остаётся FROZEN; обработка — отдельным решением после
   verdict); не подтверждена = гипотеза о _prior_lineage закрыта.

## 10. Артефакты

APPLICABILITY_BOUNDARY1_DESIGN.md (этот файл, DRAFT),
applicability_boundary1/PROTOCOL.md (после FREEZE), ab1_driver.py,
ab1_analyze.py, AB1_records.json (raw), AB1_ANALYSIS.txt,
APPLICABILITY_BOUNDARY1_REPORT.md. Слои v0.6 не изменяются.
