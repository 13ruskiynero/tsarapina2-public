# TSARAPINA EVIDENCE-PERMISSION-2 / EP-2A: PROTOCOL (FROZEN
# 10.09.2026, ред. 1 — trigger-partition C4/C5)

База: EVIDENCE_PERMISSION2_DESIGN.md (FROZEN; решения пяти точек).
Measurement-only: слои v0.6.x (update/knowledge/evaluation/strategy.py)
НЕ изменяются; адресация — A1-база (strategy_aa.py, ветка AA-1, sha
61344099…); R/S — simulated (AA-1-механика); audit до/после; анализ —
после полного RAW.

## 1. Классификация C4/C5 — disjoint trigger classes

Правило (дословно по ревью 10.09):
```
failure-событие:
  conflicting-success condition присутствует? → C5
  иначе, failure несёт (a) V-divergence?      → C4
  иначе → не C4/C5
```
Приоритет — C5: если failure удовлетворяет обоим описаниям (следует
за конфликтом успехов И несёт (a)), клетка принадлежит C5;
V-divergence сохраняется как внутреннее свойство evidence и НЕ
меняет классификацию (RAW не вырезается, запись сохраняется
целиком).

Определения: conflicting-success condition := в линии присутствуют
verified-success члены с несовместимыми V-свидетельствами (совокупность
V-значений из aw успехов и values_seen их V-записей содержит ≥2
различных значения). (a) := applicability_observations последнего
failure-члена содержат запись signal=V, relation=disagreement,
source="verified failure".

**Классификационная карта конструкций (пре-прогонная, статическая):**
```
E6S, E6N        : conflict=да,  (a)=нет  → класс C5(b)
S6bV3, E6N-V3   : conflict=да,  (a)=да   → класс C5(a)   [boundary;
                  проектная строка C4 — переклассифицирована правилом]
C1..C3, C6 среды: conflict=нет, (a)=нет  → класс по C1/C2/C3/C6
```

**Лемма (вырождение C4 в A1-контуре; доказательство):** если все
success-эпизоды имеют V-канал (конвенция EP-1/AA-1), то (a)-запись
⟹ conflict присутствует; следовательно, чистый C4 (без конфликта)
носителя не имеет.
Доказательство: (a) требует (i) seen ≠ ∅, (ii) v_now ∉ seen,
(iii) failure-эпизод применил кандидата при векторе {V: v_now}.
A1-пул — success-знания. Применимость: либо aw содержит V=v_now —
но тогда v_now ∈ seen (seen собирает V-значения aw успехов) —
противоречие (ii); либо aw без V-условия ({E:absent}) — а такой aw
у success-знания в E-пути возникает только через V-дивергенцию
(V уходит в obs), т.е. при наличии success-членов с несовместимыми
V-свидетельствами = conflict. ∎
Следствие: C4-ветвь классификатора покрывается unit-тестом
(синтетический line-state), а не прогонами; реальный C4-носитель
потребовал бы success-эпизода без V-наблюдения (расширение
конструкций — вне рамки, решение профессора).

## 2. Полигон и истории

Полигон — EP-1/AA-1 (w1: lock.a, fix-a лечит; w2: lock.a+lock.q,
fix-a мёртв, fix-aq лечит; шум — lock.n на эпизод; envver — канал
драйвера; линия L = (a, absent, fix-a)). V3 — экспериментальное
условие достижимости (a)-записи в A1-контуре (не новый механизм
системы; сохранить в отчёте).

```
SD:      learn w1@V1 → [w2] f@V1 f f
SD4:     learn w1@V1 → [w2] f@V1 f f f
N1D:     learn w1@V1 → [w1] f@V1(n) s s
NpD:     learn w1@V1 → [w1] f@V1(n) f@V1(n) f@V1(n) s
S6bV3:   learn w1@V1, learn wY@V2 → [w2] f@V3 f f
E6N-V3:  learn w1@V1, learn wY@V2 → [w1] f@V3(n) s s
E6S:     learn w1@V1, learn wY@V2 → [w2] f@V1 f f
E6N:     learn w1@V1, learn wY@V2 → [w1] f@V1(n) s s
C6N:     learn w1@V1 → [w1] f@V1(n) s@V1 f@V1(n) s@V1
```

## 3. Триггеры конфигураций (операционно)

```
C1: первый failure-член (fresh-серия длины 1)
C2: fresh-серия длины 2 (f→f)
C3: fresh-серия длины 3 (f→f→f); проверка остановки — следующий шаг
C5: первый failure при conflict=да (в E6-средах — шаг 1)
C6: failure после recovery (паттерн f→s→f; recovery := эпизод,
    применивший candidate K (refs[0]==K) с исходом success)
```
При первом срабатывании — вмешательство на следующем шаге; в
trigger-запись пишется class_actual (C5(a)/C5(b)/C4/C1/C2/C3/C6),
kind записи failure-члена ((a)/(b)), объект K = последний
verified-success член.

## 4. R/S-механика (фиксирована)

AA-1-семантика: R = исключение K из prior_lineage-чтений (обёртка) и
suggest; S = только из suggest; постоянно в горизонте; simulated,
стор append-only. Checks: granted→excluded / absent→remains.

## 5. Регистрация (RAW)

