# TSARAPINA EVIDENCE-PERMISSION-1 (EP-1): ОТЧЁТ (07.09.2026)

**Статус: CLOSED (слово профессора, 08.09.2026; strong finding).**
Итог: универсального evidence threshold не существует (Explore =
permitted verification, не evidence-based trust); R/S-INSUFFICIENT
локализован ДО permission layer (upstream candidate selection:
failure-знания в recency-гонке, D-1); V vs D2 симметричного канала
не предоставляет (EF-3); persistent noise ≡ stale на общем префиксе
— repetition count не основание для trust/permission. Следующая
граница: **AA-1 (D-1, applicability addressing)** → EP-2. Разделы
1–7 фиксируют результат и не пересматриваются.

---

Дизайн: EVIDENCE_PERMISSION1_DESIGN.md (FROZEN); протокол:
evidence_permission1/PROTOCOL.md (FROZEN). 100 прогонов (50 policy-
клеток × r1/r2) → EP1_cell_*.json (RAW) → ep1_analyze.py →
EP1_ANALYSIS.txt. Audit слоёв: OK 100/100; L6-walk: 0 нарушений;
регрессионный якорь (B N1D/N1V: K1 {E:absent,V:1} gen1): OK;
детерминизм: 0 расхождений r1≡r2. Вмешательства — simulated, стор
append-only, слои v0.6.x не изменялись.

## 1. Вопрос и ответ

Вопрос: **когда failure-derived evidence получает право изменять
поведение системы?** Гипотеза: разные типы evidence имеют разные
права, не сводящиеся к числу trust.

**Ответ по records (sufficient — только после correctness +
harm/no-harm; expected ≠ finding):**

```
Клетка    G-full          G-single        Основание
E1X       SUFFICIENT      SUFFICIENT      SM: fix-aq на шаге 3 (success
                                           после смены); N-часть пуста
                                           (E1 в N-мире не возникает)
E2X       SUFFICIENT      SUFFICIENT      S: SD/SM/NSD/E6S — success;
                                           N: N1D/NaD/NpD/E6N —
                                           восстановление ≤ baseline
E3X       NO-EVENT        NO-EVENT        гомогенная V-серия нигде не
                                           возникает (EF-3)
E4X       SUFFICIENT      SUFFICIENT      SD/E6S success; NpD
                                           восстановление на шаге 4
                                           (= baseline)
E5X       SUFFICIENT      SUFFICIENT      SM success; NpM шаг 4 (= B)
E6X       SUFFICIENT      SUFFICIENT      контроль: право по
                                           conflicting success БЕЗ
                                           failure — тоже «достаточно»
                                           по core-метрике
E3R/E3S   NO-EVENT        NO-EVENT        (EF-3)
E4R/E4S   INSUFFICIENT    INSUFFICIENT    повторений fix-a после
                                           триггера = 1 (SD, E6S)
E5R/E5S   INSUFFICIENT    INSUFFICIENT    повторений fix-a после
                                           триггера = 1 (SM)
```

## 2. Findings (execution; до и во время прогонов)

- **EF-1 (до прогонов):** полигон — q/fix-aq (STALE_EXACT2), не
  extra/fix-a2: extra наблюдаем sensor_envfact'ом → входит в E-адрес
  линии v0.6.x; смена extra = address mismatch (тип A), не предмет
  EP-1 (тип B). q скрыт от symptom и envfact → линия (a, absent,
  fix-a) едина в w1/w2. Грид и участие не менялись.
- **EF-2 (до прогонов, подтверждено checks):** suggest v0.6.x
  выбирает свежайший член пула (recency), включая failure-знания
  (legacy-путь, D-1-феномен): симуляция R/S(K1) не исключает
  выбранного кандидата (checks: granted→excluded 0/20; выбор всегда
  шёл через failure-знание). R-эффект наблюдаем только структурно:
  recorder и lineage_generation «слепнут» (после R: failure-члены
  без obs, generation сбрасывается к 1).
- **EF-3 (при прогонах):** V2-эпизоды (N1V/NpV/SV) при знании
  {E:absent,V:1} дают S3-бездействие (applicable_when исключает
  применение при V=2 — контракт v0.6.x «не применять вслепую»);
  recorder молчит. (a)-записи (V-change) НЕ достижимы как первое
  evidence: они возникают только через legacy-кандидата после
  первичного D2-failure (SM-каскад: (b) → (a) → (b)). E3
  (гомогенная V-серия) недостижима в эксплуатационном контуре —
  NO-EVENT на всех клетках. Фактическая матрица триггеров уже
  дизайн-таблицы на N1V/NpV/SV (E1/E3) и NpM (E1 фактически
  возникает на шаге 2 — как SM).
- **EF-4 (при прогонах):** E4-событие на NSD возникает только на
  терминальном шаге (2-й failure после смены = последний шаг
  истории): триггер зафиксирован (terminal), вмешательство
  невозможно — траектория ≡ baseline.

## 3. Интерпретация (граница permission)

