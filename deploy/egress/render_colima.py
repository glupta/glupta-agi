#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import re
from pathlib import Path

REGIONAL_HOSTS = {"us": "us.api.openai.com", "europe": "eu.api.openai.com"}
SUBNET, APP_IP, POSTGRES_IP = "172.30.47.0/29", "172.30.47.2", "172.30.47.3"
BEGIN, END = "# GLUPTA_EGRESS_BEGIN", "# GLUPTA_EGRESS_END"
PROVISIONED = re.compile(
    rf"(?ms)^provision:\n  {re.escape(BEGIN)} .*?\n  {re.escape(END)}\n"
)


class RenderError(RuntimeError):
    pass


def _regional_endpoints(inference_path: Path) -> dict[str, str]:
    tree = ast.parse(inference_path.read_text(encoding="utf-8"), filename=str(inference_path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "REGIONAL_ENDPOINTS"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if isinstance(value, dict) and all(
                isinstance(key, str) and isinstance(endpoint, str)
                for key, endpoint in value.items()
            ):
                return value
    raise RenderError("REGIONAL_ENDPOINTS is missing or dynamic")


def _validate_contract(compose_path: Path, inference_path: Path) -> None:
    compose = compose_path.read_text(encoding="utf-8")
    required = (
        f"ipv4_address: {APP_IP}",
        f"ipv4_address: {POSTGRES_IP}",
        f"subnet: {SUBNET}",
        "enable_ipv6: false",
    )
    if any(compose.count(item) != 1 for item in required):
        raise RenderError("Compose egress identity does not match the reviewed contract")
    services_match = re.search(
        r"(?ms)^services:\n(?P<body>.*?)(?=^[a-z][a-z0-9_-]*:\s*$)", compose
    )
    services = [] if services_match is None else re.findall(
        r"^  ([a-z][a-z0-9_-]*):\s*$", services_match.group("body"), re.MULTILINE
    )
    if services != ["app", "postgres"]:
        raise RenderError("Compose steady-state service identity changed")
    endpoints = _regional_endpoints(inference_path)
    expected = {region: f"https://{host}/v1" for region, host in REGIONAL_HOSTS.items()}
    if endpoints != expected:
        raise RenderError("inference region and endpoint identity changed")


def _script(template_path: Path, region: str) -> str:
    if region not in REGIONAL_HOSTS:
        raise RenderError("region must be exactly us or europe")
    template = template_path.read_text(encoding="utf-8")
    markers = ("__GLUPTA_REGION__", "__GLUPTA_HOST__", "__GLUPTA_PAIR__")
    if any(template.count(marker) != 1 for marker in markers):
        raise RenderError("egress template markers are invalid")
    host = REGIONAL_HOSTS[region]
    rendered = (
        template.replace("__GLUPTA_REGION__", region)
        .replace("__GLUPTA_HOST__", host)
        .replace("__GLUPTA_PAIR__", f"{region}:{host}")
    )
    if "__GLUPTA_" in rendered:
        raise RenderError("unresolved egress template marker")
    return rendered


def _block(template_path: Path, region: str) -> str:
    script = _script(template_path, region)
    digest = hashlib.sha256(script.encode()).hexdigest()
    body = "".join(f"      {line}\n" if line else "\n" for line in script.splitlines())
    return (
        "provision:\n"
        f"  {BEGIN} region={region} script_sha256={digest}\n"
        "  - mode: after-boot\n"
        "    script: |\n"
        f"{body}"
        f"  {END}\n"
    )


def render(config: Path, output: Path, compose: Path, template: Path, region: str) -> None:
    inference = compose.parent / "src" / "glupta_agi" / "inference.py"
    _validate_contract(compose, inference)
    current = config.read_text(encoding="utf-8")
    replacement = _block(template, region)
    if current.count("provision: null") == 1 and BEGIN not in current and END not in current:
        candidate = current.replace("provision: null", replacement.rstrip("\n"), 1)
    elif len(PROVISIONED.findall(current)) == 1 and current.count(BEGIN) == current.count(END) == 1:
        candidate = PROVISIONED.sub(lambda _: replacement, current, count=1)
    else:
        raise RenderError("refusing to replace an unowned or ambiguous provision block")
    verify_text(candidate, compose, template, region)
    output.write_text(candidate, encoding="utf-8")


def verify_text(candidate: str, compose: Path, template: Path, region: str) -> None:
    inference = compose.parent / "src" / "glupta_agi" / "inference.py"
    _validate_contract(compose, inference)
    expected = _block(template, region)
    matches = PROVISIONED.findall(candidate)
    if matches != [expected] or candidate.count(BEGIN) != 1 or candidate.count(END) != 1:
        raise RenderError("rendered Colima egress block is not exact")
    if "provision: null" in candidate or "__GLUPTA_" in candidate:
        raise RenderError("rendered Colima config retains an unresolved provision value")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render or verify the held Glupta Colima gate")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("render", "verify"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--region", required=True, choices=tuple(REGIONAL_HOSTS))
        subparser.add_argument("--config", required=True, type=Path)
        subparser.add_argument("--compose", required=True, type=Path)
        if command == "render":
            subparser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    template = Path(__file__).with_name("colima-after-boot.sh")
    if args.command == "render":
        render(args.config, args.output, args.compose, template, args.region)
    else:
        verify_text(args.config.read_text(encoding="utf-8"), args.compose, template, args.region)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
