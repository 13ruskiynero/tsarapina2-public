# TSARAPINA INTEGRATION GATE v0.6.x: DESIGN (07.09.2026)

**Статус: FROZEN (07.09.2026).** Ревью профессора: baseline-копии
PASS; 18 прогонов PASS (с явной формулой); generation PASS (с
инвариантами); G6 walk PASS; G3 — уточнена формулировка
provenance-критерия. «После этих двух редакторских поправок — FREEZE
INTEGRATION_GATE_V06X_DESIGN.md.» База: APPLICABILITY_LINEAGE_
INTEGRATION_DESIGN.md (FROZEN; L1–L6); v0.6 FROZEN (GATE 24/24) —
baseline, сохраняется до самого gate.

## 1. Что гейтится

Реализация контракта v0.6.x в рабочих слоях (реальный код, БЕЗ
in-process-патчей):
- update.apply: success — acquisition по L2 (pivot = последний
  field-bearing verified-success) + перенос failure-obs членов линии
  в obs по L3 (дедупликация слиянием episode_refs по сигнатуре);
  non-success — нативный recorder (a)/(b) (frozen-формат LP-2/3),
  aw не создаётся и не изменяется;
- update._prior_lineage: L1 (полная релевантная история линии,
  включая failure);
- knowledge: поле lineage_generation; observation entries новых
  знаний: source ∈ {"verified success", "verified failure"} (enum L4),
  episode_refs непустые;
- K1 honest-срез {E:absent,V:1} — норма; strategy-слой НЕ меняется.

## 2. Ограничения реализации

- **Baseline = исполняемый способ отката, а не копия для
  археологического музея.** Порядок:
  ```
  v0.6 frozen → baseline copy → implementation → gate
  ```
  Baseline-копии перед изменением слоёв: update/update.py →
  update/update_v06_baseline.py; knowledge/knowledge.py →
  knowledge/knowledge_v06_baseline.py. Откат — восстановлением
  копий (проверяется работоспособностью, не только наличием файла).
- **Никаких миграций SQLite**: новая семантика проверяется на
  существующей схеме/совместимом расширении (добавочное поле
  lineage_generation в записи knowledge), без «бесплатного бонуса»
  переписанных данных.
- Изменение knowledge.create — только добавление поля
  lineage_generation (None у вызовов без линии); чтение legacy-
  записей не меняется (source-less → success-derived, L5).

## 3. Сценарии (реальный код; грид — явная формула)

P1 и P2 — самостоятельные сценарии НАРЯДУ с S-сценариями:

```
Scenarios:   S0, S1, S2, S3, S4, S5, S6b, P1, P2        (9)
Repetitions: r1, r2                                      (2)
Total:       9 × 2 = 18 прогонов
```

Данные: data_gate_v06x_<seq>_<rep>/ (свежий стор на прогон). Драйвер:
experiments/gate_v06x.py (как lp-драйверы, БЕЗ веток-патчей;
регистрация: снапшоты после каждого шага, prior/pivot/fb_existed на
success-шагах, lineage_generation созданного знания, recorder-тип на
failure-шагах; пробы w1/wY/noise/noise2 после финального шага; audit
слоёв до/после).

## 4. Критерии G1–G6 (PASS/FAIL на реальном коде)

- **G1 (регрессия ACQ-1):** w1→wY: K1 {E:absent,V:1} (honest,
  generation=1); K2 aw=={E:absent}, obs V[1,2] source="verified
  success" (generation=2); V ∉ aw на K2.
- **G2 (AB-1-сценарии):** S1/S3/S4 — reopened-локалитетов 0, aw чист
  на latest (K2+), K1-норма сохранена; S2/S5 — как LP-1/LP-3 (S5 —
  состояние honest).
- **G3 (LP-2-дискриминатор; критерий механизма, не количества
  записей).** S6b final lineage:
  - success-derived observation существует;
  - failure-derived observation существует;
  - обе записи имеют явный source (из enum L4);
  - обе записи имеют episode_refs;
  - failure-derived evidence ∉ applicable_when;
  - applicable_when остаётся success-derived (K2+: aw == {E:absent}).
  Дополнительно S1: obs содержат D2-запись (verified failure) + V
  (verified success) при тех же условиях.
