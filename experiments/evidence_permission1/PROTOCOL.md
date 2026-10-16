# TSARAPINA EVIDENCE-PERMISSION-1 (EP-1): PROTOCOL (FROZEN 07.09.2026)

База: EVIDENCE_PERMISSION1_DESIGN.md (FROZEN; EF-1: полигон —
q/fix-aq, STALE_EXACT2-механика). Measurement-only; v0.6.x и слои
(knowledge/update/strategy/evaluation) НЕ изменяются; вмешательства
R/S/X — simulated (in-process, стор append-only); audit sha256
до/после; якорь до грида; анализ — только после полного RAW.
Грид, h=3, правила участия — FROZEN, не меняются.

## 1. Полигон и миры

tsasvc (tsasvc_daemon.sh v3: демон падает при ЛЮБОМ
/run/tsasvc.lock.*; active = sleep). Миры:
- w1: lock.a; fix-a лечит (rm a + start). envver пишется драйвером
  (/run/tsasvc.envver, '1'|'2').
- w2 (устаревание, EF-1/q): lock.a + lock.q; q скрыт от symptom И
  от envfact (HIDDEN_FLAGS) → адрес (a, absent) един в w1/w2;
  fix-a снимает только a → q остаётся → демон падает (failure);
  fix-aq (rm a+q + start; в allowlist) лечит w2 и w1.
- Шум-вставка (синтетическая, STALE M3): мир w1 НЕ меняется;
  на ОДИН эпизод добавляется lock.n (n скрыт от симптома/envfact);
  fix-a снимает a, n остаётся → failure; после эпизода lock.n
  снимается (мир вернулся). Тип recorder-записи вставки задаётся
  envver эпизода: @V1 → вектор совпал с aw {E:absent,V:1} → (b)/D2;
  @V2 → V2 ∉ seen{1} → (a)/V.
- E-контекст всех эпизодов: ctx_extra = "absent" (extra нет ни в
  w1, ни в w2; q не envfact). Линия знания: (a, absent, cmd).

## 2. Эпизоды

**learn-фаза** (драйвер показывает лечение; действие фиксировано):
обычные истории: 1 успешный learn-эпизод fix-a в w1 (envver=1) →
K1 (a, fix-a) aw={E:absent,V:1}, gen=1. E6-истории: learn w1@V1
(fix-a) → learn w1@V2 (fix-a) → K2 {E:absent}+obs V[1,2]
(conflicting success в сторе до фазы проверки).
Успех: служба active после действия (stable_active: is-active +
1.5 s стабильность).

**фаза проверки (эксплуатационные эпизоды)** — последовательность
по истории (таблица §3). Каждый эпизод:
1. env_set мира эпизода (w1/w2, ±lock.n для шума, envver).
2. suggest(store, problem=symptom=a, ctx_now="absent",
   obs_now={E:"absent", V: envver}) → кандидаты.
3. Если policy X уже сработала и это «explore-эпизод» (следующий
   после триггера): действие = fix-aq (минуя suggest). Если X не
   сработала и кандидат есть: действие = команда кандидата (fix-a).
   Если кандидатов нет (eligible пуст, включая simulated R/S-
   исключения): **S3-бездействие**: действие не исполняется, apply
   не вызывается, фиксируется эпизод S3; мир эпизода остаётся
   (повторная попытка на следующем эпизоде той же истории).
