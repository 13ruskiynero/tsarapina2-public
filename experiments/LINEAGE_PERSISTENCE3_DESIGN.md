# TSARAPINA LINEAGE-PERSISTENCE-3 (LP-3, FAILURE-EVIDENCE-PERSISTENCE):
# DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026).** Ревью профессора: «LP-3 FREEZE.
12 прогонов разрешены. Анализ только после полного RAW. v0.6 не
трогать.» Решения ревью — раздел 8 (все приняты). База: F1 выбрана
как архитектурная семантика (слово профессора 07.09.2026;
LINEAGE_PERSISTENCE2_REPORT.md §6); LP-2 CLOSED; v0.6 FROZEN — слои
не изменяются (in-process-патчи; механика LP-2: recorder (a)/(b),
ветки F0/F1/F2). LP-3 не пересматривает выбор F1: он проверяет
сохранность выбранной persistence-семантики.

## 1. Вопрос

LP-2 доказал: F1 МОЖЕТ передать failure-derived observation в новое
знание (один цикл acquisition). LP-3 проверяет persistence через
НЕСКОЛЬКО поколений lineage:

> Не исчезает ли failure-derived observation при следующем цикле
> acquisition? И главное: не возвращается ли V самопроизвольно в
> applicable_when на последующих поколениях?

Если evidence теряется на merge второго поколения — мы просто
переместили проблему с prior[-1] на следующий merge, и выбор F1
нужно пересматривать. Это контроль сохранности, не поиск новой
теории.

## 2. Ожидаемая цепочка поколений (F1; K-поколения по success)

```
K1 (w1):           aw={E:absent,V:1} (honest Q1-срез, норма) obs=[]
K2 (wY, после noise2@V2 — failure (a) V-change 1→2):
                   aw={E:absent}  obs=[V[1,2] success-derived,
                                        V-change (a) failure-derived]
K3 (wY, после noise@V1 — failure (b) outcome_disagreement):
                   aw={E:absent}  obs=[V[1,2] success,
                                        (a) failure, (b) failure]
K4 (P2, после повторного (b)):     obs=[V[1,2] success,
                                        (a) failure, (b) failure
                                        (episode_refs слиты)]
```

V ∉ aw на всех поколениях K2+; evidence-сигнатуры монотонно
накапливаются (не теряются, не дублируются).

## 3. Последовательности (узкий грид; FREEZE-решение 1)

P1: w1 → noise2 → wY → noise → wY
   (K1..K3; failure1 = V-change (a) @V2; failure2 = совпавший вектор
   (b) @V1 против aw={E:absent}; FREEZE-решение 2: второй failure
   остаётся — он проверяет перенос evidence при смешении (a)→(b))
P2: w1 → noise2 → wY → noise → wY → noise → wY
   (K1..K4; failure3 = повторный (b) → проверка дедупликации/слияния
   episode_refs без потери и без дублирования)

Миры и recorder — как LP-2 (noise2 — тот же n-based failure,
меняется только envver; полигон без изменений).

Грид: 3 ветки (F0/F1/F2) × 2 последовательности (P1, P2) × r1/r2 =
**12 прогонов**. F1 — объект контроля; F0 и F2 — контрастные
контроли (F0 остаётся: recorder спасает локальную форму против
lineage-семантики, сохраняющей структуру).

## 4. Регистрация (после КАЖДОГО шага; RAW)

Как LP-2: полный снапшот knowledge-версий после каждого шага
(append-only); на success-шагах ДО apply: prior_ids, fb_existed,
pivot_id, pivot_has_aw, created_knowledge_id; на failure-шагах — тип
записи recorder'а (a)/(b); outcome; пробы после финального шага
(w1/wY/noise/noise2): selected knowledge_id с aw.

## 5. Критерии

1. **F1 (основной):** на каждом success-поколении K2+: aw_clean
   (V ∉ aw; aw=={E:absent}); reopened_aw=0; reopened_locus=0.
   K1 — honest Q1-срез {E:absent,V:1}: НОРМА, не дефект (FREEZE-
   решение 3: критерий V ∉ aw начинается с K2, где уже есть
   приобретённая V-дивергенция).
2. **Монотонность evidence (F1; формализация ревью):** раздельно:
   - **evidence_signature(K)** = множество уникальных
     нормализованных applicability observations (без episode_refs):
     sig(K1) ⊆ sig(K2) ⊆ sig(K3) (⊆ sig(K4)); повторный (b) в P2
     НЕ создаёт вторую семантически одинаковую observation;
   - **episode_refs(K)** = provenance coverage: для каждой сигнатуры,
     присутствующей в поколениях g-1 и g: refs(K_g) ⊇ refs(K_{g-1})
     (повторный (b) может РАСШИРЯТЬ provenance, не меняя сигнатуру);
   - failure-derived присутствуют: (a) на K2+, (b) на K3+;
     success-derived (V[1,2]) сохраняется на всех K2+.
