# TSARAPINA EVIDENCE-PERMISSION-2 (EP-2): РАМКА И EP-2A
# (FROZEN 10.09.2026)

**Статус: EP-2A — FROZEN (10.09.2026; слово профессора: решения по
пяти точкам + pre-FREEZE уточнения).** EP-2B/EP-2C — эскизы, НЕ
проектируются до результата A. Прогоны EP-2A разрешены (PROTOCOL →
driver → preflight → RUN — следующие шаги). База: EP-1 CLOSED; AA-1
CLOSED, PASS (адресация A1 — рабочая база; strategy_aa.py — ветка,
НЕ интегрируется до отдельного gate после EP-2).

**Рамка:** umbrella A→B→C; НЕ смешивать; НЕ строить EP-2 = R/S +
temporary + explore + trust + recovery одной конструкцией.
Последовательность: «может ли evidence дать право?» (A) → «что
означает полученное право?» (B) → «что делать, если candidate больше
нет?» (C).

**Решения пяти точек (утверждено):**
1. Семантика A = permanent (AA-1-семантика, без TTL/reactivation);
   temporary — НЕ переменная A (переезжает в B).
2. C1–C6 подтверждены; формальные взаимоисключающие определения
   (см. §2); C5 ≠ C6 по определению (не косметикой).
3. Scope права = ТОЛЬКО candidate K (не tail/lineage/серия/все
   знания симптома). Вопрос «что именно исключается» — после
   установления, выдаётся ли право вообще.
4. Grid: participation matrix ЛИТЕРАЛЬНО (§4), затем арифметика из
   неё; baseline наследуется из EP-1/AA-1; B, R и S раздельно;
   r1/r2; матрица — до чисел.
5. Результат A формулируется УЗКО: «при permanent R/S ни одна
   исследованная evidence-конфигурация не удовлетворила совместному
   критерию остановки и восстановления; это результат EP-2A и
   основание открыть EP-2B для исследования временной semantics» —
   НЕ «evidence недостаточно вообще».

**Fixed:** permanent R/S; scope=K; C1–C6; C5≠C6; h=3 (C3); R и S
анализируются ОТДЕЛЬНО (sufficient(R), sufficient(S)); baseline
наследуется; r1/r2; критерий:
`Sufficient(right, C) = stop_on_S AND recovery_on_N >= baseline`.

**НЕ исследуется в A:** temporary retract; permanent-vs-temporary
comparison; tail/lineage scope; S3→Explore; новые thresholds ≥3;
h>3; trust score. (Всё — за последующими границами.)

**Инвариант C6:** recovery = success ТОГО ЖЕ candidate K
(K1 ↓ failure ↓ K1 verified-success), не «появление другого
решения» (fix-aq/другая линия/K2-как-иное-решение). Регистрация:
recovery-эпизод = эпизод, применивший candidate K (refs[0] == K) с
исходом success; «другое решение» recovery не считается.

## 1. Вопрос EP-2A

> Какая КОНФИГУРАЦИЯ evidence даёт право R/S, не уничтожая
> возможность восстановления?

Не переоткрывать (отрицательные результаты): «сколько failure
достаточно?» — числа не ищем; persistent failure count сам по себе
права не даёт (EP-1); Np ≡ S на общем наблюдаемом префиксе (EP-1);
постоянный R/S блокирует восстановление (AA-1, NpD).

## 2. Конфигурации (взаимоисключающие определения)

```
C1 single failure      один failure-член, без дополнительной
                       структуры (первый и единственный на момент
                       триггера)
C2 repeated failure    f → f: два смежных failure-члена, серия ещё
                       не persistent (ровно 2)
C3 persistent series   f → f → f: непрерывная серия из трёх failure-
                       членов без промежуточного verified-success
                       (граница h=3 — как в EP-1)
C4 failure +           failure-событие, НЕСУЩЕЕ наблюдаемое
   applicability       расхождение applicability: запись (a)
   divergence          (V-change: values_seen ∪ {v_now},
                       relation=disagreement) в самом failure-члене
C5 failure +           failure при наличии КОНФЛИКТУЮЩЕГО
   conflicting success verified-success (≥2 success-члена линии с
                       разными V); НЕ recovery того же candidate
C6 failure + recovery  f → s → f: новый failure ПОСЛЕ verified-
                       success того же candidate K (recovery по
                       инварианту выше)
```

**Классификация C4/C5 — disjoint trigger classes (ред. 10.09, по
ревью; формализация — PROTOCOL §1):** клетка классифицируется по
первичному событию: conflicting-success condition присутствует →
C5 (приоритет; V-divergence внутри failure сохраняется как
внутреннее свойство evidence и классификацию не меняет); иначе
(a)-запись в failure → C4; иначе — не C4/C5. Структурное следствие
(лемма, PROTOCOL §1): в A1-контуре с V-каналом у всех эпизодов
(a)-запись ⟹ конфликт присутствует, поэтому проектные C4-клетки
(S6bV3, E6N-V3) классифицируются как C5+(a); C4-класс в текущих
конструкциях носителя не имеет (unit-тест ветви — в preflight).
Число прогонов не меняется.

