# TSARAPINA APPLICABILITY-ADDRESSING-1 (AA-1): PROTOCOL (FROZEN
# 10.09.2026)

База: APPLICABILITY_ADDRESSING1_DESIGN.md (FROZEN 10.09.2026; слово
профессора: DESIGN → ACCEPTED → FREEZE; шесть точек §10 утверждены
с уточнениями). Measurement-only: слои v0.6.x (update/knowledge/
evaluation/strategy.py) НЕ изменяются; ветка адресации — копия-модуль
strategy_aa.py (diff к strategy.py = ровно 3 ханка: пометка, хелпер
_aa1_outcome_is_success, фильтр пула); audit слоёв до/после; анализ —
только после полного RAW.

## 1. Вопрос

> Исчезает ли recency-based захват кандидата failure-knowledge при
> сохранении поведения остальных частей контура?

## 2. Ветки и модули

- **A0** — live strategy.py (v0.6.x как есть; контроль).
- **A1** — strategy_aa.py (no-failure-action): фильтр
  `pool = [r for r in pool if _aa1_outcome_is_success(r)]` строго ДО
  цикла matching (`_match`/eligible); пусто после фильтра → S3
  (существующая ветка, ctx_mismatch). Failure-знания остаются в
  сторе/lineage (append-only); recorder, acquisition (L1–L6),
  lineage_generation не затрагиваются.
- Драйвер выбирает модуль по ветке клетки (importlive strategy.py vs
  spec_from_file strategy_aa.py); update.apply от strategy не зависит.

## 3. Полигон (наследуется из EP-1 PROTOCOL §1–3, FROZEN)

tsasvc; мир w1 (lock.a; fix-a лечит) / w2 (lock.a + lock.q; q скрыт
от symptom и envfact; fix-a мёртв; fix-aq в allowlist); шум-вставка =
lock.n на один эпизод (мир не меняется); envver пишется драйвером
(@V1 → D2/(b) при aw {E,V1}; @V2 → (a)/V). Линия L = (a, absent,
fix-a). Learn-фаза: обычные истории — 1 успех fix-a в w1@V1 (K1);
E6S — learn w1@V1 → w1@V2 (K1 {E,V1}, K2 {E}+obs V[1,2]). Эпизоды
эксплуатационные (suggest-driven; S3-бездействие при пустом
eligible); успех = stable_active (is-active + 1.5 s).

Истории (9; таблицы траекторий — EP-1 PROTOCOL §3):

```
N1D: f@V1 s s          NaD: f@V1 s f@V1 s f@V1 s
NpD: f@V1 f@V1 f@V1 s  N1V: f@V2 s s
SV:  f@V2 f@V2 f@V2    SD:  f@V1 f@V1 f@V1
SM:  f@V1 f@V2 f@V1    NSD: f@V1 s [w2] f@V1 f@V1
E6S: [w2] f@V1 f@V1 f@V1
```

## 4. Режимы и триггеры

- **B** — без вмешательств.
- **R@E4 / S@E4** — событие E4 (D2-серия ≥2: последние 2 члена L —
  failure с (b)-записями; детекция — EP-1-механика) → при первом
  возникновении: R = K исключается из prior_lineage-чтений (обёртка)
  и suggest-кандидатов; S = только из suggest-кандидатов; K =
  последний verified-success член L (K2 на E6S, K1 прочие); постоянно
  в горизонте прогона; simulated, стор не изменяется.
- Проверки механики (granted→excluded / absent→remains) — как EP-1.
- NSD: E4-триггер терминальный (EF-4) — клетка прогоняется, ожидание
  ≡ B (данные полноты).

## 5. Регистрация (RAW)

Траектория эпизодов (мир, envver, action, outcome, mode, strategy_id,
S3-флаги); **outcome выбранного knowledge_ref (ref_outcome)** на
каждом S2-эпизоде (A1: все = success); line-state L после каждого
шага (kid/outcome/aw/kinds); момент триггера; вмешательства; checks;
финальный полный снапшот; audit; созданные знания (aw/gen/source).

## 6. Грид (34 × r1/r2 = 68)

```
B:     A0 × 9 историй = 9;  A1 × 9 = 9          → 18
R/S:   A0 × {NpD, SD, NSD, E6S} × {R, S} = 8;
       A1 × то же = 8                            → 16
Итого: 34 policy-прогона; r1/r2 → 68 прогонов
```

## 7. Preflight (до грида; стоп при провале)

1. py_compile обоих драйверных файлов;
2. **Якорь:** A0|B|N1D|r1 — K-цепочки ≡ EP-1 B-N1D (K1 {E,V1} gen1;
   после s — дивергенция/obs по контракту; L6-walk чист);
3. **A1 smoke:** A1|B|SD|r1 — траектория f,f,f как A0, но
   ref_outcome = success на всех S2-эпизодах (K1 вместо F-серии);
4. audit слоёв до/после.

## 8. Критерии (FROZEN; раздельные утверждения)

- **AA-1 PASS (адресация):** (1) A1-B: failure-refs == 0 (ref_outcome
  == success везде); (2) N-траектории A1 ≡ A0 (действия); (3)
  регрессия чиста (якорь, L6, audit); (4) acquisition не изменён;
  store append-only; (5) никаких новых applicable_when от failure;
  (6) r1 ≡ r2.
- **R/S PASS (permission на правильно адресованном кандидате):**
  A1-R/S@E4 (SD, E6S): повторений fix-a после триггера == 0 и checks
  granted→excluded; A0: повторения == 1 (контроль).
- AA-1 PASS и R/S PASS — РАЗДЕЛЬНЫЕ утверждения; не смешивать.
- Граничные ожидания (не FAIL AA-1): A1-R/S на NpD — S3-остановка →
  восстановление недостижимо (постоянный R; граница для EP-2);
  S3 = stop — состояние AA-1; переход stop→explore — EP-2.

## 9. Запреты

Слои не изменяются; strategy.py файл не изменяется; X-право не
встраивается; никакого trust-числа; стор append-only; после FREEZE
ничего не меняется; анализ после полного RAW; технические
невозможности — execution findings.

## 10. Артефакты

PROTOCOL.md (этот файл), strategy_aa.py (sha 61344099c8f83bd0…),
aa1_driver.py, aa1_analyze.py, AA1_cell_<branch>_<mode>_<hist>_<rep>
.json (RAW), AA1_run_*.log, AA1_audit_*.txt, AA1_ANALYSIS.txt,
APPLICABILITY_ADDRESSING1_REPORT.md (после анализа). Слои v0.6.x не
изменяются.
