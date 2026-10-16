# -*- coding: utf-8 -*-
"""qwen3:4b: изоляция причины пустого ответа (system? stream? длина?)."""
import json
import urllib.request


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read().decode()


SYS = ("Ты — процессор предложения действий диагностической системы. "
       "Верни ТОЛЬКО JSON в формате: "
       '{"candidate_actions": [{"type": "command", "command": '
       '"<команда>"}], "rationale": "<почему>"}.')
CASES = [
    ("без system, без stream", {"messages": [{"role": "user",
                                               "content": "Reply hi"}]}),
    ("с system, без stream", {"messages": [{"role": "system",
                                             "content": SYS},
                                            {"role": "user",
                                             "content": "Reply hi"}]}),
    ("без system, stream:false", {"messages": [{"role": "user",
                                                 "content": "Reply hi"}],
                                   "stream": False}),
    ("с system, stream:false", {"messages": [{"role": "system",
                                               "content": SYS},
                                              {"role": "user",
                                               "content": "Reply hi"}],
                                 "stream": False}),
]
for label, extra in CASES:
    body = {"model": "qwen3:4b", "max_tokens": 4000}
    body.update(extra)
    try:
        out = call("http://localhost:11434/v1/chat/completions", body)
        d = json.loads(out)
        ch = d["choices"][0]
        print("[%s] content=%r finish=%s" %
              (label, ch["message"]["content"][:80],
               ch.get("finish_reason")))
    except Exception as e:
        print("[%s] ERR: %s" % (label, str(e)[:150]))
