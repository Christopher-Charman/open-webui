#!/usr/bin/env python3
import concurrent.futures
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import urllib.request
from pathlib import Path

BASE = Path("/home/storage/781/4477781/user/webapp")
PKG = BASE / "envs/openwebui/lib/python3.11/site-packages/open_webui"
FRONTEND = PKG / "frontend"
FSTATIC = FRONTEND / "static"
SSTATIC = PKG / "static"
INDEX = FRONTEND / "index.html"
PIDFILE = BASE / "openwebui-runtime.pid"

def emit(k, v):
    print(f"{k}={v}")

def section(name):
    print(f"\n=== {name} ===")

def sha(path):
    p = Path(path)
    if not p.is_file():
        return "ABSENT"
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def size(path):
    p = Path(path)
    return p.stat().st_size if p.is_file() else "ABSENT"

section("IDENTITY")
emit("probe", "OPENWEBUI_RECOVERY_READONLY_V2")
emit("mutation", "NONE")
emit("user", subprocess.getoutput("id -un"))
emit("uid", os.getuid())
emit("pwd", os.getcwd())
emit("base_exists", BASE.is_dir())
emit("pkg_exists", PKG.is_dir())

section("OPENWEBUI_PROCESS")
pid = None
try:
    pid = int(PIDFILE.read_text().strip())
except Exception:
    pass
if pid and Path(f"/proc/{pid}/cmdline").is_file():
    emit("pid", pid)
    cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
    emit("cmdline", re.sub(r"\s+", " ", cmd))
    envp = Path(f"/proc/{pid}/environ")
    if envp.is_file():
        allow = {
            "ENABLE_OLLAMA_API", "OLLAMA_API_BASE_URL", "OLLAMA_BASE_URL",
            "OLLAMA_BASE_URLS", "DATA_DIR", "WEBUI_URL", "ENV"
        }
        for item in envp.read_bytes().split(b"\0"):
            if b"=" not in item:
                continue
            k, v = item.split(b"=", 1)
            key = k.decode("utf-8", "replace")
            if key in allow:
                emit("env." + key, v.decode("utf-8", "replace"))
else:
    emit("pid", "UNRESOLVED")

section("RUNTIME_MATRIX")
ports = [18080, 18082, 18083, 11434, 19900, 9900]
urls = {
    "openwebui.health": "http://127.0.0.1:18080/health",
    "tts18082.health": "http://127.0.0.1:18082/health",
    "tts18082.models": "http://127.0.0.1:18082/v1/models",
    "pocket18083.health": "http://127.0.0.1:18083/health",
    "ollama.version": "http://127.0.0.1:11434/api/version",
    "ollama.tags": "http://127.0.0.1:11434/api/tags",
    "ollama.ps": "http://127.0.0.1:11434/api/ps",
}

def probe_port(p):
    s = socket.socket()
    s.settimeout(0.7)
    try:
        return f"port.{p}", "OPEN" if s.connect_ex(("127.0.0.1", p)) == 0 else "CLOSED"
    finally:
        s.close()

def probe_http(item):
    name, url = item
    out = []
    try:
        with urllib.request.urlopen(url, timeout=2.5) as r:
            body = r.read(2_000_000)
            out.append((name + ".http", r.status))
            if name == "ollama.version":
                try:
                    out.append(("ollama_version", json.loads(body).get("version", "UNKNOWN")))
                except Exception:
                    pass
            elif name == "ollama.tags":
                try:
                    models = json.loads(body).get("models") or []
                    out.append(("ollama_model_count", len(models)))
                    out += [("ollama_model", m.get("name") or m.get("model") or "") for m in models]
                except Exception:
                    pass
            elif name == "ollama.ps":
                try:
                    models = json.loads(body).get("models") or []
                    out.append(("ollama_loaded_count", len(models)))
                    out += [("ollama_loaded", m.get("name") or m.get("model") or "") for m in models]
                except Exception:
                    pass
    except Exception as e:
        out.append((name + ".http", "FAIL:" + type(e).__name__))
    return out

with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
    pf = [ex.submit(probe_port, p) for p in ports]
    hf = [ex.submit(probe_http, item) for item in urls.items()]
    for f in pf:
        emit(*f.result())
    for f in hf:
        for k, v in f.result():
            emit(k, v)

try:
    for line in subprocess.check_output(["pgrep", "-af", "ollama serve|/ollama"], text=True, stderr=subprocess.DEVNULL).splitlines():
        emit("ollama_process", line)
except Exception:
    pass

section("OPENWEBUI_CONFIG_AND_MODEL_BINDING")
candidates = [BASE / "openwebui-data/webui.db", BASE / "data/webui.db"]
db = next((p for p in candidates if p.is_file()), None)
if db is None:
    found = list(BASE.glob("**/webui.db"))
    db = found[0] if found else None
emit("db", str(db) if db else "UNRESOLVED")

def decode(v):
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", "replace")
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v

def safe_api_cfg(v):
    v = decode(v)
    if not isinstance(v, dict):
        return v
    out = {}
    for k, entry in v.items():
        if not isinstance(entry, dict):
            out[str(k)] = "NON_OBJECT"
            continue
        row = {x: entry.get(x) for x in ("enable", "connection_type", "prefix_id", "model_ids", "tags") if x in entry}
        row["has_key"] = bool(entry.get("key"))
        row["has_headers"] = bool(entry.get("headers"))
        out[str(k)] = row
    return out

