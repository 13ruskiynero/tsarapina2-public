# -*- coding: utf-8 -*-
"""Обязательный тест LLM Adapter (Tsarapina, этап 4).

Главный вопрос (профессор):
> Можно ли заменить Gemma другой моделью, не меняя Knowledge,
> Strategy, Executor и протоколы системы?

(Юнит-часть — детерминированная, на эмуляции ответов моделей:
заменяемость по конфигу (url, model) при одном и том же коде и
протоколе. Живой своп gemma↔qwen — отдельным прогоном swap_check.py,
не в тесте.)

Дополнительно:
- модель НЕ имеет доступа к хранилищу (нет store в API, нет
  импортов knowledge/experience/storage/executor);
- ответ парсится устойчиво (текст вокруг JSON);
- не-JSON / пусто → структурная ошибка, не исключение.

A1. propose возвращает структуру {ok, candidate_actions, rationale}.
A2. «грязный» ответ (текст вокруг JSON) парсится.
A3. не-JSON → ok=False + error (без исключения).
A4. пустой candidate_actions → ok=False.
A5. llm не импортирует knowledge/experience/storage/executor;
    propose не принимает store (нет параметра).
A6. заменяемость: тот же код propose + конфиг gemma/qwen → обе
    конфигурации принимают идентичную структуру ответа.
A7. неизвестный провайдер → структурная ошибка, не исключение.
"""
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import adapter  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print("%s %s %s" % ("PASS" if cond else "FAIL", name, detail),
          flush=True)


def _fake_chat(raw):
    """Подмена adapter.chat: вернуть сырой ответ «модели»."""
    return raw


def _run_propose(raw_answer, provider="gemma"):
    adapter.chat = lambda url, model, prompt, **kw: raw_answer
    return adapter.propose(provider, "диагностируй ssh")


GOOD = ('Сначала подумал, потом: '
        '{"candidate_actions": [{"type": "command", '
        '"command": "ss -ltnp | grep :22"}], '
        '"rationale": "проверить, кто слушает порт 22"} '
        'конец.')


def a1_structure():
    r = _run_propose(GOOD)
    check("A1a: ok=True", r["ok"])
    check("A1b: candidate_actions распознаны (1)",
          len(r["candidate_actions"]) == 1
          and r["candidate_actions"][0]["command"]
          == "ss -ltnp | grep :22")
    check("A1c: rationale извлечён", "порт 22" in r["rationale"])


def a2_dirty():
    r = _run_propose("Вот мой ответ:\n" + GOOD + "\nНадеюсь, поможет.")
    check("A2: грязный ответ парсится", r["ok"] and len(r["candidate_actions"]) == 1)


def a3_nonjson():
    r = _run_propose("Извините, я не могу ответить в формате JSON.")
    check("A3: не-JSON → ok=False, error непуст, исключения нет",
          not r["ok"] and bool(r["error"]) and r["raw"])


def a4_empty():
    r = _run_propose('{"candidate_actions": [], "rationale": "ничего"}')
    check("A4: пустой список действий → ok=False", not r["ok"])


def a5_no_storage():
    src = open(os.path.join(BASE, "llm", "adapter.py"),
               encoding="utf-8").read()
    bad = [w for w in ("knowledge", "experience", "storage", "executor")
           if re_import(w, src)]
    check("A5a: llm не импортирует слои хранилища", not bad)
    import inspect
    sig = inspect.signature(adapter.propose)
    check("A5b: propose не принимает store",
          "store" not in sig.parameters)


def re_import(name, src):
    import re
    return bool(re.search(r"(import|from)\s+%s" % name, src))


def a6_swap_config():
    """Один код, два провайдера: структура ответа принимается
    одинаково (замена модели = смена конфига)."""
    import importlib
    for provider in ("gemma", "qwen"):
        adapter.chat = lambda url, model, prompt, **kw: GOOD
        r = adapter.propose(provider, "x")
        check("A6[%s]: конфиг принимает ту же структуру ответа"
              % provider, r["ok"] and len(r["candidate_actions"]) == 1)
    # конфиги различны (разные модели), код общий
    check("A6b: конфиги gemma/qwen различаются моделью",
          adapter.PROVIDERS["gemma"]["model"] !=
          adapter.PROVIDERS["qwen"]["model"])


def a7_unknown_provider():
    r = adapter.propose("nonexistent", "x")
    check("A7: неизвестный провайдер → ok=False (без исключения)",
          not r["ok"] and "unknown provider" in r["error"])


def main():
    a1_structure()
    a2_dirty()
    a3_nonjson()
    a4_empty()
    a5_no_storage()
    a6_swap_config()
    a7_unknown_provider()
    failed = [r for r in RESULTS if not r[1]]
    print()
    print("=== ОБЯЗАТЕЛЬНЫЙ ТЕСТ LLM ADAPTER: %s ==="
          % ("ПРОЙДЕН" if not failed else "НЕ ПРОЙДЕН (%d)" % len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
