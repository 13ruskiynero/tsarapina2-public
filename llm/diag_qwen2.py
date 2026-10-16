# -*- coding: utf-8 -*-
"""qwen3:4b: проверка, что с достаточным num_predict появляется ответ."""
import json
import urllib.request


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read().decode()


for n in (500, 1500):
    print("== num_predict = %d ==" % n)
    try:
        out = call("http://localhost:11434/api/chat",
                   {"model": "qwen3:4b",
                    "messages": [{"role": "user", "content": "Reply hi"}],
                    "stream": False,
                    "options": {"num_predict": n, "temperature": 0.0}})
        d = json.loads(out)
        msg = d.get("message", {})
        print("content:", repr(msg.get("content"))[:150])
        print("done_reason:", d.get("done_reason"),
              "| eval_count:", d.get("eval_count"))
    except Exception as e:
        print("ERR:", str(e)[:200])
