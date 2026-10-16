# -*- coding: utf-8 -*-
"""qwen3:4b: полный запрос адаптера с usage-диагностикой."""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm import adapter  # noqa: E402

PROMPT = adapter.build_prompt(
    "ssh.service недоступен: connection refused на порту 22. "
    "Предложи диагностические команды.",
    context="факты: service:ssh state=inactive; порт 22 не слушается")

body = {
    "model": "qwen3:4b",
    "messages": [{"role": "system", "content": adapter.SYSTEM},
                 {"role": "user", "content": PROMPT}],
    "temperature": 0.0,
    "max_tokens": 4000,
    "stream": False,
}
req = urllib.request.Request(
    "http://localhost:11434/v1/chat/completions",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=600) as resp:
    d = json.loads(resp.read().decode())
ch = d["choices"][0]
print("content:", repr(ch["message"]["content"])[:300])
print("finish:", ch.get("finish_reason"))
print("usage:", d.get("usage"))
