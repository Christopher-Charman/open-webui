#!/usr/bin/env python3
"""Read-only OpenWebUI Local Agent binding collector."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BASE = Path("/home/storage/781/4477781/user/webapp")


def find_db() -> Path | None:
    for p in (BASE / "openwebui-data/webui.db", BASE / "data/webui.db"):
        if p.is_file():
            return p
    for p in BASE.glob("**/webui.db"):
        if p.is_file():
            return p
    return None


def collect_local_agent_binding() -> dict:
    """Collect Local Agent workspace binding evidence without mutating the DB."""
    db = find_db()
    if db is None:
        return {"state": "DB_NOT_FOUND", "rows": [], "row_count": 0}

    con = sqlite3.connect("file:" + str(db) + "?mode=ro", uri=True)
    cur = con.cursor()
    cols = [r[1] for r in cur.execute("pragma table_info(model)").fetchall()]
    required = {"id", "name", "base_model_id"}
    if not required.issubset(cols):
        return {
            "state": "SCHEMA_MISMATCH",
            "db": str(db),
            "columns": cols,
            "rows": [],
            "row_count": 0,
        }

    ollama_base_urls = None
    try:
        row = cur.execute("select value from config where key=?", ("ollama.base_urls",)).fetchone()
        if row:
            raw = row[0]
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8", "replace")
            try:
                ollama_base_urls = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                ollama_base_urls = raw
    except Exception:
        ollama_base_urls = None

    active_expr = "is_active" if "is_active" in cols else "1"
    q = f"select id,name,base_model_id,{active_expr} from model order by lower(name),id"
    rows = []
    for mid, name, base, active in cur.execute(q).fetchall():
        blob = " ".join(str(x or "").lower() for x in (mid, name, base))
        if any(tok in blob for tok in ("local agent", "mini c-agent", "c-agent")):
            rows.append({
                "id": mid,
                "name": name,
                "base_model_id": base,
                "is_active": bool(active),
            })

    con.close()
    return {
        "state": "OK",
        "db": str(db),
        "rows": rows,
        "row_count": len(rows),
        "ollama_base_urls": ollama_base_urls,
    }


def main() -> int:
    result = collect_local_agent_binding()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result.get("state") == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
