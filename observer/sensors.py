# -*- coding: utf-8 -*-
"""Детерминированные сенсоры Observer.

«Тупые, честные, измеримые»: никакой LLM, никаких интерпретаций.
Каждый сенсор возвращает (source, raw_text, subject, property, value),
где value — строка ровно в том виде, как её отдал источник
(без нормализации и «осмысления»). Сырой вывод команды сохраняется
отдельно (raw), факт ссылается на него через provenance.raw_ref.
"""
import subprocess

from observer import polygon_sensor  # noqa: E402  (полигон LONGITUDINAL-1)

TIMEOUT = 10


def _run(cmd):
    """Выполнить команду, вернуть (rc, stdout, stderr). Никакой
    обработки смысла: stdout сохраняется как есть."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=TIMEOUT)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return -1, "", "not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return -2, "", "timeout: %s" % " ".join(cmd)


def sensor_disk():
    """df -Pk: свободное место корня в KB (property free_kb)."""
    rc, out, err = _run(["df", "-Pk", "/"])
    line = ""
    for ln in out.splitlines():
        if ln.startswith("/dev/") or ln.split() and ln.split()[0] != "Filesystem":
            line = ln
            break
    avail = line.split()[3] if line else ""
    return "df", out, "disk", "free_kb", avail


def sensor_mem():
    """/proc/meminfo: MemAvailable в KB (property mem_available_kb)."""
    try:
        text = open("/proc/meminfo", encoding="utf-8").read()
    except OSError:
        return "meminfo", "", "memory", "mem_available_kb", ""
    val = ""
    for ln in text.splitlines():
        if ln.startswith("MemAvailable:"):
            val = ln.split()[1]
            break
    return "meminfo", text, "memory", "mem_available_kb", val


def sensor_load():
    """/proc/loadavg: load1."""
    try:
        text = open("/proc/loadavg", encoding="utf-8").read()
    except OSError:
        return "loadavg", "", "cpu", "load1", ""
    return "loadavg", text, "cpu", "load1", text.split()[0] if text else ""


def sensor_service(name="ssh"):
    """systemctl is-active <name> (property state)."""
    rc, out, err = _run(["systemctl", "is-active", name])
    return "systemctl", out or err or "", "service:%s" % name, "state", out


def sensor_ports():
    """ss -ltn: слушающие TCP-порты (property listening_ports)."""
    rc, out, err = _run(["ss", "-ltn"])
    ports = []
    for ln in out.splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 4:
            addr = parts[3]
            port = addr.rsplit(":", 1)[-1]
            if port.isdigit() and port not in ports:
                ports.append(port)
    return "ss", out, "network", "listening_ports", ",".join(ports)


def sensor_process(name):
    """ps -C <name>: число процессов (property count)."""
    rc, out, err = _run(["ps", "-C", name, "--no-headers"])
    n = len([l for l in out.splitlines() if l.strip()])
    return "ps", out, "process:%s" % name, "count", str(n)


def sensor_log(name="ssh"):
    """journalctl -n 10 -u <name>: последние строки (property tail_count).
    raw — сами строки; факт несёт только их число (не смысл)."""
    rc, out, err = _run(["journalctl", "-n", "10", "-u", name,
                         "--no-pager", "-o", "cat"])
    return "journalctl:%s" % name, out, "log:%s" % name, "tail_count", str(
        len([l for l in out.splitlines() if l.strip()]))


SENSORS = [
    ("disk", sensor_disk),
    ("memory", sensor_mem),
    ("load", sensor_load),
    ("service:ssh", lambda: sensor_service("ssh")),
    # полигон VERTICAL-1: имитатор-сервис tsasvc (реальный ssh не
    # трогается; см. experiments/VERTICAL1_PROTOCOL.md)
    ("service:tsasvc", lambda: sensor_service("tsasvc")),
    # полигон LONGITUDINAL-1: симптом (флаги болезней a/b/c/extra)
    ("symptom:tsasvc", polygon_sensor.sensor_symptom),
    ("ports", sensor_ports),
    ("process:sshd", lambda: sensor_process("sshd")),
    ("log:ssh", lambda: sensor_log("ssh")),
]
