#!/bin/bash
# tsasvc_daemon.sh v3 — полигон LONGITUDINAL-1.
# Демон падает при старте, пока существует ЛЮБОЙ флаг болезни
# /run/tsasvc.lock.* (a, b, c, extra). Лечения: fix-a/b/c/ab/a2.
if ls /run/tsasvc.lock.* >/dev/null 2>&1; then
    exit 1
fi
exec /usr/bin/sleep infinity