1. **Explore (X) — «дешёвое» право: SUFFICIENT по любому
   возникающему evidence** (E1@SM, E2, E4, E5; E6-контроль тоже).
   Подтверждено fix-aq-допущение (гипотеза): fix-aq корректен в w1
   и w2 → explore никогда не блокирует восстановление (N-истории:
   восстановление ≤ baseline везде), на S-историях достигает
   успеха, которого baseline лишён. Цена — вторичная: лишняя линия
   (a, fix-aq) (E6-контроль: 3 fix-aq-эпизода в живом мире БЕЗ
   failure-сигнала — ложное срабатывание по цене).
2. **Retract/Suppress — «дорогие» права: INSUFFICIENT на всех
   протестированных клетках**, и причина НЕ «мало повторов», а
   механика: R/S(K1) не влияет на выбор контура, потому что выбор
   идёт через failure-знания (legacy-путь, D-1). «Остановка
   повторений» (0 повторений после триггера) недостижима retract'ом
   verified-success знания; для остановки потребовалось бы
   исключение failure-знаний из пула выбора — это пересечение с
   D-1 (LEGACY_ADDRESSING_CORRECTION), а не расширение R-права.
3. **Граница определяется деструктивностью права и структурой
   события, НЕ типом записи (V vs D2).** Тип-канал V структурно
   вторичен: applicable_when-адресация делает D2 первым
   наблюдаемым evidence (EF-3); V-записи достижимы только после
   D2. Различие одиночная/серия (E2 vs E4/E5) для X не значимо
   (обе достаточны); для R/S не значимо (обе недостаточны).
4. **Формальный факт неразличимости подтверждён:** NpD ≡ SD по
   наблюдаемым префиксам (смежные D2-серии); E4-политики
   срабатывают одинаково на шуме и устаревании. Permission-
   границы между persistent-шумом и устареванием в evidence НЕТ
   (как предсказано); explore это не вредит (дешёвое право), R/S —
   не спасает (см. п.2).

## 4. Сверка с ожиданиями (expected)

- X-клетки expected sufficient → **подтверждено** (E1X/E2X/E4X/
  E5X/E6X SUFFICIENT; E3X — NO-EVENT, ожидание не тестируемо).
- R/S серийные expected INSUFFICIENT на G-full → **подтверждено**;
  expected SUFFICIENT на G-single → **опровергнуто** (INSUFFICIENT
  и там: повторения=1; механизм — D-1-перекрытие, EF-2).
- R/S × E1/E2 (лемма L-RS1, derived) → подтверждена по построению
  (checks 0/20: кандидат-исключение не наблюдаемо; одиночный
  failure не останавливает контур — failure-знания продолжают
  выбираться).
- E6-контроль → по core-метрике «безвреден» (как ожидалось при
  дешёвом X); вторичная цена = 3 лишних fix-aq-эпизода в живом
  мире без failure-сигнала (ложное срабатывание контроля).
- Тип V vs D2 может не различаться → подтверждено: различаются
  право (X vs R/S) и структура (канал V недостижим первым), не
  тип записи.

## 5. Вердикт

**PASS-форма выполнена:** ≥1 клетка SUFFICIENT (X-клетки), граница
установлена по измерению «деструктивность права × структура
события × noise model», а не по типу evidence. Дополнительно
установлено пересечение R/S-прав с D-1 (legacy-адресация
failure-знаний), невидимое до EP-1.

Следствия для реестра долгов:
- **D-2/D-4 (ветка EP-1):** «событие достаточного свидетельства»
  получает форму: для дешёвых прав (explore) достаточного
  свидетельства НЕ ТРЕБУЕТСЯ (граница — allowlist-допущение о
  правоте кандидата, не evidence); для дорогих прав (retract/
  suppress) evidence-канал v0.6.x НЕ достаточен — блокирован
  legacy-адресацией (пересечение с D-1). Trust-число по-прежнему
  не строится и не требуется: различие прав категориально.
- **D-1 (legacy addressing):** получает новый вес — R/S-permission
  нереализуемы, пока failure-знания адресуемы через legacy-путь;
  коррекция адресации — precondition любых «дорогих» прав.
- **D-3:** разделение permission ≠ generalization сохранено
  (explore-право нашло fix-aq по подсказке allowlist, не обобщило
  A/B→C).

## 6. Статус и следующие шаги (слово профессора)

v0.6.x не изменялся; грид/h/участие — как FROZEN. Вторая волна
(горизонты h≥4; пары R+X/S+X; пороги серий ≥3; V-канал через
learn-принудительные эпизоды) — по слову профессора. Кандидаты:
(1) EP-1-вторая-волна; (2) D-1-коррекция как precondition дорогих
прав (теперь обоснована экспериментально); (3) permission
semantics (какие статусы становятся контрактом следующей версии).

## 7. Артефакты

EVIDENCE_PERMISSION1_DESIGN.md (FROZEN), evidence_permission1/
PROTOCOL.md (FROZEN), ep1_driver.py, ep1_analyze.py, EP1_cell_*.json
(RAW ×100), EP1_ANALYSIS.txt, EVIDENCE_PERMISSION1_REPORT.md (этот
файл). Слои v0.6.x не изменялись (audit 100/100).