Эпизоды: мир/envver/action/outcome/mode/strategy_id/refs/ref_outcome;
failure-члены с kind (a)/(b); trigger (conf, step, class_actual);
intervention; checks; line_trace; final_snapshot (L6); audit; r1≡r2.

## 6. Матрица и арифметика (ред. 1; число не изменено)

```
       S-среда (триггер)            N-среда (триггер)          Права
C1     SD (шаг 1)                    N1D (шаг 1)                R, S
C2     SD (шаг 2)                    NpD (шаг 2)                R, S
C3     SD4 (шаг 3)                   NpD (шаг 3)                R, S
C5     S6bV3 (шаг 1; (a))            E6N-V3 (шаг 1; (a))        R, S
       E6S (шаг 1; (b))              E6N (шаг 1; (b))           R, S
C6     — (нет S-аналога)             C6N (шаг 3)                R, S
C4     — (класс вырожден: лемма §1; unit-тест ветви в preflight)
```
```
Юниты: C1:4, C2:4, C3:4, C5:8, C6:2 = 22 × r1/r2 = 44
Новые B: SD4, S6bV3, E6N-V3, E6N, C6N = 5 × r1/r2 = 10
Деривация baseline: SD, N1D, NpD, E6S — AA-1 (A1-B)
ИТОГО: 54 прогона
```

## 7. Preflight (до RUN; стоп при провале)

1. py_compile драйвера и анализатора; sha strategy_aa/слоёв.
2. **Unit-тесты классификатора (синтетика, без прогонов):**
   - C5(b): conflict=да, (b)-запись → C5;
   - boundary: conflict=да, (a)-запись → C5 (детерминированно,
     не «по счастливой случайности»);
   - C4-ветвь: conflict=нет, (a)-запись → C4.
3. **Реальные классификационные смоуки (после learn-фазы и 1-го
   failure, без вмешательств):**
   - E6S → class_actual = C5(b); S6bV3 → class_actual = C5(a)
     (boundary на реальном состоянии);
   - якорь A1-B-N1D: K-цепочки ≡ AA-1/EP-1 (K1 {E,V1} gen1, L6 чист).
4. audit LAYERS_UNCHANGED после смоуков.

## 8. Критерии (раздельно R и S; из DESIGN §5)

stop_on_S (повторений fix-a после триггера == 0 и granted→excluded);
recovery_on_N (success fix-a достижим и не позже baseline);
Sufficient(right, C) = stop_on_S AND recovery_on_N >= baseline.
Итог «все C INSUFFICIENT по (б)» — допустимый результат A (узкая
формулировка; открывает EP-2B).

## 9. Запреты

Не смешивать A/B/C; никакого trust-числа; конфигурации — структуры;
strategy_aa не интегрируется; слои v0.6.x frozen; V3 — условие, не
механизм; после FREEZE ничего не меняется; анализ после полного RAW.

## 10. Артефакты

PROTOCOL.md (этот файл), ep2_driver.py, ep2_analyze.py,
EP2_cell_<branch>_<mode>_<hist>_<rep>.json (RAW ×54), EP2_run.log,
EP2_audit.txt, EP2_ANALYSIS.txt, EVIDENCE_PERMISSION2A_REPORT.md.
Слои v0.6.x не изменяются.

## 11. Проведение и execution findings

RUN завершён: 54 клетки + якорь + 2 классификационных смоука; audit
LAYERS_UNCHANGED (все записи); детерминизм r1≡r2 OK; class_actual:
C5a (S6bV3, E6N-V3), C5b (E6S, E6N) — boundary разрешён
детерминированно; L6 чист; ref_outcome==success везде (адресация A1).

**EF-5 (семантика exclusion в симуляции R/S).** Симуляция реализует
исключение как halt: если suggest ВЫБРАЛ исключённый K — эпизод
отменяется (S3). Унаследовано из EP-1/AA-1 (там среды не различали
семантики). Альтернативная pool-семантика: K невидим для suggest →
выбор следующего кандидата. В средах с ≥2 success-кандидатами
(E6-семейство, C5) семантики расходятся: halt-данные дают
recovery=False на N-историях; pool — предсказание — дал бы
восстановление через K1 на N-историях, но повторение через K1 на
S-историях (тот же fix-a, мёртвый в w2). Устойчивость общего
вердикта: при обеих интерпретациях ни одна конфигурация не
sufficient (при halt — провал (б); при pool — предсказанный провал
(а) для C5); локализация провала C5 зависит от семантики. RAW не
переписывается; решение — за профессором; при выборе pool —
дополнительная волна C5+C6 (20 прогонов, отдельные записи).

**EF-5: CLOSED (слово профессора, 10.09.2026).** Формулировка: при
наличии нескольких success-candidates exclusion имеет две возможные
operational semantics, HALT и POOL; EP-2A измерил HALT,
унаследованный из EP-1/AA-1; альтернатива POOL не измерялась — её
предсказание зафиксировано, но finding'ом не считается. Вывод
EP-2A no-sufficient устойчив к выбору HALT/POOL (по предварительному
анализу), но локализация failure для C5 зависит от semantics
exclusion. POOL сохраняется как предсказанная альтернатива для
EP-2B; дополнительная волна (20 прогонов) не требуется.
