#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

MODEL_HOST = "chatgpt.com"
AUTH_HOST = "auth.openai.com"
CODEX_VERSION = "0.147.0"
SUBNET, APP_IP, POSTGRES_IP = "172.30.47.0/29", "172.30.47.2", "172.30.47.3"
PROJECT_NAME, NETWORK_NAME = "glupta-crawl", "glupta-crawl_private"
COMPOSE_SEARCH_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
COMPOSE_TIMEOUT_SECONDS = 10
BEGIN, END = "# GLUPTA_EGRESS_BEGIN", "# GLUPTA_EGRESS_END"
PROVISIONED = re.compile(rf"(?ms)^provision:\n  {re.escape(BEGIN)} .*?\n  {re.escape(END)}\n")


class RenderError(RuntimeError):
    pass


def _compose_model(repo: Path) -> dict[str, object]:
    executable = shutil.which("docker-compose", path=COMPOSE_SEARCH_PATH)
    if executable is None:
        raise RenderError("Docker Compose semantic validator is unavailable")
    argv = (
        str(Path(executable).resolve()),
        "--ansi",
        "never",
        "--env-file",
        "/dev/null",
        "--project-directory",
        str(repo),
        "-f",
        str(repo / "compose.yaml"),
        "config",
        "--format",
        "json",
        "--no-interpolate",
        "--no-env-resolution",
        "--no-path-resolution",
    )
    completed: subprocess.CompletedProcess[str] | None = None
    failure: str | None = None
    try:
        completed = subprocess.run(  # noqa: S603
            argv,
            check=False,
            cwd=repo,
            env={
                "COMPOSE_DISABLE_ENV_FILE": "1",
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=COMPOSE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        failure = "Docker Compose semantic validation timed out"
    except OSError:
        failure = "Docker Compose semantic validator is unavailable"
    except UnicodeError:
        failure = "Docker Compose semantic validation failed"
    if failure is not None:
        raise RenderError(failure)
    if completed is None:
        raise RenderError("Docker Compose semantic validation failed")
    if completed.returncode != 0:
        del completed
        raise RenderError("Docker Compose semantic validation failed")
    model: object = None
    invalid_json = False
    try:
        model = json.loads(completed.stdout)
    except json.JSONDecodeError:
        invalid_json = True
    del completed
    if invalid_json:
        raise RenderError("Docker Compose semantic validation failed")
    if not isinstance(model, dict):
        del model
        raise RenderError("Docker Compose semantic validation failed")
    return model


def _validate_contract(repo: Path) -> None:
    compose = _compose_model(repo)
    services = compose.get("services")
    if not isinstance(services, dict) or set(services) != {"app", "postgres"}:
        raise RenderError("Compose steady-state service identity changed")
    expected_network = {
        "name": NETWORK_NAME,
        "ipam": {"config": [{"subnet": SUBNET}]},
        "enable_ipv6": False,
    }
    expected_service_networks = {
        "app": {"private": {"ipv4_address": APP_IP}},
        "postgres": {"private": {"ipv4_address": POSTGRES_IP}},
    }
    networks = compose.get("networks")
    if (
        compose.get("name") != PROJECT_NAME
        or not isinstance(networks, dict)
        or set(networks) != {"private"}
        or networks.get("private") != expected_network
        or any(
            not isinstance(services[service], dict)
            or services[service].get("networks") != expected_networks
            for service, expected_networks in expected_service_networks.items()
        )
    ):
        raise RenderError("Compose egress identity does not match the reviewed contract")

    project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project.get("project", {}).get("dependencies", [])
    if dependencies.count(f"openai-codex=={CODEX_VERSION}") != 1:
        raise RenderError("pinned Codex runtime identity changed")
    adapter = (repo / "src" / "glupta_agi" / "codex_adapter.py").read_text(encoding="utf-8")
    invariants = (
        'env_binary, "-i"',
        '"apps", "plugins", "remote_plugin"',
        '"web_search": WebSearchMode.disabled.value',
        '"requires_openai_auth": True',
    )
    if any(adapter.count(item) != 1 for item in invariants):
        raise RenderError("Codex subscription route controls changed")
    forbidden = ("chatgpt_base_url", "OPENAI_BASE_URL", "CODEX_BASE_URL")
    if re.search(r"\bbase_url\b", adapter) or any(item in adapter for item in forbidden):
        raise RenderError("Codex subscription route contains an endpoint override")


def _script(template: Path) -> str:
    source = template.read_text(encoding="utf-8")
    markers = (
        "__GLUPTA_MODEL_HOST__",
        "__GLUPTA_AUTH_HOST__",
        "__GLUPTA_HOST_PAIR__",
    )
    if any(source.count(marker) != 1 for marker in markers):
        raise RenderError("egress template markers are invalid")
    rendered = (
        source.replace("__GLUPTA_MODEL_HOST__", MODEL_HOST)
        .replace("__GLUPTA_AUTH_HOST__", AUTH_HOST)
        .replace("__GLUPTA_HOST_PAIR__", f"{MODEL_HOST}:{AUTH_HOST}")
    )
    if "__GLUPTA_" in rendered:
        raise RenderError("unresolved egress template marker")
    return rendered


def _block(template: Path) -> str:
    script = _script(template)
    digest = hashlib.sha256(script.encode()).hexdigest()
    body = "".join(f"      {line}\n" if line else "\n" for line in script.splitlines())
    return (
        "provision:\n"
        f"  {BEGIN} route=codex-subscription-v1 script_sha256={digest}\n"
        "  - mode: after-boot\n"
        "    script: |\n"
        f"{body}"
        f"  {END}\n"
    )


def verify_text(candidate: str, repo: Path, template: Path) -> None:
    _validate_contract(repo)
    expected = _block(template)
    if PROVISIONED.findall(candidate) != [expected]:
        raise RenderError("rendered Colima egress block is not exact")
    if candidate.count(BEGIN) != 1 or candidate.count(END) != 1:
        raise RenderError("rendered Colima egress markers are ambiguous")
    if "provision: null" in candidate or "__GLUPTA_" in candidate:
        raise RenderError("rendered Colima config retains an unresolved provision value")


def render(config: Path, output: Path, repo: Path, template: Path) -> None:
    _validate_contract(repo)
    current = config.read_text(encoding="utf-8")
    replacement = _block(template)
    if current.count("provision: null") == 1 and BEGIN not in current and END not in current:
        candidate = current.replace("provision: null", replacement.rstrip("\n"), 1)
    elif len(PROVISIONED.findall(current)) == 1 and current.count(BEGIN) == current.count(END) == 1:
        candidate = PROVISIONED.sub(lambda _: replacement, current, count=1)
    else:
        raise RenderError("refusing to replace an unowned or ambiguous provision block")
    verify_text(candidate, repo, template)
    output.write_text(candidate, encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render or verify the held Glupta Codex egress gate"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("render", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--config", required=True, type=Path)
        subparser.add_argument("--repo", required=True, type=Path)
        if command == "render":
            subparser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    template = Path(__file__).with_name("colima-after-boot.sh")
    if args.command == "render":
        render(args.config, args.output, args.repo, template)
    else:
        verify_text(args.config.read_text(encoding="utf-8"), args.repo, template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
