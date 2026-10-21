"""Validate the generated ZimaOS AppStore v2 files."""

import json
import sys
from pathlib import Path


DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
PUBLIC_BASE = "https://mattboxx.github.io/Clipboard-Bridge-AppStore/"


def load_json(relative):
    path = DIST / relative
    if not path.is_file():
        raise SystemExit(f"Missing generated file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


store = load_json("store.json")
index = load_json("index.json")

if store.get("version") != 2:
    raise SystemExit("store.json must use ZimaOS store protocol version 2")
if store.get("store_id") != "io.github.mattbox03.clipboard-bridge":
    raise SystemExit("store.json contains an unexpected store_id")

items = index.get("apps", index if isinstance(index, list) else [])
if not isinstance(items, list) or len(items) != 1:
    raise SystemExit("index.json must contain exactly one application")

item = items[0]
if item.get("id") != "io.github.mattbox03.clipboard-bridge":
    raise SystemExit("index.json does not contain Clipboard Bridge")
for field in ("compose_url", "meta_url"):
    value = item.get(field, "")
    if value.startswith(PUBLIC_BASE):
        continue
    relative = value.lstrip("/")
    if not relative.startswith("apps/") or ".." in Path(relative).parts:
        raise SystemExit(f"index.json contains an invalid {field}")
    if not (DIST / relative).is_file():
        raise SystemExit(f"index.json {field} does not point to a generated file")

print("Generated ZimaOS v2 store is valid.")
