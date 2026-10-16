# OUTPUT-BUDGET MAP-1 (11.09.2026): КАРТА

**Статус: PASS → CLOSED (вердикт профессора, 11.09).**

Read-only / isolated provider probe. Production adapter НЕ менялся
(использованы его публичные chat/parse_json/validate как есть);
store/executor/слои не трогались; эпизодов нет. Переменная —
max_tokens; prompt фиксирован (реальные контексты starvation-
траекторий). temperature=0.

## 1. Runs

```
#   контекст  prompt  max_tokens  →  результат        compl  raw_len
1   E507      3907    60          →  invalid (лимит)   60     176
2   E507      3907    80          →  invalid (лимит)   80     242
3   E507      3907    100         →  invalid (лимит)   100    350
4   E507      3907    120         →  invalid (лимит)   120    440
5   E507      3907    140         →  VALID              136    513
6   E507      3907    160         →  VALID              136    513
7   E513      3983    113         →  invalid (потолок)  113    435
8   E513      3983    200         →  invalid (потолок)  113    401
run8: 200 запрошено, но доступно 4096−3983=113 → упёрся в ОКНО,
       не в max_tokens.
```

## 2. Выводы

```
1. Минимальный completion-бюджет текущего proposal-контракта
   (при почти полном промпте): фактическое потребление полного
   валидного ответа = 136 токенов (дважды повторено, t=0);
   контракт не закрывается при ≤120. Граница в интервале
   (120, 140).
2. На starvation-контексте (доступно 113): контракт НЕ закрывается
   ни при 113, ни при «щедрых» 200 — потолок окна 113 < требуемых
   ~136. B5-математика замыкается: starvation не стохастика
   модели, а следствие дефицита: нужно ≥~136, доступно 113.
3. Совместно с r1/r2 (потребления полных ответов: 119, 125, 136,
   141 в разных точках) требуемый бюджет ≈ 125–141; контракт
   требует ~1/30 всего окна (4096) сверх промпта.
4. Осторожно (не закон, не фундаментальная константа): на
   исследованной конфигурации и текущем proposal contract
   starvation наблюдается при prompt ≈3960+; минимальный
   наблюдаемый required completion лежит в интервале (120, 140);
   конкретное потребление варьируется ≈125–141. Точную границу
   120–140 не сужали (лимит 6–8 runs); completion demand не
   абсолютно постоянен.
```

**Строгая формулировка B5 (вердикт 11.09):**

```
B5: output-budget starvation возникает, когда доступный
completion budget меньше минимального бюджета, необходимого для
завершения валидного proposal contract:

    P + B_required > N_ctx

Замкнутый цикл:
  Knowledge growth → prompt growth → B_available ↓
  → B_available < B_required → INVALID proposal
  → NO ACTION → no new verified consequence
  → no new Knowledge → same context (↺).
```

**RESOURCE STATE R0 (baseline для RESOURCE-RESPONSE-1):**

```
prompt ≈ 3983; available completion = 113;
required completion ≈ 136; proposal = structurally invalid;
action = none; Knowledge growth = 0; context growth = 0.
```

## 3. Ограничения

```
одна модель (gemma3:4b), один формат контракта; стохастика в
точке отказа наблюдалась и ранее (r1 E489 fail vs E490 pass при
том же prompt); точная граница между 120 и 140 не сужалась
(лимит 6–8 runs соблюдён).
```

## 4. Следствие (не действие)

```
Появляется предмет RESOURCE-RESPONSE-1 (ответ контура при
дефиците output-бюджета), но он не начинается без отдельного
слова. Базовая линия фактов: минимальный бюджет контракта ~136;
доступный при starvation 113; состояние самоподдерживающееся.
```

## 5. Артефакты

```
recon1/obm1_probe.py, recon1/OBM1_run1..8.json, этот файл.
RECON1_ANALYSIS.txt (§14 r2), RECON1_REPORT.md (§9), RESEARCH_DEBT
(D-context-2).
```
