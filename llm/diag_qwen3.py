# -*- coding: utf-8 -*-
"""qwen3:4b через /v1: контроль пути."""
import json
import urllib.request


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read().decode()


for label, mt in (("hi, 4000", 4000), ("hi, 200", 200)):
    print("== /v1 max_tokens=%s (%s) ==" % (mt, label))
    try:
        out = call("http://localhost:11434/v1/chat/completions",
                   {"model": "qwen3:4b",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": mt})
        d = json.loads(out)
        ch = d["choices"][0]
        print("content:", repr(ch["message"]["content"])[:150])
        print("finish:", ch.get("finish_reason"), "| usage:",
              d.get("usage"))
    except Exception as e:
        print("ERR:", str(e)[:200])
