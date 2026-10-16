# -*- coding: utf-8 -*-
"""qwen3:4b: попытка отключить думание (think=false) в /api/chat."""
import json
import urllib.request


def call(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read().decode()


CASES = [
    ("think:false в теле", {"think": False, "options": {"num_predict": 300}}),
    ("think:false в options", {"options": {"think": False,
                                           "num_predict": 300}}),
]
for label, extra in CASES:
    body = {"model": "qwen3:4b",
            "messages": [{"role": "user", "content": "Reply hi"}],
            "stream": False}
    body.update(extra)
    try:
        out = call("http://localhost:11434/api/chat", body)
        d = json.loads(out)
        msg = d.get("message", {})
        print("[%s]" % label)
        print("  content:", repr(msg.get("content"))[:120])
        print("  thinking:", repr(msg.get("thinking"))[:80])
        print("  done_reason:", d.get("done_reason"),
              "| eval_count:", d.get("eval_count"))
    except Exception as e:
        print("[%s] ERR: %s" % (label, str(e)[:150]))