- **G4 (LP-3-persistence):** P1/P2 — evidence_signature монотонна;
  episode_refs растут; повторный (b) не дублируется; source не
  стирается.
  **Инварианты поколений (механические):**
  - если знание принадлежит F1 applicability lineage (learn-путь с
    E): lineage_generation ∈ {1,2,3,...};
  - иначе (legacy-путь): поле absent/None;
  - generation(K1)=1, generation(K2)=2, generation(K3)=3,
    generation(K4)=4 — без пропусков;
  - старое generation не изменяется (append-only);
  - **failure НЕ создаёт новое поколение**: он принадлежит
    переходу между поколениями (K1 success → failure evidence → K2
    success; не «K1 → K1.5 → K2»). Знание failure получает
    поколение следующего success (правило L6: 1 + число
    предшествующих verified-success членов линии).
- **G5 (поведенческая эквивалентность):** пробы w1/wY/noise/noise2
  дают S2 fix-a, идентично v0.6-baseline на тех же сценариях
  (candidate commands, strategy_id). Структурные критерии G1–G4
  проверяются НЕЗАВИСИМО от того, какой legacy candidate случайно
  спасает поведение (проверки на структуре стора, не на выборе
  пробы).
- **G6 (audit + append-only + L6-механический walk по стору).**
  Walk проверяет не только наличие полей, но и СОГЛАСОВАННОСТЬ
  происхождения. Минимальный набор:
  - source ∈ {"verified success", "verified failure"};
  - episode_refs ≠ ∅;
  - lineage_generation присутствует у learn-path знаний;
  - source == "verified failure" → запись только в observations
    (не в applicable_when);
  - applicable_when не содержит failure-derived observation;
  - происхождение каждой observation механически восстановимо
    (source="verified failure" → в сторе существует failure-знание с
    пересекающимися experience_refs и outcome != success;
    source="verified success" → values_seen согласованы с
    дивергенцией success-цепи);
  - generation sequence монотонно возрастает.
  **Важное различие (из LP-2, сохранить):** aw_clean == True ПРИ
  существующем failure-derived evidence — НЕ ошибка сама по себе
  (F1 именно это и вводит). Ошибка — только если failure-derived
  evidence попала в applicable_when ИЛИ её provenance невозможно
  восстановить. G6 не должен запрещать поведение F1.
  Дополнительно: hash слоёв до/после gate-прогонов unchanged
  (реализация уже сделана; прогоны слои не меняют); legacy-стор
  v0.6 читается без изменений; backfill отсутствует.

## 5. Процедура

1. DRAFT → ревью → **FREEZE (07.09.2026; 4 пункта PASS + правки
   G3/грид внесены)** — выполнено.
2. Baseline-копии v0.6 (update/knowledge) + реализация контракта в
   рабочих слоях (по слову профессора; v0.6 frozen → baseline →
   implementation → gate).
3. gate_v06x.py → RUN: 9 сценариев × 2 реплики = 18 прогонов →
   GATE_V06X_records.json (RAW).
4. Анализ по G1–G6 (анализ — после полного RAW) →
   GATE_V06X_ANALYSIS.txt → INTEGRATION_V06X_REPORT.md.
5. Итог: v0.6.x PASS (статус по слову профессора) или FAIL
   (baseline восстанавливается, вопросы в контракт).

## 6. Ревью профессора (решения; все приняты)

1. Baseline-копии (update_v06_baseline.py, knowledge_v06_baseline.py)
   — PASS; baseline = исполняемый откат; без миграций SQLite.
2. Грид 18 прогонов — PASS; формула явно: 9 сценариев (S0, S1, S2,
   S3, S4, S5, S6b, P1, P2) × 2 реплики; P1/P2 — самостоятельные
   сценарии.
3. lineage_generation — PASS с механическими инвариантами:
   learn-path ∈ {1,2,...}, legacy absent/None; K1..K4 = 1..4 без
   пропусков; старое не меняется; failure не создаёт поколение.
4. G6 механический walk — PASS (минимальный набор + различие:
   aw_clean при failure-derived evidence — не ошибка; ошибка — только
   попадание в aw или невосстановимость provenance).
5. G3 — уточнён: критерий механизма (6 пунктов), не количество
   записей.

## 7. Артефакты

INTEGRATION_GATE_V06X_DESIGN.md (этот файл, FROZEN),
update/update_v06_baseline.py + knowledge/knowledge_v06_baseline.py
(исполняемый откат), реализация контракта в update.py/knowledge.py,
experiments/gate_v06x.py, GATE_V06X_records.json (raw),
GATE_V06X_ANALYSIS.txt, INTEGRATION_V06X_REPORT.md. Слои v0.6 не
изменяются до слова профессора на реализацию.