3. **Происхождение:** failure-derived записи сохраняют source=
   "verified failure" на всех поколениях (различимость success/
   failure не стирается).
4. **F0-контраст (ожидание):** K2 aw чист (recorder (a) prev-ветка —
   «recorder спасает локальную форму»), K3 aw={E:absent,V:2} — V
   возвращается в condition (pivot = failure (b) без signal) —
   «lineage-семантика (F1) сохраняет структуру; формат без неё — нет».
5. **F2-контраст (ожидание):** aw чист на всех поколениях,
   failure-derived obs отсутствуют (evidence отбрасывается).
6. Детерминизм r1 ≡ r2; audit sha256 до/после; пробы (вторично).

## 6. Предсказания (НЕ результаты)

- F1-P1: K1 honest {E:absent,V:1}; K2 aw={E:absent}, sig={(V-succ),
  (a)}; K3 aw={E:absent}, sig={(V-succ),(a),(b)} — evidence пережило
  смешение (a)→(b) через два цикла acquisition; V в aw не вернулся.
- F1-P2: K4 sig == K3 sig (без дублей), refs((b)) расширены — evidence
  пережило три цикла.
- F0-P1: K2 aw чист (sig={V-fail(a)-merged}); K3 aw={E:absent,V:2}
  (дефект возвращается; (a)-evidence выпадает из latest-цепи).
- F2-P1/P2: aw чист; fail-entries нет ни на одном поколении.
- Пробы: S2 fix-a всюду; F1 — свежайшее широкое {E:absent}+obs.

## 7. Запреты

- Слои v0.6 не изменяются (in-process-патчи; audit до/после);
- полигон без изменений; noise2 — не новый класс мира (envver);
- выбор F1 LP-3 не пересматривает;
- **провал F1 на K3/K4 (evidence исчезает или V возвращается в aw) —
  настоящий провал выбранной persistence-семантики: фиксируем
  boundary, затем пересматриваем merge-семантику; код сразу НЕ
  чинить (FREEZE-решение 4)**;
- неизменны: v0.6, все реальные файлы слоёв, F1 как выбранная
  семантика, append-only история, distinction applicable_when /
  applicability_observations (FREEZE-решение 5);
- после FREEZE ничего не меняется; анализ — после полного RAW.

## 8. Ревью профессора (FREEZE-решения; все приняты)

1. Грид 12 прогонов оставить (F0/F1/F2 × P1/P2 × r1/r2) — принято.
2. Второй failure в P1 оставить ((a)→(b) смешение типов) — принято.
3. K1 — honest-норма {E:absent,V:1}; критерий V ∉ aw с K2 — принято.
4. Провал F1 на K3/K4 = настоящий провал persistence-семантики:
   сначала boundary, затем пересмотр merge-семантики; не повод сразу
   чинить код — принято.
5. Неизменны: v0.6; реальные файлы слоёв; F1 как выбранная
   семантика; append-only; distinction aw/obs — принято.
6. Монотонность — по нормализованной evidence-сигнатуре (без
   episode_refs), provenance coverage отдельно — принято, раздел 5.2.

## 9. Процедура

1. DRAFT → ревью → **FREEZE (07.09.2026; решения 1–6 приняты;
   прогоны разрешены)** — выполнено.
2. lineage_persistence3/PROTOCOL.md (frozen).
3. lp3_driver.py: механика lp2_driver (recorder (a)/(b), ветки
   F0/F1/F2), последовательности P1/P2.
4. RUN: 3 × 2 × 2 = 12 прогонов → LP3_records_<branch>.json (RAW).
   Анализ — только после полного RAW.
5. lp3_analyze.py → LP3_ANALYSIS.txt: критерии раздела 5; K-цепочки;
   evidence_signature и episode_refs раздельно; F0/F2-контрасты;
   r1≡r2; audit.
6. LINEAGE_PERSISTENCE3_REPORT.md; v0.6 остаётся FROZEN. Затем —
   APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md (L1–L5) + integration
   gate по слову профессора.

## 10. Артефакты

LINEAGE_PERSISTENCE3_DESIGN.md (этот файл, FROZEN),
lineage_persistence3/PROTOCOL.md (frozen), lp3_driver.py,
lp3_analyze.py, LP3_records_<branch>.json (raw), LP3_run_<branch>.log,
LP3_audit_<branch>.txt, LP3_ANALYSIS.txt,
LINEAGE_PERSISTENCE3_REPORT.md. Слои v0.6 не изменяются.
