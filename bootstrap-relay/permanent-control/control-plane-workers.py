#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ACCOUNT = Path(os.environ.get("PPC_ACCOUNT", "/home/storage/781/4477781/user"))
WEBAPP = Path(os.environ.get("PPC_WEBAPP", str(ACCOUNT / "webapp")))
STATE = Path(os.environ.get("PPC_WORKER_STATE", str(ACCOUNT / ".powerpc-control-workers")))
LOCKFILE = STATE / "supervisor.lock"
PIDFILE = STATE / "supervisor.pid"
STATUSFILE = STATE / "status.json"
LOGFILE = STATE / "supervisor.log"
DISABLED = STATE / "disabled"
TUNNEL_DIR = STATE / "tunnel-client"
TUNNEL_PIDFILE = TUNNEL_DIR / "pid"
TUNNEL_LOG = TUNNEL_DIR / "worker.log"
BRIDGE_DIR = STATE / "continuity-bridge"
BRIDGE_PIDFILE = BRIDGE_DIR / "pid"
BRIDGE_LOG = BRIDGE_DIR / "worker.log"

EXPECTED_UID = 2257347
TUNNEL_ALIAS = "powerpc-local-mcp"
TUNNEL_PROFILE = "powerpc-local-mcp"
TUNNEL_PROFILE_DIR = WEBAPP / ".config" / "tunnel-client"
BRIDGE_ROOT = WEBAPP / "runtime-domains" / "continuity-bridge"
BRIDGE_FOREGROUND = BRIDGE_ROOT / "run-foreground.sh"
BRIDGE_HEALTH = "http://127.0.0.1:19910/healthz"

LOOP_SECONDS = 10
STATUS_SECONDS = 10
RESTART_WINDOW_SECONDS = 900
RESTART_LIMIT = 6
BACKOFF = (5, 15, 30, 60, 120, 240)
MAX_LOG_BYTES = 2 * 1024 * 1024
STOP = False


def now() -> int:
    return int(time.time())


