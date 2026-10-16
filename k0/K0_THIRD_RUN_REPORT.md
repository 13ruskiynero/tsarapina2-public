# K0 — ОТЧЁТ: ТРЕТИЙ ЛОКАЛЬНЫЙ ПРОГОН K0-M1 (сид 101, v28), 2026-10-16

Статус: **серия ЗАВЕРШЕНА — первый завершённый прогон серии K0-M1/101.**
Прогон дошёл до F4: `final_present=true`, метрики посчитаны. Стоп-причины нет;
`malformed=0` (ни одного отклонённого блока F2, `rejections=[]`). После старта
ничего не перезапускалось, не исправлялось и не «подгонялось»; правок по ходу
не было.

Основание: решение постановщика 2026-10-16 («да, v28», передано дословно в
`K0_PROTOCOL_v28_ACT.md` §1); акт `K0_PROTOCOL_v28_ACT.md`
(sha256 `04426919c1926df48eaf397a787b1317a32d0e0f050a5d15394e1f8c13b5abf5`);
каталог прогона `runs/run_K0-M1_101_v28/`.

## 1. Канарейка (сверка D1)

- F1-промпт: 1 725 Б; локальная оценка 578 ток; сервер
  `prompt_eval_count` = 578 → расхождение **0.0%**.
- `eval_count` = 126 (модель завершила ответ сама, лимит 256 не задет).
- `preflight_canary.json` и `calls/0001_F1_a1.response.txt` **побайтово совпали**
  с прогоном v27 (см. §9) — при temp 0 тот же F1-промпт дал идентичный ответ.

## 2. Фаза F1 — пройдена с первой попытки

- `forecast_status: F1/1 → ok`; записаны 9 прогнозов:
  - `disappeared`: O1 T=1 H=0; O1 T=2 H=1;
  - `present`: O2 T=2 H=1; O2 T=2 H=2; O3 T=2 H=0; O3 T=2 H=1; O3 T=2 H=2;
    O4 T=2 H=1; O4 T=2 H=2.

## 3. Фаза F2 — полный бюджет, ноль отказов

- 16 вызовов F2, бюджет 16 → 0 израсходован полностью; отказов нет
  (`malformed=0`).
- Действия по порядку (P<n> — исполненные пробы, исход раскрыт):
  - P1 `probe O3 T=1 H=0` → present;
  - P2 `probe O1 T=0 H=2` → present;
  - P3 `repeat` → O1 T=0 H=2 → present;
  - P4 `repeat` → O1 T=0 H=2 → present;
  - P5 `probe O3 T=2 H=0` → **disappeared**;
  - P6 `probe O2 T=1 H=0` → present;
  - P7 `probe O3 T=1 H=0` → **disappeared** (клетка P1 дала другой исход —
    после единственного `state_change`, см. ниже);
  - P8 `probe O4 T=1 H=0` → present;
  - P9–P16 `repeat` → O4 T=1 H=0 → present (восемь повторов подряд).
- Повторов (`repeat`): 10 из 16 действий.
- Единственный `state_change`: после P5 объект O3 сменил состояние
  present → disappeared (запись `state_change`, `action_ref = P5`).
- P5 раскрыл батарейную клетку `O3 T=2 H=0` → исключена из E
  (`exclude_reason: revealed_present`).

## 4. Фазы F3 и F4

- F3: `forecast_status: F3/1 → ok`; 9 прогнозов. Изменения против F1 на
  E-клетках: O1 T=2 H=1 → present (было disappeared); O1 T=1 H=0 → present
  (было disappeared); O3 T=2 H=0 → disappeared (было present; в E не входит).
- F4: **FINAL получен** (`final_present=true`). Текст FINAL:
  «Объект находится в состоянии 'present', если для него выполняется условие
  (T=0 И H=2) ИЛИ (O1 и T=0 и H=0) ИЛИ (O3 и T=0 и H=0) ИЛИ (O4 и T=0 и H=0)
  ИЛИ (O2 и T=1 и H=0) ИЛИ (O3 и T=1 и H=2) ИЛИ (O2 и T=1 и H=2) ИЛИ
  (O4 и T=1 и H=2).»

