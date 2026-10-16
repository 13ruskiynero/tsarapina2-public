# TSARAPINA LINEAGE-PERSISTENCE-3 (LP-3): PROTOCOL (FROZEN 07.09.2026)

База: LINEAGE_PERSISTENCE3_DESIGN.md (FROZEN 07.09.2026; слово
профессора: «LP-3 FREEZE. 12 прогонов разрешены. Анализ только после
полного RAW. v0.6 не трогать»). Measurement-only; v0.6 НЕ изменяется
(recorder и ветки — in-process-патчи драйвера, механика LP-2); audit
sha256 до/после каждого прогона; полигон без изменений (noise2 — тот
же n-based failure, меняется только envver). F1 — выбранная
архитектурная семантика; LP-3 проверяет её сохранность, выбор не
пересматривает.

## 1. Вопрос

Persistency failure-derived observations через несколько поколений
lineage под F1; V не возвращается в applicable_when на K2+.

## 2. Ветки, последовательности, грид

F0: v0.6-семантика (контраст: recorder спасает локальную форму).
F1: field-bearing pivot + перенос failure-obs в obs (никогда в aw) —
объект контроля.
F2: failure-excluded lineage (контраст: evidence отбрасывается).

P1: w1, noise2, wY, noise, wY      (K1..K3; failure (a) @V2, затем
                                    совпавший вектор (b) @V1)
P2: w1, noise2, wY, noise, wY, noise, wY   (K1..K4; повторный (b))

Грид: 3 ветки × 2 последовательности × r1/r2 = 12 прогонов. Данные:
data_lp3_<branch>_<seq>_<rep>/ (свежий стор на каждый прогон).

## 3. Регистрация (после КАЖДОГО шага; RAW)

Снапшот knowledge-версий стора после каждого шага; на success-шагах
ДО apply: prior_ids, fb_existed, pivot_id, pivot_has_aw,
created_knowledge_id; тип recorder-записи на failure-шагах; outcome;
пробы (w1/wY/noise/noise2) после финального шага: selected
knowledge_id с aw.

## 4. Критерии (DESIGN р.5)

1. F1: K2+ aw_clean (aw=={E:absent}, V ∉ aw), reopened_aw=0,
   reopened_locus=0; K1 — honest-норма {E:absent,V:1}.
2. Монотонность (раздельно):
   - evidence_signature(K) — уникальные нормализованные obs (без
     episode_refs): sig(K1) ⊆ sig(K2) ⊆ sig(K3) (⊆ sig(K4)); повторный
     (b) не создаёт второй семантически одинаковой observation;
   - episode_refs(K) — provenance coverage: refs(K_g) ⊇ refs(K_{g-1})
     для каждой общей сигнатуры;
   - (a) на K2+, (b) на K3+; success-derived V[1,2] на всех K2+.
3. Происхождение: source="verified failure" сохраняется.
4. F0-контраст: K2 aw чист; K3 aw={E:absent,V:2} (ожидание).
5. F2-контраст: aw чист; fail-entries=0.
6. Детерминизм r1 ≡ r2; audit; пробы (вторично).

## 5. Вердикт (после RAW и анализа)

- F1: K-цепочки по P1/P2 — evidence пережило 2–3 цикла (sig монотонна,
  refs расширяются, V ∉ aw на K2+) = контроль ПРОЙДЕН; если evidence
  исчезает или V возвращается в aw на K3/K4 = настоящий провал
  выбранной persistence-семантики: фиксируем boundary, пересматриваем
  merge-семантику (код не чинить);
- F0-контраст: recorder спасает локальную форму (K2) против
  lineage-семантики, сохраняющей структуру (F1 K3) — фиксируется;
- F2-контраст: evidence недоступна lineage — фиксируется;
- «Победитель» не пересматривается (F1); v0.6 остаётся FROZEN.
  После вердикта — APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md
  (L1–L5) + integration gate по слову профессора.

## 6. Артефакты

PROTOCOL.md (этот файл, FROZEN), lp3_driver.py, lp3_analyze.py,
LP3_records_<branch>.json (RAW ×3), LP3_run_<branch>.log,
LP3_audit_<branch>.txt, LP3_ANALYSIS.txt,
LINEAGE_PERSISTENCE3_REPORT.md (после анализа). Слои v0.6 не
изменяются.