def atomic_json(path: Path, obj: dict[str, Any], mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    data = json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def rotate(path: Path) -> None:
    try:
        if path.stat().st_size <= MAX_LOG_BYTES:
            return
    except FileNotFoundError:
        return
    old = path.with_suffix(path.suffix + ".1")
    try:
        old.unlink()
    except FileNotFoundError:
        pass
    os.replace(path, old)


def log(msg: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    rotate(LOGFILE)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(f"{stamp} {msg}\n")
    os.chmod(LOGFILE, 0o600)


def read_pid(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="ascii").strip()
        pid = int(value)
        return pid if pid > 1 else None
    except Exception:
        return None


def cmdline(pid: int) -> str:
    try:
        return (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\x00", b" ").decode("utf-8", "replace")
    except Exception:
        return ""


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def tunnel_binary() -> str | None:
    candidates = [
        shutil.which("tunnel-client"),
        str(WEBAPP / "bin" / "tunnel-client"),
        str(WEBAPP / ".local" / "bin" / "tunnel-client"),
        str(ACCOUNT / ".local" / "bin" / "tunnel-client"),
        str(WEBAPP / "miniconda" / "bin" / "tunnel-client"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def tunnel_pid_valid(pid: int | None, binary: str | None) -> bool:
    if not pid_alive(pid) or not binary:
        return False
    line = cmdline(pid or 0)
    return os.path.basename(binary) in line and " run " in (" " + line + " ") and TUNNEL_PROFILE in line


def bridge_pid_valid(pid: int | None) -> bool:
    if not pid_alive(pid):
        return False
    line = cmdline(pid or 0)
    return str(BRIDGE_ROOT) in line or "continuity-bridge" in line


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(ACCOUNT)
    env["XDG_CONFIG_HOME"] = str(WEBAPP / ".config")
    parts = [
        str(WEBAPP / ".local" / "bin"),
        str(ACCOUNT / ".local" / "bin"),
        str(WEBAPP / "miniconda" / "bin"),
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
    ]
    env["PATH"] = ":".join(parts)
    return env


def tunnel_command(binary: str) -> list[str]:
    command = [binary, "run", "--profile", TUNNEL_PROFILE]
    try:
        cp = subprocess.run(
            [binary, "run", "--help"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=child_env(),
            timeout=5,
            check=False,
        )
        help_text = cp.stdout.decode("utf-8", "replace")
        if "--profile-dir" in help_text:
            command.extend(["--profile-dir", str(TUNNEL_PROFILE_DIR)])
    except Exception:
        pass
    return command


def spawn(command: list[str], cwd: Path, log_path: Path, pidfile: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rotate(log_path)
    log_handle = open(log_path, "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=child_env(),
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_handle.close()
    pidfile.write_text(str(proc.pid) + "\n", encoding="ascii")
    os.chmod(pidfile, 0o600)
    return proc.pid


def terminate_verified(pidfile: Path, validator) -> None:
    pid = read_pid(pidfile)
    if not validator(pid):
        try:
            pidfile.unlink()
        except FileNotFoundError:
            pass
        return
    assert pid is not None
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.time() + 12
    while time.time() < deadline and pid_alive(pid):
        time.sleep(0.25)
    if pid_alive(pid) and validator(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        pidfile.unlink()
    except FileNotFoundError:
        pass


def get_json(command: list[str], timeout: int = 8) -> dict[str, Any] | None:
    try:
        cp = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=child_env(),
            cwd=str(WEBAPP),
            timeout=timeout,
            check=False,
        )
        if cp.returncode != 0:
            return None
        obj = json.loads(cp.stdout.decode("utf-8", "replace"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def http_ok(url: str, timeout: float = 3.0) -> bool | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return 200 <= int(r.status) < 300
    except urllib.error.HTTPError:
        return False
    except Exception:
        return None


class Worker:
    def __init__(self, name: str) -> None:
        self.name = name
        self.restarts: list[int] = []
        self.failures = 0
        self.next_retry_at = 0
        self.last_start = 0
        self.last_health = "unknown"
        self.last_error = ""

    def prune(self) -> None:
        cutoff = now() - RESTART_WINDOW_SECONDS
        self.restarts = [t for t in self.restarts if t >= cutoff]

    def can_restart(self) -> bool:
        self.prune()
        return len(self.restarts) < RESTART_LIMIT and now() >= self.next_retry_at

    def record_start(self) -> None:
        self.restarts.append(now())
        self.last_start = now()
        self.failures = 0
        self.next_retry_at = 0
        self.last_error = ""

    def record_failure(self, reason: str) -> None:
        self.failures += 1
        delay = BACKOFF[min(self.failures - 1, len(BACKOFF) - 1)]
        self.next_retry_at = now() + delay
        self.last_error = reason
        log(f"{self.name}_failure reason={reason} retry_in={delay}")

    def summary(self) -> dict[str, Any]:
        self.prune()
        return {
            "health": self.last_health,
            "last_error": self.last_error,
            "last_start": self.last_start,
            "next_retry_at": self.next_retry_at,
            "restarts_window": len(self.restarts),
            "restart_limit": RESTART_LIMIT,
        }


def ensure_tunnel(worker: Worker) -> dict[str, Any]:
    binary = tunnel_binary()
    configured = bool(binary and TUNNEL_PROFILE_DIR.is_dir())
    pid = read_pid(TUNNEL_PIDFILE)

    if not configured:
        worker.last_health = "not_configured"
        return {
            **worker.summary(),
            "configured": False,
            "pid": pid,
            "process_alive": False,
            "profile": TUNNEL_PROFILE,
        }

    if tunnel_pid_valid(pid, binary):
        status = get_json([binary, "runtimes", "status", TUNNEL_ALIAS, "--json"])
        explicit_ready = None
        ui_url = None
        if status:
            state = status.get("runtime_state")
            stale = status.get("stale")
            ui_url = status.get("ui_url")
            if state is not None:
                explicit_ready = state == "ready" and stale is False

        readyz = None
        if isinstance(ui_url, str) and ui_url.startswith("http://127.0.0.1:"):
            base = ui_url[:-3] if ui_url.endswith("/ui") else ui_url.rstrip("/")
            readyz = http_ok(base + "/readyz")

        if explicit_ready is True or readyz is True:
            worker.last_health = "ready"
            worker.failures = 0
            worker.last_error = ""
        elif explicit_ready is False or readyz is False:
            worker.last_health = "process_alive_degraded"
        else:
            worker.last_health = "process_alive_unverified"

        return {
            **worker.summary(),
            "configured": True,
            "pid": pid,
            "process_alive": True,
            "profile": TUNNEL_PROFILE,
            "runtime_state": status.get("runtime_state") if status else None,
            "stale": status.get("stale") if status else None,
            "readyz": readyz,
        }

    if pid:
        try:
            TUNNEL_PIDFILE.unlink()
        except FileNotFoundError:
            pass

    if not worker.can_restart():
        worker.last_health = "restart_suppressed"
        return {
            **worker.summary(),
            "configured": True,
            "pid": None,
            "process_alive": False,
            "profile": TUNNEL_PROFILE,
        }

    try:
        command = tunnel_command(binary)
        new_pid = spawn(command, WEBAPP, TUNNEL_LOG, TUNNEL_PIDFILE)
        time.sleep(1)
        if not tunnel_pid_valid(new_pid, binary):
            worker.record_failure("start_identity_check_failed")
            worker.last_health = "start_failed"
        else:
            worker.record_start()
            worker.last_health = "starting"
            log(f"tunnel_start pid={new_pid}")
        pid = new_pid
    except Exception as e:
        worker.record_failure("spawn_" + type(e).__name__)
        worker.last_health = "start_failed"
        pid = None

    return {
        **worker.summary(),
        "configured": True,
        "pid": pid,
        "process_alive": tunnel_pid_valid(pid, binary),
        "profile": TUNNEL_PROFILE,
    }


def ensure_bridge(worker: Worker) -> dict[str, Any]:
    configured = BRIDGE_FOREGROUND.is_file() and os.access(BRIDGE_FOREGROUND, os.X_OK)
    pid = read_pid(BRIDGE_PIDFILE)

    if not configured:
        worker.last_health = "not_installed"
        return {
            **worker.summary(),
            "configured": False,
            "pid": pid,
            "process_alive": False,
            "endpoint": BRIDGE_HEALTH,
        }

    if bridge_pid_valid(pid):
        health = http_ok(BRIDGE_HEALTH)
        if health is True:
            worker.last_health = "ready"
            worker.failures = 0
            worker.last_error = ""
        elif health is False:
            worker.last_health = "process_alive_degraded"
        else:
            worker.last_health = "process_alive_unverified"
        return {
            **worker.summary(),
            "configured": True,
            "pid": pid,
            "process_alive": True,
            "endpoint": BRIDGE_HEALTH,
            "readyz": health,
        }

    if pid:
        try:
            BRIDGE_PIDFILE.unlink()
        except FileNotFoundError:
            pass

    if not worker.can_restart():
        worker.last_health = "restart_suppressed"
        return {
            **worker.summary(),
            "configured": True,
            "pid": None,
            "process_alive": False,
            "endpoint": BRIDGE_HEALTH,
        }

    try:
        new_pid = spawn([str(BRIDGE_FOREGROUND)], BRIDGE_ROOT, BRIDGE_LOG, BRIDGE_PIDFILE)
        time.sleep(1)
        if not bridge_pid_valid(new_pid):
            worker.record_failure("start_identity_check_failed")
            worker.last_health = "start_failed"
        else:
            worker.record_start()
            worker.last_health = "starting"
            log(f"bridge_start pid={new_pid}")
        pid = new_pid
    except Exception as e:
        worker.record_failure("spawn_" + type(e).__name__)
        worker.last_health = "start_failed"
        pid = None

    return {
        **worker.summary(),
        "configured": True,
        "pid": pid,
        "process_alive": bridge_pid_valid(pid),
        "endpoint": BRIDGE_HEALTH,
    }


def publish_status(tunnel: dict[str, Any], bridge: dict[str, Any], started_at: int) -> None:
    overall = "healthy"
    if tunnel.get("configured") and not tunnel.get("process_alive"):
        overall = "degraded"
    if bridge.get("configured") and not bridge.get("process_alive"):
        overall = "degraded"
    status = {
        "schema": 1,
        "runtime_id": "fasthost.powerpc",
        "supervisor_pid": os.getpid(),
        "started_at": started_at,
        "heartbeat_at": now(),
        "state": overall,
        "tunnel_client": tunnel,
        "continuity_bridge": bridge,
        "local_mcp_mode": "stdio_child_only",
    }
    atomic_json(STATUSFILE, status)


def stop_signal(_signum, _frame) -> None:
    global STOP
    STOP = True


def main() -> int:
    if os.getuid() != EXPECTED_UID and os.environ.get("PPC_WORKERS_ALLOW_TEST_UID") != "1":
        print(f"REFUSED uid={os.getuid()} expected={EXPECTED_UID}", file=sys.stderr)
        return 2
    if not WEBAPP.is_dir():
        print("REFUSED canonical webapp missing", file=sys.stderr)
        return 2
    if DISABLED.exists():
        return 0

    STATE.mkdir(parents=True, exist_ok=True)
    TUNNEL_DIR.mkdir(parents=True, exist_ok=True)
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    os.chmod(TUNNEL_DIR, 0o700)
    os.chmod(BRIDGE_DIR, 0o700)

    lock_handle = open(LOCKFILE, "a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0

    PIDFILE.write_text(str(os.getpid()) + "\n", encoding="ascii")
    os.chmod(PIDFILE, 0o600)

    signal.signal(signal.SIGTERM, stop_signal)
    signal.signal(signal.SIGINT, stop_signal)

    started_at = now()
    tunnel = Worker("tunnel_client")
    bridge = Worker("continuity_bridge")
    log("supervisor_start pid=" + str(os.getpid()))

    try:
        while not STOP:
            if DISABLED.exists():
                log("supervisor_disabled")
                break
            tunnel_state = ensure_tunnel(tunnel)
            bridge_state = ensure_bridge(bridge)
            publish_status(tunnel_state, bridge_state, started_at)
            deadline = time.time() + LOOP_SECONDS
            while time.time() < deadline and not STOP:
                time.sleep(0.25)
    finally:
        try:
            PIDFILE.unlink()
        except FileNotFoundError:
            pass
        log("supervisor_stop")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        lock_handle.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