## 3. Семантика R/S в A (фиксирована)

AA-1-семантика: право выдаётся по конфигурации; R/S(K) =
исключение конкретного candidate K (последний verified-success
член линии) из prior_lineage-чтений (R) и/или suggest (S);
постоянно в горизонте; simulated, стор append-only. Механика —
из AA-1 (granted→excluded/absent→remains). Non-success пути
(recorder, acquisition) не затрагиваются.

## 4. Participation matrix (ЛИТЕРАЛЬНО) и арифметика из неё

```
       S-среда: история (триггер)          N-среда: история (триггер)      Права
C1     SD (после шага 1)                    N1D (после шага 1)              R, S
C2     SD (после шага 2)                    NpD (после шага 2)              R, S
C3     SD4 (после шага 3)                   NpD (после шага 3)              R, S
C4     S6bV3 (после шага 1; (a)-запись)     E6N-V3 (после шага 1; (a))      R, S
C5     E6S (после шага 1)                   E6N (после шага 1)              R, S
C6     — (recovery same-K в мёртвом мире    C6N (после шага 3; паттерн      R, S
        невозможно: S-аналог отсутствует)   f s f)
```

Истории (полные конструкции):
```
SD:      [w2] f@V1 f f
SD4:     [w2] f@V1 f f f
N1D:     [w1] f@V1(noise) s s
NpD:     [w1] f@V1(noise) ×3, s
S6bV3:   learn w1@V1, learn wY@V2 → [w2] f@V3 f f
E6N-V3:  learn w1@V1, learn wY@V2 → f@V3(noise) s s
E6S:     learn w1@V1, learn wY@V2 → [w2] f@V1 f f
E6N:     learn w1@V1, learn wY@V2 → f@V1(noise) s s
C6N:     learn w1@V1 → f@V1(noise) s@V1 f@V1(noise) s@V1
```

Арифметика (из матрицы; policy-единица = конфигурация × право ×
история):
```
C1: (R,S) × (SD, N1D) = 4        C4: (R,S) × (S6bV3, E6N-V3) = 4
C2: (R,S) × (SD, NpD) = 4        C5: (R,S) × (E6S, E6N) = 4
C3: (R,S) × (SD4, NpD) = 4       C6: (R,S) × (C6N) = 2
Policy-единиц: 22 × r1/r2 = 44
Новые B-линии (на A1): SD4, S6bV3, E6N-V3, E6N, C6N = 5 × r1/r2 = 10
Базовая деривация: SD, N1D, NpD, E6S — из AA-1 (A1-B records)
ИТОГО: 27 единиц × r1/r2 = 54 прогона
```

(Ред. 10.09: клетки S6bV3/E6N-V3, спроектированные под C4,
классифицируются по trigger-partition как C5+(a) — маркировка
класса фиксируется в PROTOCOL §1; прогоны и число — те же.)

Конструктивные детали (фиксируются в PROTOCOL; расширений
механизмов нет): третий вектор envver (V3) — тот же канал, для
C4-записи (a) при применимом кандидате; SD4 — расширение горизонта
для C3 (триггер на 3-м failure, проверка остановки на 4-м); C6 —
N-среда only (recovery требует живого мира).

## 5. Критерии (раздельно R и S)

- `stop_on_S`: на S-истории конфигурации — повторений fix-a после
  триггера == 0 и granted→excluded;
- `recovery_on_N`: на N-истории — восстановление (success fix-a)
  достижимо и не позже baseline;
- `Sufficient(right, C) = stop_on_S AND recovery_on_N >= baseline`,
  отдельно для right ∈ {R, S}; возможен расходящийся вердикт
  (напр., R sufficient, S insufficient) — не предполагаем заранее;
- Пред-согласованный исход: «все C INSUFFICIENT по (б)» — допустимый
  результат A (формулировка из решений, узкая); открывает EP-2B.

## 6. Регистрация/инварианты

Как AA-1: траектории (мир/envver/action/outcome/mode), ref_outcome
(S2-only), checks granted/absent, line-state L, L6-walk, audit,
r1≡r2; store append-only; слои v0.6.x не изменяются; адресация =
A1-база (strategy_aa).

## 7. Процедура

1. FROZEN (этот файл) → PROTOCOL.md (evidence_permission2/) →
   ep2_driver.py (база aa1_driver + детекторы C1–C6 + новые
   истории) → preflight (якорь A1-B-N1D; C1-smoke) → RUN 54 →
   анализ → EVIDENCE_PERMISSION2A_REPORT.md.
2. После A: решение о B (temporary semantics) — по слову профессора.

## 8. Артефакты

EVIDENCE_PERMISSION2_DESIGN.md (этот файл, FROZEN EP-2A-часть),
evidence_permission2/PROTOCOL.md, ep2_driver.py, ep2_analyze.py,
EP2_cell_*.json (RAW ×54), EP2_ANALYSIS.txt,
EVIDENCE_PERMISSION2A_REPORT.md. Слои v0.6.x не изменяются.
