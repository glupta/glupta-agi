#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
import tomllib
from pathlib import Path

MODEL_HOST = "chatgpt.com"
AUTH_HOST = "auth.openai.com"
CODEX_VERSION = "0.147.0"
SUBNET, APP_IP, POSTGRES_IP = "172.30.47.0/29", "172.30.47.2", "172.30.47.3"
BEGIN, END = "# GLUPTA_EGRESS_BEGIN", "# GLUPTA_EGRESS_END"
PROVISIONED = re.compile(
    rf"(?ms)^provision:\n  {re.escape(BEGIN)} .*?\n  {re.escape(END)}\n"
)


class RenderError(RuntimeError):
    pass


def _validate_contract(repo: Path) -> None:
    compose = (repo / "compose.yaml").read_text(encoding="utf-8")
    required = (
        f"ipv4_address: {APP_IP}",
        f"ipv4_address: {POSTGRES_IP}",
        f"subnet: {SUBNET}",
        "enable_ipv6: false",
    )
    if any(compose.count(item) != 1 for item in required):
        raise RenderError("Compose egress identity does not match the reviewed contract")
    match = re.search(r"(?ms)^services:\n(?P<body>.*?)(?=^[a-z][a-z0-9_-]*:\s*$)", compose)
    services = [] if match is None else re.findall(
        r"^  ([a-z][a-z0-9_-]*):\s*$", match.group("body"), re.MULTILINE
    )
    if services != ["app", "postgres"]:
        raise RenderError("Compose steady-state service identity changed")

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
    if any(item in adapter for item in forbidden):
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
