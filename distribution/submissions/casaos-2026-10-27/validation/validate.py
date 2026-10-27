"""Validate the submission files without starting containers or changing data."""

import argparse
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]
IMAGE = "ghcr.io/mattboxx/clipboard-bridge-server:1.0.11"
COMPOSES = (
    "big-bear/universal/apps/clipboard-bridge/docker-compose.yml",
    "big-bear/casaos-reference/Apps/clipboard-bridge/docker-compose.yml",
    "homeautomation/Apps/ClipboardBridge/docker-compose.yml",
    "linuxserver/custom-import/docker-compose.yml",
)
DEFAULTS = {
    "CLIPBOARD_PORT": "5088", "CLIPBOARD_DATA_DIR": "/data",
    "CLIPBOARD_MAX_HISTORY": "200", "CLIPBOARD_MAX_UPLOAD_MB": "64",
    "CLIPBOARD_TOKEN": "", "CLIPBOARD_PASSWORD": "", "CLIPBOARD_ACCOUNTS": "",
    "CLIPBOARD_ACCOUNTS_FILE": "", "CLIPBOARD_SESSION_DAYS": "3650",
}


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def validate_compose(relative):
    path = ROOT / relative
    source = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
    env = os.environ.copy()
    for name in ("AppID", "PUID", "PGID", "TZ", "APP_PORT", "DATA_ROOT"):
        env.pop(name, None)
    result = subprocess.run(
        ["docker", "compose", "--env-file", str(ROOT / "validation/.env.compose-check"),
         "-f", str(path), "config", "--format", "json"],
        env=env, capture_output=True, text=True, check=True, timeout=60,
    )
    model = json.loads(result.stdout)
    assert len(model["services"]) == 1, relative
    name, service = next(iter(model["services"].items()))
    assert service["image"] == IMAGE, relative
    assert service["restart"] == "unless-stopped", relative
    assert {key: service["environment"].get(key) for key in DEFAULTS} == DEFAULTS, relative
    assert not {"PUID", "PGID"} & service["environment"].keys(), relative
    assert len(service["ports"]) == 1 and service["ports"][0]["target"] == 5088, relative
    assert service["ports"][0]["published"] == "5088", relative
    assert service["ports"][0]["protocol"] == "tcp", relative
    assert len(service["volumes"]) == 1 and service["volumes"][0]["target"] == "/data", relative
    assert not service.get("privileged") and service.get("network_mode") != "host", relative
    assert not service.get("devices") and not service.get("cap_add"), relative
    assert service["healthcheck"]["test"][:3] == ["CMD", "python", "-c"], relative
    assert "http://127.0.0.1:5088/health" in service["healthcheck"]["test"][3], relative
    if "universal" in relative:
        assert "x-casaos" not in source and "x-casaos" not in source["services"][name], relative
        assert service["volumes"][0]["type"] == "volume", relative
    else:
        metadata = source["x-casaos"]
        assert metadata["main"] == name and str(metadata["port_map"]) == "5088", relative
        assert set(metadata["architectures"]) == {"amd64", "arm64"}, relative
    if relative.startswith("linuxserver/"):
        assert service["user"] == "1000:1000" and service["environment"]["TZ"] == "Etc/UTC", relative
    print(f"PASS Compose and runtime contract: {relative}")
    return source


def public_urls(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from public_urls(child)
    elif isinstance(value, list):
        for child in value:
            yield from public_urls(child)
    elif isinstance(value, str) and value.startswith("https://") and " " not in value:
        yield value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-links", action="store_true")
    args = parser.parse_args()
    app = json.loads((ROOT / "big-bear/universal/apps/clipboard-bridge/app.json").read_text())
    schema = json.loads((ROOT / "validation/big-bear-app-schema-v1.json").read_text())
    jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker()).validate(app)
    assert app["metadata"]["version"] == IMAGE.rsplit(":", 1)[1]
    print("PASS actual Big Bear universal JSON Schema")
    models = [validate_compose(relative) for relative in COMPOSES]
    for name in ("icon.png", "screenshot-1.png", "screenshot-2.png"):
        assert (ROOT / "homeautomation/Apps/ClipboardBridge" / name).stat().st_size > 0, name
    if args.check_links:
        for url in sorted(set(public_urls([app, *models]))):
            parts = urlsplit(url)
            assert parts.scheme == "https" and not parts.username and not parts.query, url
            with urlopen(Request(url, headers={"User-Agent": "ClipboardBridge-submission-validation"}), timeout=30) as response:
                assert response.status == 200, url
                assert response.read(1), url
            print(f"PASS public URL: {url}")
    print("Package checks passed. Physical CasaOS/ARM64 installs and store acceptance are not implied.")


if __name__ == "__main__":
    main()
