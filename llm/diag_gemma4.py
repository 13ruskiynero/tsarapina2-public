# -*- coding: utf-8 -*-
"""gemma4-e4b-heretic:q4km: reasoning-диагностика + адаптерный smoke.

Часть 1 (низкоуровнево): один и тот же запрос через
/v1/chat/completions с reasoning_effort=none и без него —
сравнить usage и наличие reasoning-хвоста.
Часть 2 (контракт Царапины): adapter.propose("gemma4", ...) —
проверить, что модель отдаёт валидный JSON через существующий
код адаптера (провайдер зарегистрирован в adapter.PROVIDERS).
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import adapter  # noqa: E402

URL = "http://localhost:11434/v1/chat/completions"
MODEL = "gemma4-e4b-heretic:q4km"

PROMPT = adapter.build_prompt(
    "ssh.service недоступен: connection refused на порту 22. "
    "Предложи диагностические команды.",
    context="факты: service:ssh state=inactive; порт 22 не слушается")

print("== ЧАСТЬ 1: прямой вызов /v1 (reasoning_effort none vs default) ==",
      flush=True)
for label, extra in (("none", {"reasoning_effort": "none"}),
                     ("default", {})):
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": adapter.SYSTEM},
                     {"role": "user", "content": PROMPT}],
        "temperature": 0.0,
        "max_tokens": 300,
        "stream": False,
    }
    body.update(extra)
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            d = json.loads(resp.read().decode())
        ch = d["choices"][0]
        msg = ch["message"]
        reasoning = msg.get("reasoning") or msg.get("thinking") or ""
        print("[%s] finish=%s usage=%s"
              % (label, ch.get("finish_reason"), d.get("usage")), flush=True)
        print("[%s] reasoning_len=%d" % (label, len(reasoning)), flush=True)
        print("[%s] content=%r"
              % (label, (msg.get("content") or "")[:300]), flush=True)
    except Exception as exc:
        print("[%s] ERR %s: %s"
              % (label, type(exc).__name__, str(exc)[:200]), flush=True)
    print()

print("== ЧАСТЬ 2: adapter.propose('gemma4', ...) ==", flush=True)
r = adapter.propose("gemma4", PROMPT)
print("ok:", r["ok"], flush=True)
if r["ok"]:
    for a in r["candidate_actions"]:
        print("action:", a["type"], "|", a["command"], flush=True)
    print("rationale:", r["rationale"][:200], flush=True)
else:
    print("error:", r["error"][:300], flush=True)
    print("raw:", r["raw"][:300], flush=True)
print("provider_meta:", r["provider_meta"], flush=True)
