# V-SWAP-G4: REPORT (controlled model swap)

**Дата: 12.09.2026. Дизайн: SWAP_G4_DESIGN.md (пре-регистрация).
Режим: bare, единственный фактор — provider (gemma3:4b →
gemma4-e4b-heretic:q4km). Замороженные протоколы VERTICAL-1 (v1/v2)
и их данные не изменялись.**

## 1. Среда до прогона (находка)

Полигон tsasvc на момент старта: юнит настроен на демон
experiments/longitudinal1 (v3-механика: lock-* файлы) и в состоянии
failed (остаточный /run/tsasvc.lock.a от 11.09). Сценарий v2 требует
демон experiments/vertical1 (падает от /run/tsasvc.lock).

Действие (обратимое, провенанс сохранён):
юнит временно переключён на vertical1-демон —
бэкап исходного: `tsasvc.service.bak_20260912`;
после серий юнит возвращён в исходную конфигурацию (failed, как до).
Локи `/run/tsasvc.lock.*` не трогались.

## 2. Результаты (RAW: SWAP_G4_run.log)

S2 — v2 (невыводимый tsafix), bare x3, provider=gemma4:
```text
успех:     [false, false, false]   | baseline gemma3: [false, false, false]
траектории: gemma4: start → status; gemma3: start → restart
llm:       ok=3/3, completion 141/152/152 (бюджет 300)
```

S1 — v1 (inactive → start), bare x3, provider=gemma4:
```text
успех:     [true, true, true]      | baseline gemma3: [true, true, true]
траектории: start (1 действие до успеха; предложено 2)
llm:       ok=3/3, completion 161 x3
```

Инварианты: knowledge_bare=0 (обе серии); среда после серий active;
вердикт — по evaluation (факты), не по словам модели.

## 3. Чтение результата

- Исходы совпадают с gemma3 на обоих сценариях — своп НЕ изменил
  решающую способность контура в этих задачах (ожидаемо: задачи
  построены так, что LLM не является решателем).
- Единственное наблюдённое отличие — уровень траектории (второе
  действие на неуспешном сценарии: status vs restart). Материал для
  будущего сравнения поведения G3/G4, не вывод.
- Контракт адаптера выдержан: JSON валиден, бюджет не превышен.

## 4. Контроль (smoke/invariants)

- diag_gemma4.py: reasoning_effort=none → чистый JSON (212 токенов
  на диагностической задаче); default → content пуст
  (finish=length, 1230 символов reasoning) — воспроизведено.
- tests/test_llm_adapter.py: PASS (12/12).
- Полный прогон tests/: 7/10 PASS. Три FAIL вне LLM-контура:
  test_strategy t1 (EF-11, known expected mismatch — решение 11.09,
  D-6); test_knowledge K1a/K1c и test_update U3 (schema_version
  mismatch 0.2/0.3 в тестовом слое; тесты не импортируют llm).
  Регрессий LLM/перехода нет.

## 5. Переход на Gemma 4 (выполнено по задаче 12.09)

- adapter.PROVIDERS: gemma4 — основной провайдер (пометка 12.09);
  gemma — legacy (конфиг сохранён для истории/тестов).
- `ollama rm gemma3:4b`: удалено; свободное место 6.5G → 9.7G
  (+3.2G). Остались: gemma4 (5.3G), qwen2.5 (1.9G), qwen3 (2.5G).
- Baseline gemma3 сохранён полностью: RAW-логи серий, отчёты,
  конфиги; удалены только веса модели.

## 6. Артефакты

- swap_g4_driver.py, SWAP_G4_run.log, SWAP_G4_DESIGN.md,
  tsasvc.service.bak_20260912, SWAP_G4_REPORT.md (этот файл);
- stores: data_swap_g4_v1_bare/, data_swap_g4_v2_bare/;
- базы сравнения не изменялись: VERTICAL1_run.log (bare_d0),
  VERTICAL1_v2_run.log (bare_test).

## 7. Границы / не сделано

- R2 не открывался (отдельным словом).
- long3 и прочие серии не перезапускались; RESEARCH_DEBT.md не
  изменялся (запись о S-G4 — по слову).
- Повтор V-SWAP-G4 после удаления gemma3 возможен: сценарии зависят
  только от gemma4; перед серией может потребоваться переключение
  юнита на vertical1-демон (см. §1).
