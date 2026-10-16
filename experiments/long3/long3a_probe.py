# -*- coding: utf-8 -*-
"""LONG-3A: provider-scale probe (observation-only; ничего не меняет).

Цель: зафиксировать фактическое поведение ollama при росте промпта
(наблюдение масштаба относительно num_ctx). Отправляет промпты
растущей длины с max_tokens=1 и печатает provider-метаданные
(prompt_tokens). Не пишет в store; серии LONG-3 не трогаются.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, BASE)

from llm import adapter  # noqa: E402

url = adapter.PROVIDERS["gemma"]["url"]
for name, n in (("A", 500), ("B", 2000), ("C", 8000)):
    p = "test " * n
    try:
        c, m = adapter.chat(url, "gemma3:4b", p, max_tokens=1,
                            timeout=180, with_meta=True)
        print("%s chars=%d prompt_tokens=%s ok"
              % (name, len(p), m.get("prompt_tokens")), flush=True)
    except Exception as exc:
        print("%s chars=%d ERROR: %s"
              % (name, len(p), str(exc)[:160]), flush=True)
