# TSARAPINA LINEAGE-PERSISTENCE-3 (LP-3, FAILURE-EVIDENCE-PERSISTENCE):
# ОТЧЁТ (07.09.2026)

Дизайн: LINEAGE_PERSISTENCE3_DESIGN.md (FROZEN 07.09; слово
профессора: «LP-3 FREEZE. 12 прогонов разрешены...»); протокол:
lineage_persistence3/PROTOCOL.md (FROZEN). Прогон: 3 ветки (F0/F1/F2)
× 2 последовательности (P1, P2) × r1/r2 = **12 прогонов** →
LP3_records_<branch>.json (RAW) → lp3_analyze.py → LP3_ANALYSIS.txt
(анализ только после полного RAW). **v0.6 НЕ изменялась** (audit
sha256: LAYERS_UNCHANGED=True ×3; механика LP-2 — recorder (a)/(b),
ветки — in-process-патчи). Полигон без изменений. Детерминизм:
r1 ≡ r2 на всех 6 парах.

## 1. Вопрос и объект

Контроль сохранности выбранной семантики F1 (failure-visible
lineage): переживает ли failure-derived evidence несколько поколений
acquisition (смешение типов failure (a)→(b)), и не возвращается ли V
в applicable_when на K2+. F0/F2 — контрастные контроли.

## 2. K-цепочки (r1; r2 идентичен)

```
F1 P1:  K1 {E,V1}[] → K2 {E}[success,fail_a] → K3 {E}[success,fail_a,fail_b]      OK
F1 P2:  K1 {E,V1}[] → K2 {E}[success,fail_a] → K3 {E}[success,fail_a,fail_b]
        → K4 {E}[success,fail_a,fail_b] (sig не дублируется, refs растут)          OK
F0 P1:  K1 {E,V1}[] → K2 {E}[fail_a] → K3 {E,V2}[fail_b]      (контраст, ожидаемо)
F0 P2:  … K3 {E,V2}[fail_b] → K4 {E,V2}[]                     (контраст, усилен)
F2 P1/P2: K1 {E,V1}[] → K2+ {E}[success] — failure-derived нет (контраст)
```

## 3. Вердикт

**F1 — контроль persistence ПРОЙДЕН (4/4 прогона OK):**
- K2+ aw={E:absent}, V ∉ aw на всех поколениях; reopened-локалитетов
  нет (pivot всегда field-bearing); K1 — honest-норма {E:absent,V:1};
- evidence_signature монотонна: K1∅ ⊆ K2{success,fail_a} ⊆
  K3{success,fail_a,fail_b} (⊆ K4 — тот же набор, БЕЗ дублирования
  повторного (b)); episode_refs растут (provenance coverage
  расширяется на каждом поколении); source="verified failure"
  сохраняется на всех поколениях;
- evidence пережило смешение типов failure (V-change (a) → совпавший
  вектор (b)) через два (P1) и три (P2) цикла acquisition.

**F0-контраст — подтверждён и УСИЛЕН измерением:**
- K2 aw чист (recorder (a) prev-ветка спасает локальную форму — один
  цикл), но K3: V возвращается в condition (aw={E:absent,V:2}, pivot
  = failure (b) без signal) — «формат без семантики F1 не
  персистентен»;
- **новое измерение (сильнее предсказанного): дефект
  самоподдерживающийся.** На поколении 3 (P2, шаг 6) failure@V1 не
  совпал с УЖЕ ИСПОРЧЕННЫМ условием {E:absent,V:2} (recorder (b)
  требует полного совпадения вектора с aw) → recorder вернул None,
  запись не создана, и evidence-цепочка оборвалась: K4 obs=[].
  Испорченное условие ослепляет recorder на следующих информативных
  failure — F0 не просто повторяет дефект, он его усиливает.

**F2-контраст — подтверждён:** aw чист на K2+ всех поколений, но
failure-derived observations отсутствуют полностью (f_entries=0) —
evidence недоступна acquisition через lineage.

**Поведение:** пробы S2 fix-a всюду (поведенческая неразличимость
сохранена); selected knowledge_id: F0 — w1/noise-пробы на failure-
знание (aw=None, legacy-путь), wY/noise2 — узкое {E:absent,V:2};
F1/F2 — свежайшее широкое {E:absent}+obs на всех четырёх мирах.

## 4. Итог цепочки

```
ACQ-1      PASS
v0.6       PASS / FROZEN
AB-1       BOUNDARY / CLOSED
LP-1       F1 ≡ F2 in old polygon
LP-2       DISCRIMINATOR FOUND
F1         ARCHITECTURAL CHOICE (слово профессора)
LP-3       PERSISTENCE CONTROL PASSED (этот отчёт)
v0.6.x     integration (следующий шаг, по слову профессора)
```

Семантика подтверждена на сохранность: lineage обязан сохранять
failure-derived evidence (L3/L4-требования выполнимы), evidence не
имеет права влиять на condition (L2), происхождение не стирается.
Контрасты F0/F2 показывают, ЧТО именно даёт выбор F1: recorder без
семантики спасает один цикл и затем ослепляется собственным
дефектом; exclusion отбрасывает evidence; visible lineage сохраняет
её через поколения.

**Следующий шаг (по слову профессора):** APPLICABILITY_LINEAGE_
INTEGRATION_DESIGN.md (L1–L5) + отдельный integration gate → v0.6.x.
v0.6 остаётся FROZEN до этого слова.

## 5. Закрытие LP-3 (слово профессора, 07.09.2026)

- **F1 persistence: PASS** (выбранная семантика, теперь с
  экспериментальным подтверждением persistence через поколения);
- **F0: self-reinforcing structural failure** — испорченное
  applicable_when способно сделать последующий recorder слепым к
  информативному failure (запись (b) требует совпадения вектора с
  aw), цепочка evidence обрывается, структурная деградация
  усиливается;
- **F2: deliberate evidence exclusion**;
- **behavioral discrimination: absent**; **structural discrimination:
  strong** — один из самых сильных аргументов ветки в пользу
  структурных измерений вместо одного success/failure;
- **v0.6: FROZEN**; **F1: выбранная архитектурная семантика**.
  Различие-схема: F0 — failure → локально спасённая форма → следующий
  acquisition → испорченный pivot → recorder слепнет → деградация
  усиливается; F1 — failure → applicability_observation → следующий
  acquisition → field-bearing success pivot → evidence сохраняется →
  следующее поколение. Поведение при этом одинаковое.
- **Следующий шаг:** APPLICABILITY_LINEAGE_INTEGRATION_DESIGN.md
  (L1–L6, включая новый L6 Structural provenance invariant) →
  FREEZE → отдельный integration gate → v0.6.x. v0.6 не трогается
  до самого gate.

## 6. Артефакты

LINEAGE_PERSISTENCE3_DESIGN.md (FROZEN), lineage_persistence3/
PROTOCOL.md (FROZEN), lp3_driver.py, lp3_analyze.py, LP3_records_
F0/F1/F2.json (RAW, 4 прогона каждый), LP3_run_<branch>.log,
LP3_audit_<branch>.txt (LAYERS_UNCHANGED=True ×3), LP3_ANALYSIS.txt,
LINEAGE_PERSISTENCE3_REPORT.md (этот файл). Слои v0.6 не изменялись.
