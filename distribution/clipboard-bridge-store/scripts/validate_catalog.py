import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "compose.yaml",
    "config.json",
    "Apps/clipboard-bridge/docker-compose.yml",
    "portainer/templates.json",
    "adapters/umbrel/umbrel-app-store.yml",
    "adapters/umbrel/clipboard-bridge/umbrel-app.yml",
    "adapters/runtipi/apps/clipboard-bridge/config.json",
    "store-config.json",
]

for relative in REQUIRED:
    if not (ROOT / relative).is_file():
        raise SystemExit(f"Missing required file: {relative}")
for path in ROOT.rglob("*.json"):
    json.loads(path.read_text(encoding="utf-8"))
for pattern in ("*.yml", "*.yaml"):
    for path in ROOT.rglob(pattern):
        yaml.safe_load(path.read_text(encoding="utf-8"))
for path in ROOT.rglob("docker-compose.yml"):
    if "ghcr.io/mattbox03/clipboard-bridge-server:1.0.0" not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"Unexpected image in {path.relative_to(ROOT)}")

versions = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
if versions.get("clipboard-bridge") != "1.0.0":
    raise SystemExit("config.json does not expose clipboard-bridge version 1.0.0")

store = json.loads((ROOT / "store-config.json").read_text(encoding="utf-8"))
for field in ("name", "description"):
    if "en_US" not in store.get(field, {}):
        raise SystemExit(f"store-config.json {field} is missing en_US")

app = yaml.safe_load(
    (ROOT / "Apps/clipboard-bridge/docker-compose.yml").read_text(encoding="utf-8")
)
metadata = app.get("x-casaos", {})
if metadata.get("id") != "io.github.mattbox03.clipboard-bridge":
    raise SystemExit("ZimaOS app is missing its stable x-casaos.id")
for field in ("title", "tagline", "description"):
    languages = metadata.get(field, {})
    if "en_US" not in languages:
        raise SystemExit(f"ZimaOS app {field} is missing en_US")
print("Catalog files are valid.")
