# TSARAPINA APPLICABILITY-ADDRESSING-1 (AA-1): ОТЧЁТ (10.09.2026)

**Статус: CLOSED (слово профессора, 10.09.2026; PASS — оба
раздельных утверждения).** D-1: experimentally confirmed.
**strategy_aa.py НЕ интегрируется в working layers**: это
экспериментальная реализация доказанного механизма, а не часть
замороженного слоя; integration gate — отдельно, ПОСЛЕ EP-2, по
слову профессора. Следующая граница: EP-2 (umbrella A→B→C;
первый шаг — EP-2A: Evidence → R/S).

---

Дизайн: APPLICABILITY_ADDRESSING1_DESIGN.md (FROZEN 10.09.2026;
DESIGN → ACCEPTED → FREEZE). Протокол: applicability_addressing1/
PROTOCOL.md (FROZEN). Прогон: 34 клетки × r1/r2 = 68 прогонов
(grid: B: A0/A1 × 9 историй; R/S@E4: A0/A1 × {NpD, SD, NSD, E6S} ×
{R, S}); RAW: AA1_cell_*.json; анализ: aa1_analyze.py →
AA1_ANALYSIS.txt. Audit слоёв: 68/68 без изменений; store
append-only; r1 ≡ r2 (OK).

## 1. Вопрос

> Исчезает ли recency-based захват кандидата failure-knowledge при
> сохранении поведения остальных частей контура?

## 2. Результаты (раздельные утверждения)

**2.1. AA-1 PASS: ДА (адресация).** Ветка A1 (strategy_aa.py:
фильтр `outcome == "success"` строго ДО цикла matching):
- **failure-refs == 0:** на всех A1-B-прогонах выбранный S2-кандидат
  (ref_outcome) — verified-success знание; ни один failure-ref;
- **N-траектории A1 ≡ A0:** N1D, NaD, NpD — идентичны (действия и
  исходы); V2-контроль N1V, SV — идентичны (S3-вырождение,
  унаследованное от applicable_when-адресации);
- **S-истории:** SD, NSD, E6S — идентичны; **SM — единственное
  расхождение** (измеренный эффект, не FAIL): шаг f@V2: A0
  эксплуатирует failure-знание через legacy-путь (aw=None, V2 не
  проверяется — знание вне его applicability), A1 — S3-остановка
  (K1 не применим при V2, failure отфильтрованы);
- якорь (A0-B-N1D ≡ EP-1 B-N1D по форме K-цепочки) — OK; L6-walk
  чист (source enum, failure-obs с refs, aw только success-путь);
  acquisition не изменён; r1 ≡ r2.

**2.2. R/S PASS: ДА (permission на правильно адресованном
кандидате).** При A1 simulated R/S(K) действует на того же кандидата,
что производит выбор:
- A1 R@E4/S@E4 на SD и E6S: **повторений fix-a после триггера = 0**;
  **checks granted→excluded = True**; следующий эпизод — S3
  (пул пуст: K исключён, failure-знания не кандидаты);
- A0-контроль (та же механика на текущей адресации): granted→
  excluded = False; повторения = 1 (SD, E6S), = 2 (NpD) — выбор
  идёт через failure-серию, R/S бессильны (воспроизведение EP-1).

**2.3. Границы (не FAIL AA-1):**
- A1-R/S на NpD: S3-остановка → восстановление потеряно
  (постоянный R/S исключает K1 навсегда; failure-знания не
  кандидаты; успех fix-a в горизонте отсутствует) — граница
  семантики постоянного retract/suppress; материал EP-2;
- NSD-R/S@E4: терминальный триггер (EF-4 EP-1) — ожидание ≡ B
  подтверждено (вмешательство в горизонте невозможно).

## 3. Execution notes

- **EN-1:** ref_outcome на S3-шагах зависит от порядка kid'ов
  (диагностический список refs) — нормализовано в анализе (ref-класс
  только для S2-шагов); RAW не изменялся (правило заморозки).
- **EN-2:** детерминизм r1≡r2 подтверждён после нормализации EN-1;
  остаточные расхождения отсутствуют.

## 4. Вердикт

**AA-1 PASS** (адресация: recency-захват failure-knowledge
устранён; поведение контура сохранено) и **R/S PASS** (механика
permission разблокирована: R/S действуют на кандидата линии
applicability). Утверждения раздельные: AA-1 отвечает «правильно ли
выбран объект», R/S-часть — «дошло ли право до объекта».

Следствия:
- **D-1 (APPLICABILITY ADDRESSING):** экспериментально подтверждён;
  strategy_aa.py (фильтр до matching) — кандидат на интеграцию в
  strategy-слой (отдельный gate по слову профессора);
- **EP-2 открыт:** R/S permission boundary при корректной
  адресации — теперь измерима: (а) какие evidence достаточны для
  R/S; (б) семантика постоянного vs временного («до-подтверждения»)
  retract/suppress для append-only store; (в) связка S3→explore
  (stop → permission to explore — переезжает из AA-1);
- EP-1-вопрос «R/S insufficient — свойство permission или артефакт
  адресации?» получил первую половину ответа: артефакт адресации
  существовал и снят; вторая половина (достаточность evidence для
  R/S) — предмет EP-2.

## 5. Артефакты

APPLICABILITY_ADDRESSING1_DESIGN.md (FROZEN), applicability_
addressing1/PROTOCOL.md (FROZEN), strategy_aa.py (sha
61344099c8f83bd0…; diff к strategy.py = 3 ханка), aa1_driver.py,
aa1_analyze.py, AA1_cell_*.json (RAW ×68), AA1_ANALYSIS.txt,
APPLICABILITY_ADDRESSING1_REPORT.md (этот файл). Слои v0.6.x не
изменялись (audit 68/68).
