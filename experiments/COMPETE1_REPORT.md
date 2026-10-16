# COMPETE-1: ОТЧЁТ (11.09.2026)

**Статус: PROTOCOL PASS / STRUCTURAL RESULT → CLOSED (вердикт
профессора, 11.09).** 20 runs; M1–M6 без нарушений; narrative-leak
чисто; L-chain чисто; r1 ≡ r2 полностью.

**Каноническая формулировка вклада (профессор):**

> **COMPETE-1 показал, что при наличии двух ранее verified
> Knowledge lines retrieval, mechanical candidate selection и LLM
> proposal являются эмпирически различимыми стадиями. В текущем
> прототипе обе Knowledge lines стабильно retrieved и transported;
> механический exact-pool демонстрирует acquisition-order/
> recency-like выбор; LLM proposal стабильно не следует этому
> выбору и не совпадает ни с одной из двух линий.**

Разложение (стрелки — НЕ одна причинная операция):

```
K_F ─────┐
         ├──→ RETRIEVAL ──→ обе линии
K_G ─────┘           ↓
              STRATEGY POOL
                     ↓
              recency-like choice (K_G в C1 / K_F в C2)
                     ↓
                   LLM
                     ↓
              restart (C1) / start (C2) — вне обеих линий
                     ↓
                 PERMISSION → ACTION
```

## 1. Уровни E4 (все серии)

```
C1_r1: retr F/G=True/True | lines F/G=True/True |
       strategy_ref F/G=False/True | proposal=restart | cons=partial
C2_r1: retr F/G=True/True | lines F/G=True/True |
       strategy_ref F/G=True/False | proposal=start   | cons=partial
C1_r2: как C1_r1; C2_r2: как C2_r1 (полное совпадение реплик).
```

## 2. Особенно ценное (сохранено для истории ветки)

```
C1:  E2 → Gemma сама выбрала fix-a → SUCCESS
     E4 → при наличии K_F + K_G:
          Strategy pool → K_G;  Gemma → restart
     т.е. наличие успешной предыдущей команды само по себе
     не заставило LLM её повторить:
             verified Knowledge ≠ LLM obedience

C2:  (зеркально) обе retrieved; Strategy → K_F; LLM → start
     т.е. даже механический выбор кандидата не является
     командой модели:
             mechanical selection ≠ model command
```

## 3. M-проверки

```
M1  записи 20/20 полны; audit 20/20;
M2  K_F/K_G — distinct kids; оба acquisition = success;
M3  first_seen(K_F/K_G) = 0/3 (или 3/0); traceable;
M4  E4: обе retrieved; строки обеих в prompt; уровни записаны;
M5  append-only; L-chain чист; removed=0;
M6  r1/r2: полное совпадение.
narrative-leak: чисто.
```

## 4. Наблюдения (не критерии)

```
* C1-E2: fix-a → success (линия F «сработала» в середине серии);
  к E4 линия F расширена вторым success-знанием — и всё равно
  E4-proposal вне линий.
* C2-E1/E2: restart → partial дважды; на E4 — start (не K_F).
  Среда C-конструкций дала другой режим, чем RETURN-1.
* Обе предложенные команды в w1 дают partial — consequence
  свободен от «правильного ответа» (E4 = w1), как задумано.
```

## 5. Что дальше (вердикт 11.09)

```
COMPETE-1 больше не трогаем (PROTOCOL PASS, 20/20, r1≡r2,
narrative чист, слои наблюдаемы — сделал, что должен).
COMPETE-2 — в долге (не открывать до понимания разрыва).
Следующий шаг: targeted boundary reconnaissance — поведение
слоёв Retrieval → Strategy → Proposal при приближении к silent
truncation (НЕ полный N≈404; он — только если разведка найдёт
интересную деградацию).
Новый долг: D-selection-1 (см. RESEARCH_DEBT.md); запрет:
Do not modify Strategy→LLM semantics to force proposal
adherence (OBSERVE → EXPLAIN → MODIFY).
```

## 6. Артефакты

```
compete1/PROTOCOL.md (FROZEN), compete1_driver.py,
compete1_analyze.py, COMPETE1_E*_*.json (20),
COMPETE1_ANALYSIS.txt, этот отчёт.
Слои v0.6.x+A1 не изменялись (audit 20/20).
```
