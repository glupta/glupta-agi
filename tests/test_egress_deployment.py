# ruff: noqa: S101
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
RENDERER = ROOT / "deploy" / "egress" / "render_colima.py"
TEMPLATE = ROOT / "deploy" / "egress" / "colima-after-boot.sh"
SPEC = importlib.util.spec_from_file_location("render_colima", RENDERER)
assert SPEC and SPEC.loader
render_colima = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(render_colima)


def _config(
    tmp_path: Path, text: str = "arch: aarch64\nprovision: null\nruntime: docker\n"
) -> Path:
    path = tmp_path / "colima.yaml"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("region", "host"), (("us", "us.api.openai.com"), ("europe", "eu.api.openai.com"))
)
def test_render_is_deterministic_exact_and_verifiable(
    tmp_path: Path, region: str, host: str
) -> None:
    config = _config(tmp_path)
    first, second = tmp_path / "first.yaml", tmp_path / "second.yaml"
    for output in (first, second):
        render_colima.render(config, output, ROOT / "compose.yaml", TEMPLATE, region)

    assert first.read_bytes() == second.read_bytes()
    candidate = first.read_text(encoding="utf-8")
    assert candidate.count(host) == 2
    assert candidate.count("GLUPTA_EGRESS_BEGIN") == 1
    assert "mode: after-boot" in candidate
    assert "__GLUPTA_" not in candidate
    assert "proxy" not in candidate.lower()
    render_colima.verify_text(candidate, ROOT / "compose.yaml", TEMPLATE, region)


def test_render_replaces_only_its_exact_prior_block(tmp_path: Path) -> None:
    original = _config(tmp_path)
    first = tmp_path / "first.yaml"
    render_colima.render(original, first, ROOT / "compose.yaml", TEMPLATE, "us")
    updated = tmp_path / "updated.yaml"
    render_colima.render(first, updated, ROOT / "compose.yaml", TEMPLATE, "europe")

    candidate = updated.read_text(encoding="utf-8")
    assert "eu.api.openai.com" in candidate
    assert "us.api.openai.com" not in candidate
    render_colima.verify_text(candidate, ROOT / "compose.yaml", TEMPLATE, "europe")


@pytest.mark.parametrize(
    "content",
    (
        "provision:\n  - mode: system\n    script: echo existing\n",
        "provision: null\n# GLUPTA_EGRESS_BEGIN stale\n",
        "provision: null\nprovision: null\n",
    ),
)
def test_render_refuses_unowned_or_ambiguous_provision(tmp_path: Path, content: str) -> None:
    with pytest.raises(render_colima.RenderError, match="unowned or ambiguous"):
        render_colima.render(
            _config(tmp_path, content),
            tmp_path / "candidate.yaml",
            ROOT / "compose.yaml",
            TEMPLATE,
            "us",
        )


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("172.30.47.2", "172.30.47.4"),
        ("172.30.47.3", "172.30.47.5"),
        ("172.30.47.0/29", "172.30.48.0/29"),
        ("enable_ipv6: false", "enable_ipv6: true"),
    ),
)
def test_render_refuses_compose_identity_drift(tmp_path: Path, old: str, new: str) -> None:
    compose = tmp_path / "compose.yaml"
    compose.write_text((ROOT / "compose.yaml").read_text(encoding="utf-8").replace(old, new),
                       encoding="utf-8")
    inference = tmp_path / "src" / "glupta_agi" / "inference.py"
    inference.parent.mkdir(parents=True)
    shutil.copy(ROOT / "src" / "glupta_agi" / "inference.py", inference)
    with pytest.raises(render_colima.RenderError, match="Compose egress identity"):
        render_colima.render(
            _config(tmp_path), tmp_path / "candidate.yaml", compose, TEMPLATE, "us"
        )


def test_render_refuses_inference_endpoint_drift(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    shutil.copy(ROOT / "compose.yaml", compose)
    inference = tmp_path / "src" / "glupta_agi" / "inference.py"
    inference.parent.mkdir(parents=True)
    inference.write_text(
        (ROOT / "src" / "glupta_agi" / "inference.py")
        .read_text(encoding="utf-8")
        .replace("https://us.api.openai.com/v1", "https://api.openai.com/v1"),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="inference region"):
        render_colima.render(
            _config(tmp_path), tmp_path / "candidate.yaml", compose, TEMPLATE, "us"
        )


def test_render_refuses_a_third_steady_state_service(tmp_path: Path) -> None:
    compose = tmp_path / "compose.yaml"
    source = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    compose.write_text(source.replace("\nvolumes:\n", "\n  proxy:\n    image: proxy\n\nvolumes:\n"),
                       encoding="utf-8")
    inference = tmp_path / "src" / "glupta_agi" / "inference.py"
    inference.parent.mkdir(parents=True)
    shutil.copy(ROOT / "src" / "glupta_agi" / "inference.py", inference)
    with pytest.raises(render_colima.RenderError, match="steady-state service"):
        render_colima.render(
            _config(tmp_path), tmp_path / "candidate.yaml", compose, TEMPLATE, "us"
        )


def test_shell_template_is_syntax_checked_and_fail_closed() -> None:
    subprocess.run(["/bin/sh", "-n", str(TEMPLATE)], check=True)  # noqa: S603
    script = TEMPLATE.read_text(encoding="utf-8")
    assert "priority filter - 10" in script
    assert "ip saddr 172.30.47.2" in script
    assert "ip daddr 172.30.47.3 tcp dport 5432 accept" in script
    assert "ip daddr @openai4 tcp dport 443 accept" in script
    assert "counter name glupta_denied reject" in script
    assert "systemctl stop docker.service docker.socket containerd.service" in script
    assert all(term not in script.lower() for term in ("curl ", "wget ", "proxy", "sidecar"))
