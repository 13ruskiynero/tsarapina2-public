# LONG-1A: ОТЧЁТ (11.09.2026)

**Статус: PASS → CLOSED (вердикт профессора, 11.09);
12 runs; 57 checks, FAIL=0; audit 12/12; r1 ≡ r2 — вплоть до
траектории предложений и исходов.**

Вопрос:

> Can repeated verified interactions cause externally stored
> Knowledge to alter subsequent Strategy/LLM proposals or action
> outcomes over a longitudinal episode sequence?

Ответ: **да — контур демонстрирует временную динамику**: накопление
транспортируется в каждый следующий запрос (ctx_src 0→5),
L-chain invariant выполнен на всех переходах, предложения Gemma
менялись между эпизодами (в отличие от LOOP-0), и после
накопления (E4) оба прогона достигли verified success.

## 1. Траектория (обе реплики идентичны)

```
E0 seed  w1    fix-a (seed) → success          K1 fix-a/success
E1 LLM   w1    start → partial                 K2 start/partial
E2 LLM   шум   fix-a → partial                 K3 fix-a/partial
E3 LLM   шум   restart → partial               K4 restart/partial
E4 LLM   w1    fix-a → SUCCESS                 K5 fix-a/success
E5 LLM   w1    start → partial                 K6 start/partial
ctx_src:        0 → 1 → 2 → 3 → 4 → 5
```

## 2. Проверки

```
A-L1-1  полные записи + audit (12/12);
A-L1-2  каждый verified consequence → knowledge_diff;
A-L1-3  retrieved-связи восстановимы (counters §3);
A-L1-4  динамика: для каждого N→N+1 context содержит ≥1 prior
        verified knowledge; L-chain: first_seen(K) < n для всех
        retrieved K;
A-L1-5  деградации нет: ворота/append-only/chain kid→exp→episode
        на всех runs;
A-L1-6  r1 ≡ r2 (структурные поля; совпали и траектории).
57/57 PASS.
```

## 2a. LONG-1A establishes / does NOT establish (whiteboard)

```
establishes:
  persistent external Knowledge;
  longitudinal retrieval;
  context transport;
  observed proposal/action dynamics.
does NOT establish:
  learning law;
  stable policy adaptation;
  monotonic improvement;
  forgetting;
  generalization;
  long-term competence.
```

## 3. Counters (после EF-14; observability)

```
K1 fix-a    first=0 ret=5 act=2 vs=1 vf=1
K2 start    first=1 ret=4 act=1 vs=0 vf=1
K3 fix-a    first=2 ret=3 act=1 vs=1 vf=0
K4 restart  first=3 ret=2 act=0
K5 fix-a    first=4 ret=1 act=0
K6 start    first=5 ret=0
(числа совпадают между r1/r2)
```

## 4. Наблюдения (не критерии)

```
O1  proposal_diff менялось на КАЖДОМ шаге E2..E5 (в LOOP-0 —
    ни разу): start → fix-a → restart → fix-a → start.
O2  E4: после накопления контекста (fix-a→success; start→partial;
    fix-a→partial; restart→partial) предложение fix-a дало
    verified success — «observable change ... attributable
    through the recorded chain to prior verified Knowledge»
    (наблюдение, без интерпретаций об «обучении»).
O3  E5: после success снова start → partial (возврат к прежней
    гипотезе модели; наблюдение).
O4  Hа шумовом участке (E2/E3) система сменила предложение и
    сохранила структуру контура; шум — условие траектории,
    не robustness-гипотеза.
O5  Пять фиксов не привели к разрушению контура: знания растут,
    адресация/ворота стабильны.
```

## 5. EF-14 (execution finding; исправлено)

Счётчики actioned/vs/vf не были ограничены моментом создания
знания (эпизод действия мог быть РАНЬШЕ first_seen(K)) — исправлено
условием fs < ep; анализ перезапущен; записи не менялись.
Зафиксировано.

## 6. Ограничения

```
* 6 эпизодов × 2 — не длинная серия; длинная — отдельным словом.
* Шум — условие траектории (не robustness-эксперимент).
* Proposal change — observation; changed==true ≠ PASS.
* D-2/D-3/D-4/D-6/EF-12 не открывались; strategy.py не трогался.
```

## 7. Дальше (по слову)

```
Длинная серия (большая длина) — после вердикта по L1-A.
Открытые кандидаты для дизайна: состав/формат контекста при
росте истории (N≥10); «возврат к прежней гипотезе» (O3) как
наблюдаемый паттерн; сохранение per-knowledge counters между
сериями.
```

## 8. Артефакты

```
long1a/PROTOCOL.md (FROZEN), long1a_driver.py, long1a_analyze.py,
LONG1A_E0..E5_r1/r2.json (12), LONG1A_ANALYSIS.txt (57 checks),
LONG1A_DESIGN.md (FROZEN). Слои v0.6.x+A1 не изменялись
(audit 12/12).
```
