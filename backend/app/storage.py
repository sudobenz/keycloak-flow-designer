import json, uuid
from pathlib import Path
from typing import Any
from .config import DATA_DIR

for folder in ("projects", "instances", "users", "backups", "audit", "history"):
    (DATA_DIR / folder).mkdir(parents=True, exist_ok=True)

def read_json(path: Path, default: Any):
    if not path.exists(): return default
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

def collection(name: str): return DATA_DIR / name

def new_id(): return str(uuid.uuid4())

def audit(action: str, actor: str, detail: dict | None = None):
    from datetime import datetime, timezone
    path = collection("audit") / "events.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "actor": actor, "action": action, "detail": detail or {}}, ensure_ascii=False) + "\n")
