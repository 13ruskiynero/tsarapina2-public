# -*- coding: utf-8 -*-
"""Живой своп-прогон LLM Adapter (Tsarapina, этап 4).

Один и тот же код adapter.propose; провайдеры gemma и qwen
(ollama, локально). Проверка: заменяемость модели БЕЗ изменения
Knowledge/Strategy/Executor/протоколов — структура ответа
принимается одинаково.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import adapter  # noqa: E402

PROMPT = adapter.build_prompt(
    "ssh.service недоступен: connection refused на порту 22. "
    "Предложи диагностические команды.",
    context="факты: service:ssh state=inactive; порт 22 не слушается")

print("== SWAP CHECK: gemma3:4b vs qwen2.5:3b ==", flush=True)
results = {}
for provider in ("gemma", "qwen25"):
    r = adapter.propose(provider, PROMPT, max_tokens=300, timeout=180)
    results[provider] = r
    print("[%s] ok=%s" % (provider, r["ok"]), flush=True)
    if r["ok"]:
        for a in r["candidate_actions"]:
            print("    action:", a["type"], "|", a["command"], flush=True)
        print("    rationale:", r["rationale"][:200], flush=True)
    else:
        print("    error:", r["error"][:200], flush=True)
        print("    raw:", r["raw"][:300], flush=True)

ok_gemma = results["gemma"]["ok"] and results["gemma"]["candidate_actions"]
ok_qwen = results["qwen25"]["ok"] and results["qwen25"]["candidate_actions"]
print()
print("== ВЕРДИКТ: замена модели без изменения кода/протоколов ==")
print("gemma3:4b:", "OK" if ok_gemma else "FAIL",
      "| qwen2.5:3b:", "OK" if ok_qwen else "FAIL")
if ok_gemma and ok_qwen:
    print("ЗАМЕНА ВОЗМОЖНА: две РАЗНЫЕ модели (Google, Alibaba) вернули "
          "структурный ответ через один adapter.propose")
else:
    print("ЗАМЕНА НЕ ПОДТВЕРЖДЕНА (см. ошибки выше)")