4. Исполнение → outcome (success | failure по stable_active;
   failure-исход пишется apply'ем с recorder-записью).
5. apply(experience, outcome) (recorder v0.6.x на failure).
6. После эпизода: триггер-проверка policy (раздел 4); при первом
   срабатывании — вмешательство (раздел 5), фиксация момента.

S-истории: после learn-фазы мир переключается w1→w2 (env_set w2);
fix-a во всех эпизодах даёт failure (серия). N-истории: мир w1;
failure только на шум-вставках. NSD: шум-вставка@V1, success@V1,
затем w1→w2 и два failure@V1.

## 3. Истории (FROZEN; f = failure fix-a, s = success fix-a)

```
N1D: f@V1 s s            N1V: f@V2 s s
NaD: f@V1 s f@V1 s f@V1 s
NpD: f@V1 f@V1 f@V1 s    NpV: f@V2 f@V2 f@V2 s
NpM: f@V1 f@V2 f@V1 s
SD:  f@V1 f@V1 f@V1      SV:  f@V2 f@V2 f@V2
SM:  f@V1 f@V2 f@V1      NSD: f@V1 s |смена w2| f@V1 f@V1
E6N: f@V1 s s            E6S: f@V1 f@V1 f@V1 (сразу в w2 после learn w1→wY)
```

Примечания: в N-историях «s» — success fix-a в w1 (после шума lock.n
снят). В S-историях все f — fix-a в w2 (q не снимается). В SM/NpM
чередование V1/V2 задаёт типы записей: V1-эпизод → (b)/D2, V2-эпизод
→ (a)/V. Baseline (B) = та же история без вмешательств.

## 4. Триггеры (структура стора; момент первого возникновения)

Линия L = (a, absent, fix-a); члены — knowledge-записи линии,
упорядоченные по created_at; тип члена — outcome из context
(success | failure); тип записи obs — (a)-запись (signal=V,
source=verified failure) / (b)-запись (outcome_disagreement).
«Свежие» члены = после последнего success-члена L.

- E1: последний член L — failure с (a)-записью (и нет success после
  него).
- E2: последний член L — failure с (b)-записью.
- E3: последние 2 члена L — failure, ОБА с (a)-записью (гомогенная
  V-серия ≥2).
- E4: последние 2 члена L — failure, ОБА с (b)-записью.
- E5: последние ≥2 членов L — failure, и среди них есть и (a)- и
  (b)-записи (смешанная серия ≥2).
- E6: в L ≥2 success-члена с разным V в applicable_when
  (conflicting success); проверяется на 1-м эпизоде фазы проверки
  (момент 0), ДО failure (контроль: право без failure-сигнала).

Policy однократна: вмешательство применяется при ПЕРВОМ
возникновении события в прогоне; момент фиксируется в records.

## 5. Вмешательства (simulated; стор не изменяется)

- R(K): K (= последний verified-success член L на момент триггера)
  исключается из prior_lineage-чтений драйвера и из suggest-
  кандидатов (in-process фильтры; records: simulated_retract={K,
  step}).
- S(K): K исключается только из suggest-кандидатов (lineage-
  чтения без изменений).
- X: следующий за триггером эпизод исполняет fix-aq (минуя
  suggest); apply штатно (знания создаются контрактом v0.6.x).
Проверки механики в каждом прогоне с вмешательством: (i) granted:
после триггера suggest (с симуляцией) не содержит K; (ii) absent
(baseline): suggest содержит K (кандидат остаётся). Несоответствие —
execution finding, прогон помечается.

## 6. Ожидания (expected) и статусы

**expected ≠ результат.** expected sufficient / expected INSUFFICIENT
(раздел 9 DESIGN) — гипотезы дизайна. Итоговый статус клетки
выставляется ТОЛЬКО анализатором по records:
- X-клетка SUFFICIENT: (correctness) на всех S-историях события
  достигнут success fix-aq в горизонте (baseline: нет); (harm/
  no-harm) на всех N-историях события восстановление (success
  fix-a) не позже baseline.
- R/S-клетка SUFFICIENT: на всех N-историях события восстановление
  не заблокировано (success достижим, не позже baseline); на всех
  S-историях события после триггера 0 повторений fix-a (baseline:
  ≥1). R/S не создают success сами.
- INSUFFICIENT: условие не выполнено (per-channel, не
  «невозможно»).
- Клетки вне грида: derived (лемма L-RS1 — проверяется
  injection-тестами), undefined (R/S × E6), «−» (≡ baseline).

## 7. Регрессионный якорь (precondition)

B-прогоны N1D/N1V до основного грида: K1 {E:absent,V:1} gen1;
s-эпизод после шума: дивергенция/obs по контракту v0.6.x; L6-walk
чист; траектории ≡ GATE-эквивалентам. Не совпало — стоп, execution
finding.

## 8. Грид и артефакты

50 policy-прогонов × r1/r2 = 100 (матрица участия — DESIGN §8;
«−»-клетки не прогоняются). Прогон: свежий стор
data_ep1_<policy>_<hist>_<rep>/; регистрация: траектория эпизодов
(мир, действие, outcome, S3-флаги), снапшоты стора после каждого
эпизода, момент триггера, вмешательства, suggest-проверки; audit
слоёв до/после каждого чанка. Артефакты: PROTOCOL.md (этот файл),
ep1_driver.py, ep1_analyze.py, EP1_records.json (RAW, один файл на
чанк → конкатенация), EP1_run_*.log, EP1_audit_*.txt,
EP1_ANALYSIS.txt, EVIDENCE_PERMISSION1_REPORT.md. Слои v0.6.x не
изменяются; отклонения — execution findings, не переделка дизайна.