## 5. Метрики (derived/metrics.json)

- `n_E = 8` (E-набор: 8 из 9 B-клеток; `e_min_ok = true`);
- `acc_before = 0.625` · `acc_after = 0.625` · `improvement = 0.0` ·
  **`o1_pass = false`**;
- `final_present = true` · `malformed = 0`;
- контекст: `approx_tokens_max = 1270` (порог 3900; `warn_calls = 0`);
- итоги сессии: вызовов 19 из 30; токенов 19 697 из 100k.

## 6. Аудит (derived/audit.json)

- `structural_full = false` · `agent_full = false` · `agent_valid_full = false` ·
  `s6_complete = true` · `correct_s4 = null` · `status_hint = «normal»`.
- Звенья S1–S5: не найдены (`found=false`); S4 — «нет вердикта после раскрытия
  исхода с валидной ссылкой» (записей `VERDICT` в журнале нет).
- S6: `structural=true`, `agent=true` (предзапись до действия:
  `pre_before_action=true`; порядок «вердикт после исхода»:
  `verdict_after_outcome=true`).
- Открытые пункты аудитора — как в `audit.json` (в т.ч. связь
  `probe_outcome` ↔ `action_requested`, A24).

## 7. Классификация и границы

- Полнота серии: F1 ✓, F2 ✓ (полный бюджет), F3 ✓, F4/FINAL ✓, F5-метрики ✓.
- Критерий O1 (измеримое улучшение предсказаний): **не пройден**
  (`improvement = 0.0`).
- Интерпретации поведения как «способности/неспособности» здесь не делаются;
  решение о статусе серии (valid и дальнейшие шаги) — за постановщиком.

## 8. Наблюдения для решения (без действий)

1. Формат-правка v28 (правило 1) сняла проблему второго прогона: 0 отказов
   формата, серия впервые прошла целиком до FINAL.
2. Расход бюджета: 10 из 16 действий — `repeat` одной клетки (O4 T=1 H=0 —
   восемь раз подряд); контур Q/H/VERDICT/DECISION не использовался
   (звенья S1–S5 не найдены).
3. F1-ответ детерминирован: `preflight_canary.json` и
   `calls/0001_F1_a1.response.txt` побайтово совпадают с прогоном v27.

## 9. Контрольные суммы (sha256)

    preflight_canary.json                99df7543defc2cd7c7b4af416f7a883b76f10f456772f3fa84b553b134f4f0ac
    passport/passport.json               c40165d20a2ae2395c4ed85a6c636a881d99fed433f673b38dff526dd4cf3da5
    raw/journal.jsonl                    b37153e2b54c969af764285a2d67e492139e38b768f973e1e71b1740cfa63722
    raw/calls/0001_F1_a1.response.txt    f47c2d99fb5cb686d00e00fbb75a84de26365b0d46134c5b7989c0ae94753358
    raw/calls/0002_F2_a1.response.txt    90a684c1a24683065136a7b37b1b0ef6dc242d328092ab889edac161586590f6
    raw/calls/0017_F2_a1.response.txt    15d15f2793eaf7ef0eccfdc97c962b0620ad64767ab78975842d0ae00857ff47
    raw/calls/0018_F3_a1.response.txt    0cae8f5c2816e9ed7ec73bf1064dd6c27c898b95c72d5758f1b780ad85788114
    raw/calls/0019_F4_a1.response.txt    e4f180b75600cf3908c1d59fb27037a9e7539b7808d9fc9ccf28e3904c842402
    derived/e_set.json                   2cd6355019e7ce969423ad8c358e1f3c2dbf595ce5841d1a8c0b2ef811529b67
    derived/forecasts.json               73fd95137611546eff721384fa652e6baa5fe16970394f598bbf22ee5df41975
    derived/metrics.json                 da312ef740118727226f4dd2e8dfbf3de2afd742744b3463ec3c3c0a68ed5f22
    derived/audit.json                   6d2e9065c4c33a9607b1817186edc0c5fc06ada8db624c921886d2c1857cdec7
    derived/rejections.json              4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

Отчёт подготовлен по фактическим данным артефактов прогона (без интерпретаций).