if db:
    con = sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True)
    cur = con.cursor()
    keys = [
        "ollama.enable", "ollama.base_urls", "ollama.api_configs",
        "ui.default_models", "ui.default_pinned_models",
        "audio.tts.engine", "audio.tts.voice", "audio.tts.model",
    ]
    try:
        rows = dict(cur.execute(
            "select key,value from config where key in (%s)" % ",".join("?" * len(keys)),
            keys
        ).fetchall())
        for k in keys:
            if k not in rows:
                emit("config." + k, "ABSENT")
                continue
            v = decode(rows[k])
            if k == "ollama.api_configs":
                v = safe_api_cfg(v)
            emit("config." + k, json.dumps(v, sort_keys=True, separators=(",", ":")))
    except Exception as e:
        emit("config_query", "FAIL:" + type(e).__name__ + ":" + str(e))
    try:
        cols = [r[1] for r in cur.execute("pragma table_info(model)").fetchall()]
        emit("model_table_columns", ",".join(cols))
        if {"id", "name", "base_model_id"}.issubset(cols):
            if "is_active" in cols:
                q = "select id,name,base_model_id,is_active from model order by lower(name),id"
            else:
                q = "select id,name,base_model_id,1 from model order by lower(name),id"
            data = cur.execute(q).fetchall()
            emit("workspace_model_count", len(data))
            counts = {}
            for _, name, _, _ in data:
                norm = (name or "").strip().lower()
                if norm:
                    counts[norm] = counts.get(norm, 0) + 1
            for name, count in sorted(counts.items()):
                if count > 1:
                    emit("duplicate_model_name", f"{name}|count={count}")
            needles = ("local agent", "mini c-agent", "c-agent", "starfleet", "deepseek", "qwen")
            for mid, name, base_model_id, active in data:
                blob = " ".join(str(x or "").lower() for x in (mid, name, base_model_id))
                if any(n in blob for n in needles):
                    emit("target_model", json.dumps({
                        "id": mid, "name": name, "base_model_id": base_model_id,
                        "is_active": bool(active)
                    }, sort_keys=True, separators=(",", ":")))
    except Exception as e:
        emit("model_query", "FAIL:" + type(e).__name__ + ":" + str(e))
    con.close()

section("FRONTEND_DEPLOYMENT_IDENTITY")
emit("index_sha256", sha(INDEX))
emit("loader_bytes", size(FSTATIC / "loader.js"))
emit("loader_sha256", sha(FSTATIC / "loader.js"))
emit("custom_css_bytes", size(FSTATIC / "custom.css"))
emit("custom_css_sha256", sha(FSTATIC / "custom.css"))
if INDEX.is_file():
    txt = INDEX.read_text(errors="replace")
    markers = [
        "owui-postmount-ui-voice-v20260929.1",
        "owui-postmount-orb-beam-v20260930.1",
        "continuity-shell-semantic-binder-v20260930.2",
        "continuity-shell-landing-hero-presenter-v20260930.4",
        "continuity-neural-material.css?v=20260930.2",
    ]
    for marker in markers:
        emit("index_marker[" + marker + "]", txt.count(marker))

assets = [
    "pwa-voice-bridge.js", "pwa-client-runtime.js", "continuity-postmount-bootstrap.js",
    "owui-orb-v1.js", "owui-orb-v1.css", "continuity-orb-beam-postmount.js",
    "continuity-neural-material.js", "continuity-neural-material.css",
    "continuity-shell-semantic-binder.js", "continuity-shell-semantic-binder.css",
    "continuity-shell-hero-presenter.js", "continuity-shell-hero-presenter.css",
]
for name in assets:
    p = SSTATIC / name
    emit("asset." + name + ".bytes", size(p))
    emit("asset." + name + ".sha256", sha(p))

section("VOICE_STARTUP_STATIC_SCAN")
pat = re.compile(r"warmSelectedVoice|/api/v1/audio/local-voice/warm|speechSynthesis|new\s+Audio|\.play\(|cortana|Cortana|ready|Ready")
for name in ["pwa-voice-bridge.js", "pwa-client-runtime.js", "continuity-postmount-bootstrap.js", "continuity-controls.js"]:
    p = SSTATIC / name
    if not p.is_file():
        continue
    emit("scan_file", str(p))
    hits = 0
    for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
        if pat.search(line):
            print(f"scan_hit={n}:{line[:500]}")
            hits += 1
            if hits >= 80:
                break

section("CLASSIFICATION_HINTS")
emit("rule", "NO_REPAIR_PERFORMED")
emit("rule", "OLLAMA_LISTENER_THEN_CONFIG_THEN_INVENTORY_THEN_MODEL_BINDING")
emit("rule", "CACHE_WARMING_NE_AUDIO_PLAYBACK")
emit("rule", "ACCEPTED_STACK_RESTORE_REMAINS_STAGED_UNTIL_THIS_PROBE_IS_REVIEWED")
emit("OPENWEBUI_RECOVERY_READONLY_V2", "END")
