# V-SWAP-G4: CONTROLLED MODEL SWAP (gemma3:4b → gemma4-e4b-heretic:q4km)

**Статус: пре-регистрация до прогона. Замороженные протоколы
VERTICAL-1 (v1/v2) не изменяются; их драйверы, логи и данные не
трогаются.**

## Вопрос

Что изменится в поведении контура при ЕДИНСТВЕННОМ изменении —
замене LLM-провайдера `gemma` (gemma3:4b) на `gemma4`
(gemma4-e4b-heretic:q4km)? Всё остальное фиксировано.

## Фиксировано (не меняется)

- среда: tsasvc (systemd-имитатор), состояния управляются драйвером;
- задача: тексты задач серий v1/v2 — дословно;
- адаптер: llm/adapter.py, SYSTEM-промпт, build_prompt — без правок;
- бюджет: max_tokens=300, temperature=0.0, timeout=180;
- рука/линейка: executor (ALLOWED_PREFIXES), evaluation — без правок;
- MAX_ACTIONS=5; фильтр предложений — как в сериях v1/v2.

## Единственный фактор

```text
provider: gemma (gemma3:4b)  →  gemma4 (gemma4-e4b-heretic:q4km)
           reasoning_effort=none — уже в adapter.PROVIDERS (diag_gemma4)
```

## Серии (bare-режим, без контура памяти)

- **S2 = v2-сценарий** (невыводимый tsafix, флаг /run/tsasvc.lock),
  bare ×3. Baseline gemma3: `[false, false, false]`.
- **S1 = v1-сценарий** (inactive, лечится systemctl start),
  bare ×3. Baseline gemma3: `[true, true, true]`.

Запуск по секциям: сначала S2 (v2); при чистоте — S1 (v1).

## Запись

- лог: `experiments/vertical1/SWAP_G4_run.log` (append по секциям);
- stores: `data_swap_g4_v2_bare/`, `data_swap_g4_v1_bare/` (свежие);
- в эпизод-лог: success / executed / proposed / outcomes, llm_ok,
  llm_candidates (команды модели), llm_meta (usage).

## Инварианты (проверяются после серий)

- knowledge_bare == 0 (bare не создаёт знание);
- среда оставлена в active; результат определяется evaluation по
  фактам (goal), не по словам модели.

## Границы

- интерпретация — после серии; отчёт отдельно (SWAP_G4_REPORT.md);
- удаление gemma3 — только после фиксации результата и
  подтверждения воспроизводимости сценариев (задача 12.09);
- Strategy / Knowledge / Executor / экспериментальные протоколы —
  не меняются; R2 — отдельным словом.
