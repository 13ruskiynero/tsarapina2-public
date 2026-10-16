#!/bin/bash
# tsasvc_daemon.sh v2 — демон-имитатор полигона VERTICAL-1.
# Если существует флаг-блокировка /run/tsasvc.lock — демон
# НЕМЕДЛЕННО завершается (exit 1): «сервис не запускается».
# Лечение (невыводимое из задачи): tsafix — снять флаг и start.
LOCK=/run/tsasvc.lock
if [ -e "$LOCK" ]; then
    exit 1
fi
exec /usr/bin/sleep infinity
