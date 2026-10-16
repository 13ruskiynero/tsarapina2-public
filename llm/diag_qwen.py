# -*- coding: utf-8 -*-
"""Диагностика qwen3:4b через ollama: пустой ответ в /v1."""
import json
import urllib.request


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read().decode()


print("== /v1 chat/completions: простой запрос ==")
try:
    out = call("http://localhost:11434/v1/chat/completions",
               {"model": "qwen3:4b",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 100})
    d = json.loads(out)
    print("content:", repr(d["choices"][0]["message"]["content"])[:200])
    print("finish:", d["choices"][0].get("finish_reason"))
    print("usage:", d.get("usage"))
except Exception as e:
    print("ERR:", str(e)[:300])

print()
print("== /api/chat: с options ==")
try:
    out = call("http://localhost:11434/api/chat",
               {"model": "qwen3:4b",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False,
                "options": {"num_predict": 100, "temperature": 0.0}})
    d = json.loads(out)
    print("message:", repr(d.get("message", {}).get("content"))[:200])
    print("done_reason:", d.get("done_reason"))
    print("eval_count:", d.get("eval_count"))
except Exception as e:
    print("ERR:", str(e)[:300])
