"""Keep the beginner installation examples aligned with the shipped Compose file."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUIDES = ("DOCKER.md", "DOCKER.it.md")


def dotenv_example(filename):
    text = (ROOT / filename).read_text(encoding="utf-8")
    return re.findall(r"```dotenv\n(.*?)\n```", text, re.S)[0]


@pytest.mark.parametrize("filename", GUIDES)
def test_complete_example_documents_every_template_setting(filename):
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    keys = set(re.findall(r"^(\w+)=", template, re.M))
    example = dotenv_example(filename)
    assert set(re.findall(r"^(\w+)=", example, re.M)) == keys
    server = re.search(r'SERVER_VERSION = "([^"]+)"',
                       (ROOT / "clipboard_bridge-Server.py").read_text(encoding="utf-8"))
    assert server is not None
    assert f"APP_IMAGE=ghcr.io/mattboxx/clipboard-bridge-server:{server[1]}" in example
    text = (ROOT / filename).read_text(encoding="utf-8")
    assert text.index("```dotenv") < text.index("docker compose config --quiet")
    assert "GUIDE.md#5-set-up-iphone-shortcuts" in text
    assert "docker compose restart` does not apply" in text or "non applica" in text
    assert "docker compose logs --tail=100 clipboard-bridge" in text
    assert "--volumes" in text and "localhost" in text


def test_readmes_keep_basic_commands_and_link_to_the_full_guide():
    for filename in ("README.md", "README.it.md"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        assert "](DOCKER.md)" in text
        assert "curl -fL https://raw.githubusercontent.com/Mattboxx/Clipboard-Bridge/main/compose.yaml -o compose.yaml" in text
        assert "nano .env\ndocker compose pull\ndocker compose up -d" in text
        assert "```dotenv" not in text


@pytest.mark.parametrize("filename", GUIDES)
def test_documented_configuration_resolves_with_real_compose(filename, tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI not installed")
    available = subprocess.run(["docker", "compose", "version"], capture_output=True,
                               text=True, timeout=30)
    if available.returncode:
        pytest.skip("Compose plugin not installed")
    shutil.copyfile(ROOT / "compose.yaml", tmp_path / "compose.yaml")
    example = dotenv_example(filename)
    (tmp_path / ".env").write_text(example + "\n", encoding="utf-8")
    env = os.environ.copy()
    for key in re.findall(r"^(\w+)=", example, re.M):
        env.pop(key, None)
    result = subprocess.run(
        ["docker", "compose", "--project-directory", str(tmp_path),
         "--env-file", str(tmp_path / ".env"), "-f", str(tmp_path / "compose.yaml"),
         "config", "--format", "json"],
        env=env, capture_output=True, text=True, timeout=30, check=True)
    config = json.loads(result.stdout)
    service = config["services"]["clipboard-bridge"]
    assert service["environment"]["CLIPBOARD_PORT"] == "5088"
    assert service["environment"]["CLIPBOARD_DATA_DIR"] == "/data"
    assert service["environment"]["CLIPBOARD_TOKEN"] == ""
    assert service["environment"]["CLIPBOARD_PASSWORD"] == ""
    assert service["environment"]["CLIPBOARD_ACCOUNTS"] == ""
    assert service["ports"][0]["published"] == "5088"
    assert service["volumes"][0]["target"] == "/data"
    assert Path(service["volumes"][0]["source"]) == tmp_path / "data"
