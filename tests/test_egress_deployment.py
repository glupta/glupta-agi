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
    tmp_path: Path,
    text: str = "arch: aarch64\nprovision: null\nruntime: docker\n",
) -> Path:
    path = tmp_path / "colima.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _repo_copy(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "glupta_agi").mkdir(parents=True)
    shutil.copy(ROOT / "compose.yaml", repo / "compose.yaml")
    shutil.copy(ROOT / "pyproject.toml", repo / "pyproject.toml")
    shutil.copy(
        ROOT / "src" / "glupta_agi" / "codex_adapter.py",
        repo / "src" / "glupta_agi" / "codex_adapter.py",
    )
    return repo


def test_render_is_deterministic_exact_and_verifiable(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first, second = tmp_path / "first.yaml", tmp_path / "second.yaml"
    for output in (first, second):
        render_colima.render(config, output, ROOT, TEMPLATE)
    assert first.read_bytes() == second.read_bytes()
    candidate = first.read_text(encoding="utf-8")
    assert candidate.count("chatgpt.com") == 2
    assert candidate.count("auth.openai.com") == 2
    assert "api.openai.com" not in candidate.replace("auth.openai.com", "")
    assert candidate.count("GLUPTA_EGRESS_BEGIN") == 1
    assert "mode: after-boot" in candidate
    assert "__GLUPTA_" not in candidate
    assert "proxy" not in candidate.lower()
    render_colima.verify_text(candidate, ROOT, TEMPLATE)


def test_render_replaces_only_its_exact_prior_block(tmp_path: Path) -> None:
    first, updated = tmp_path / "first.yaml", tmp_path / "updated.yaml"
    render_colima.render(_config(tmp_path), first, ROOT, TEMPLATE)
    render_colima.render(first, updated, ROOT, TEMPLATE)
    assert first.read_bytes() == updated.read_bytes()


@pytest.mark.parametrize("content", (
    "provision:\n  - mode: system\n    script: echo existing\n",
    "provision: null\n# GLUPTA_EGRESS_BEGIN stale\n",
    "provision: null\nprovision: null\n",
))
def test_render_refuses_unowned_or_ambiguous_provision(tmp_path: Path, content: str) -> None:
    with pytest.raises(render_colima.RenderError, match="unowned or ambiguous"):
        render_colima.render(
            _config(tmp_path, content), tmp_path / "candidate.yaml", ROOT, TEMPLATE
        )


@pytest.mark.parametrize(("old", "new"), (
    ("172.30.47.2", "172.30.47.4"),
    ("172.30.47.3", "172.30.47.5"),
    ("172.30.47.0/29", "172.30.48.0/29"),
    ("enable_ipv6: false", "enable_ipv6: true"),
))
def test_render_refuses_compose_identity_drift(tmp_path: Path, old: str, new: str) -> None:
    repo = _repo_copy(tmp_path)
    path = repo / "compose.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    with pytest.raises(render_colima.RenderError, match="Compose egress identity"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_render_refuses_swapped_compose_service_addresses(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    path = repo / "compose.yaml"
    compose = path.read_text(encoding="utf-8")
    path.write_text(
        compose.replace("172.30.47.2", "172.30.47.swap", 1)
        .replace("172.30.47.3", "172.30.47.2", 1)
        .replace("172.30.47.swap", "172.30.47.3", 1),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="Compose egress identity"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_render_refuses_a_third_steady_state_service(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    path = repo / "compose.yaml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "\nvolumes:\n", "\n  proxy:\n    image: proxy\n\nvolumes:\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="steady-state service"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_render_refuses_runtime_or_route_control_drift(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    project = repo / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace(
            "openai-codex==0.147.0", "openai-codex==0.148.0"
        ),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="runtime identity"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)

    repo = _repo_copy(tmp_path / "second")
    adapter = repo / "src" / "glupta_agi" / "codex_adapter.py"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            '"web_search": WebSearchMode.disabled.value', '"web_search": "live"'
        ),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="route controls"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_render_refuses_endpoint_override(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    adapter = repo / "src" / "glupta_agi" / "codex_adapter.py"
    adapter.write_text(
        adapter.read_text(encoding="utf-8")
        + '\nchatgpt_base_url = "https://elsewhere.invalid"\n',
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="endpoint override"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_render_refuses_model_provider_base_url_override(tmp_path: Path) -> None:
    repo = _repo_copy(tmp_path)
    adapter = repo / "src" / "glupta_agi" / "codex_adapter.py"
    adapter.write_text(
        adapter.read_text(encoding="utf-8").replace(
            '"crawl_openai": {"name": "OpenAI",',
            '"crawl_openai": {"base_url": "https://elsewhere.invalid", "name": "OpenAI",',
        ),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="endpoint override"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_shell_template_is_syntax_checked_and_fail_closed() -> None:
    subprocess.run(["/bin/sh", "-n", str(TEMPLATE)], check=True)  # noqa: S603
    script = TEMPLATE.read_text(encoding="utf-8")
    assert "priority filter - 10" in script
    assert "ip saddr 172.30.47.2" in script
    assert "ip daddr 172.30.47.3 tcp dport 5432 accept" in script
    assert "ip daddr @codex4 tcp dport 443 accept" in script
    assert "counter name glupta_denied reject" in script
    assert "systemctl stop docker.service docker.socket containerd.service" in script
    assert all(term not in script.lower() for term in ("curl ", "wget ", "proxy", "sidecar"))
