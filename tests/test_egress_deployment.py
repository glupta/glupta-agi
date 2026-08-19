# ruff: noqa: S101
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import traceback
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


def _compose_contract_model() -> dict[str, object]:
    return {
        "name": "glupta-crawl",
        "networks": {
            "private": {
                "name": "glupta-crawl_private",
                "ipam": {"config": [{"subnet": "172.30.47.0/29"}]},
                "enable_ipv6": False,
            }
        },
        "services": {
            "app": {"networks": {"private": {"ipv4_address": "172.30.47.2"}}},
            "postgres": {"networks": {"private": {"ipv4_address": "172.30.47.3"}}},
        },
    }


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
    assert "mode: system" in candidate
    assert "__GLUPTA_" not in candidate
    assert "proxy" not in candidate.lower()
    render_colima.verify_text(candidate, ROOT, TEMPLATE)


def test_render_replaces_only_its_exact_prior_block(tmp_path: Path) -> None:
    first, updated = tmp_path / "first.yaml", tmp_path / "updated.yaml"
    render_colima.render(_config(tmp_path), first, ROOT, TEMPLATE)
    render_colima.render(first, updated, ROOT, TEMPLATE)
    assert first.read_bytes() == updated.read_bytes()


def test_verify_and_render_accept_colima_marker_normalization(tmp_path: Path) -> None:
    marked, updated = tmp_path / "marked.yaml", tmp_path / "updated.yaml"
    render_colima.render(_config(tmp_path), marked, ROOT, TEMPLATE)
    normalized = "".join(
        line
        for line in marked.read_text(encoding="utf-8").splitlines(keepends=True)
        if "GLUPTA_EGRESS_BEGIN" not in line and "GLUPTA_EGRESS_END" not in line
    )
    active = _config(tmp_path, normalized)

    render_colima.verify_text(normalized, ROOT, TEMPLATE)
    render_colima.render(active, updated, ROOT, TEMPLATE)

    assert updated.read_bytes() == marked.read_bytes()


def test_normalized_owned_block_does_not_authorize_unrelated_provisioning(
    tmp_path: Path,
) -> None:
    marked = tmp_path / "marked.yaml"
    render_colima.render(_config(tmp_path), marked, ROOT, TEMPLATE)
    normalized = "".join(
        line
        for line in marked.read_text(encoding="utf-8").splitlines(keepends=True)
        if "GLUPTA_EGRESS_BEGIN" not in line and "GLUPTA_EGRESS_END" not in line
    )
    unrelated = normalized + "provision:\n  - mode: system\n    script: echo unrelated\n"

    with pytest.raises(render_colima.RenderError, match="unowned or ambiguous"):
        render_colima.render(
            _config(tmp_path, unrelated), tmp_path / "candidate.yaml", ROOT, TEMPLATE
        )
    with pytest.raises(render_colima.RenderError, match="not exact"):
        render_colima.verify_text(unrelated, ROOT, TEMPLATE)


@pytest.mark.parametrize("form", ("marked", "normalized"))
@pytest.mark.parametrize("position", ("before", "after"))
def test_owned_block_rejects_extra_item_in_same_provision_list(
    tmp_path: Path, form: str, position: str
) -> None:
    marked = tmp_path / "marked.yaml"
    render_colima.render(_config(tmp_path), marked, ROOT, TEMPLATE)
    text = marked.read_text(encoding="utf-8")
    if form == "normalized":
        text = "".join(
            line
            for line in text.splitlines(keepends=True)
            if "GLUPTA_EGRESS_BEGIN" not in line
            and "GLUPTA_EGRESS_END" not in line
        )
    extra = "  - mode: user\n    script: echo unrelated\n"
    if position == "before":
        text = text.replace("provision:\n", "provision:\n" + extra, 1)
    else:
        text = text.replace("runtime: docker\n", extra + "runtime: docker\n", 1)

    with pytest.raises(render_colima.RenderError, match="unowned or ambiguous"):
        render_colima.render(
            _config(tmp_path, text), tmp_path / "candidate.yaml", ROOT, TEMPLATE
        )
    with pytest.raises(render_colima.RenderError, match="not exact"):
        render_colima.verify_text(text, ROOT, TEMPLATE)


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
            _config(tmp_path, content), tmp_path / "candidate.yaml", ROOT, TEMPLATE
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
            "\nvolumes:\n", "\n  proxy: {image: proxy}\n\nvolumes:\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(render_colima.RenderError, match="steady-state service"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        ("name: glupta-crawl", "name: changed-project"),
        ("networks:\n  private:", "networks:\n  other:\n  private:"),
        (
            "networks:\n      private:\n        ipv4_address: 172.30.47.2",
            "networks:\n      default: {}\n      private:\n        ipv4_address: 172.30.47.2",
        ),
    ),
)
def test_render_refuses_additional_compose_network_identity(
    tmp_path: Path, old: str, new: str
) -> None:
    repo = _repo_copy(tmp_path)
    path = repo / "compose.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
    with pytest.raises(render_colima.RenderError, match="Compose egress identity"):
        render_colima.render(_config(tmp_path), tmp_path / "candidate.yaml", repo, TEMPLATE)


def test_compose_validator_uses_exact_sanitized_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        render_colima.shutil,
        "which",
        lambda *_args, **_kwargs: "/trusted/docker-compose",
    )

    def run(argv: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, json.dumps(_compose_contract_model()), "")

    monkeypatch.setattr(render_colima.subprocess, "run", run)
    assert render_colima._compose_model(ROOT) == _compose_contract_model()
    assert captured["argv"] == (
        "/trusted/docker-compose",
        "--ansi",
        "never",
        "--env-file",
        "/dev/null",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "compose.yaml"),
        "config",
        "--format",
        "json",
        "--no-interpolate",
        "--no-env-resolution",
        "--no-path-resolution",
    )
    assert captured["env"] == {
        "COMPOSE_DISABLE_ENV_FILE": "1",
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": "/usr/bin:/bin",
    }
    assert captured["cwd"] == ROOT
    assert captured["stdin"] is subprocess.DEVNULL
    assert captured["capture_output"] is True
    assert captured["timeout"] == 10
    assert captured["check"] is False


def test_compose_validator_fails_closed_without_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(render_colima.shutil, "which", lambda *_args, **_kwargs: None)
    with pytest.raises(
        render_colima.RenderError,
        match=r"^Docker Compose semantic validator is unavailable$",
    ):
        render_colima._compose_model(ROOT)


@pytest.mark.parametrize(
    ("outcome", "message"),
    (
        (
            subprocess.TimeoutExpired(
                cmd=("docker-compose",),
                timeout=10,
                output="sensitive-stdout",
                stderr="sensitive-stderr",
            ),
            "Docker Compose semantic validation timed out",
        ),
        (
            subprocess.CompletedProcess(
                ("docker-compose",), 1, "sensitive-stdout", "sensitive-stderr"
            ),
            "Docker Compose semantic validation failed",
        ),
        (
            subprocess.CompletedProcess(
                ("docker-compose",), 0, "not-json-sensitive-stdout", "sensitive-stderr"
            ),
            "Docker Compose semantic validation failed",
        ),
        (
            subprocess.CompletedProcess(
                ("docker-compose",), 0, '["sensitive-model"]', "sensitive-stderr"
            ),
            "Docker Compose semantic validation failed",
        ),
        (OSError("sensitive-os-error"), "Docker Compose semantic validator is unavailable"),
        (
            UnicodeDecodeError("utf-8", b"\xffsensitive", 0, 1, "sensitive-unicode-error"),
            "Docker Compose semantic validation failed",
        ),
    ),
)
def test_compose_validator_failures_do_not_leak_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    outcome: subprocess.CompletedProcess[str] | BaseException,
    message: str,
) -> None:
    monkeypatch.setattr(
        render_colima.shutil,
        "which",
        lambda *_args, **_kwargs: "/trusted/docker-compose",
    )

    def run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(render_colima.subprocess, "run", run)
    with pytest.raises(render_colima.RenderError) as raised:
        render_colima._compose_model(ROOT)
    assert str(raised.value) == message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert "sensitive" not in repr(raised.value)
    product_traceback = raised.value.__traceback__
    while product_traceback is not None and product_traceback.tb_frame.f_code.co_filename != str(
        RENDERER
    ):
        product_traceback = product_traceback.tb_next
    assert product_traceback is not None
    assert "sensitive" not in repr(product_traceback.tb_frame.f_locals)
    captured_traceback = traceback.TracebackException(
        type(raised.value),
        raised.value,
        product_traceback,
        capture_locals=True,
    )
    assert "sensitive" not in "".join(captured_traceback.format())
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("failure_path", "message"),
    (
        ("service", "Compose steady-state service identity changed"),
        ("egress", "Compose egress identity does not match the reviewed contract"),
    ),
)
def test_compose_semantic_failures_do_not_retain_model(
    monkeypatch: pytest.MonkeyPatch,
    failure_path: str,
    message: str,
) -> None:
    marker = "unique-sensitive-semantic-marker"
    model = _compose_contract_model()
    if failure_path == "service":
        services = model["services"]
        assert isinstance(services, dict)
        services[marker] = {"image": marker}
    else:
        networks = model["networks"]
        assert isinstance(networks, dict)
        private = networks["private"]
        assert isinstance(private, dict)
        private[marker] = marker
    monkeypatch.setattr(render_colima, "_compose_model", lambda _repo: model)

    with pytest.raises(render_colima.RenderError) as raised:
        render_colima._validate_contract(ROOT)
    assert str(raised.value) == message
    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None

    product_tracebacks = []
    current = raised.value.__traceback__
    while current is not None:
        if current.tb_frame.f_code.co_filename == str(RENDERER):
            product_tracebacks.append(current)
            assert marker not in repr(current.tb_frame.f_locals)
        current = current.tb_next
    assert product_tracebacks
    captured_traceback = traceback.TracebackException(
        type(raised.value),
        raised.value,
        product_tracebacks[0],
        capture_locals=True,
    )
    assert marker not in "".join(captured_traceback.format())


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
        adapter.read_text(encoding="utf-8") + '\nchatgpt_base_url = "https://elsewhere.invalid"\n',
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


def _write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _run_template(
    tmp_path: Path,
    *,
    uid: int = 0,
    nft_fail_call: int = 0,
    dnsmasq_test_fails: bool = False,
    install_fail_destination: str = "",
) -> tuple[subprocess.CompletedProcess[str], str]:
    fake_bin = tmp_path / "bin"
    state = tmp_path / "state"
    fake_bin.mkdir()
    state.mkdir()
    log = state / "calls.log"
    rendered = tmp_path / "egress.sh"
    rendered.write_text(render_colima._script(TEMPLATE), encoding="utf-8")
    rendered.chmod(0o755)

    _write_executable(fake_bin / "id", f"#!/bin/sh\nprintf '%s\\n' {uid}\n")
    _write_executable(
        fake_bin / "mktemp",
        """#!/bin/sh
count_file="$FAKE_STATE/mktemp-count"
count=0
[ ! -f "$count_file" ] || count="$(cat "$count_file")"
count=$((count + 1))
printf '%s\n' "$count" >"$count_file"
path="$FAKE_STATE/candidate-$count"
: >"$path"
printf '%s\n' "$path"
""",
    )
    _write_executable(
        fake_bin / "nft",
        """#!/bin/sh
if [ "$1" = list ]; then
    exit 1
fi
if [ "$1" = --check ]; then
    printf 'NFT_CHECK\n' >>"$FAKE_LOG"
    exit 0
fi
count_file="$FAKE_STATE/nft-count"
count=0
[ ! -f "$count_file" ] || count="$(cat "$count_file")"
count=$((count + 1))
printf '%s\n' "$count" >"$count_file"
printf 'NFT_CALL_%s\n' "$count" >>"$FAKE_LOG"
cat "$2" >>"$FAKE_LOG"
printf 'NFT_END_%s\n' "$count" >>"$FAKE_LOG"
[ "$FAKE_NFT_FAIL_CALL" -ne "$count" ]
""",
    )
    _write_executable(
        fake_bin / "dnsmasq",
        """#!/bin/sh
printf 'dnsmasq %s\n' "$*" >>"$FAKE_LOG"
if [ "$1" = --version ]; then
    printf 'dnsmasq nftset\n'
    exit 0
fi
[ "$FAKE_DNSMASQ_TEST_FAILS" -eq 0 ]
""",
    )
    _write_executable(
        fake_bin / "install",
        """#!/bin/sh
printf 'install %s\n' "$*" >>"$FAKE_LOG"
[ "$1" != -d ] || exit 0
source=""
destination=""
for argument in "$@"; do
    source="$destination"
    destination="$argument"
done
[ "$destination" != "$FAKE_INSTALL_FAIL_DESTINATION" ] || exit 73
case "$destination" in
    /usr/local/sbin/glupta-egress-apply)
        cp "$source" "$FAKE_STATE/installed-script"
        chmod 0755 "$FAKE_STATE/installed-script"
        ;;
    /etc/systemd/system/glupta-egress.service)
        cp "$source" "$FAKE_STATE/service-unit"
        ;;
    /etc/systemd/system/*/90-glupta-egress.conf)
        cp "$source" "$FAKE_STATE/dropin-unit"
        ;;
esac
""",
    )
    _write_executable(
        fake_bin / "systemctl",
        """#!/bin/sh
printf 'systemctl %s\n' "$*" >>"$FAKE_LOG"
if [ "$1:$2" = restart:glupta-egress.service ]; then
    /bin/sh "$FAKE_STATE/installed-script" --apply
fi
""",
    )
    _write_executable(
        fake_bin / "sudo",
        "#!/bin/sh\nprintf 'sudo %s\\n' \"$*\" >>\"$FAKE_LOG\"\nexit 77\n",
    )

    env = {
        "PATH": f"{fake_bin}:/usr/bin:/bin",
        "FAKE_STATE": str(state),
        "FAKE_LOG": str(log),
        "FAKE_NFT_FAIL_CALL": str(nft_fail_call),
        "FAKE_DNSMASQ_TEST_FAILS": "1" if dnsmasq_test_fails else "0",
        "FAKE_INSTALL_FAIL_DESTINATION": install_fail_destination,
    }
    completed = subprocess.run(  # noqa: S603
        ["/bin/sh", str(rendered)],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )
    return completed, log.read_text(encoding="utf-8") if log.exists() else ""


def test_system_provision_rejects_non_root_even_when_sudo_fails(tmp_path: Path) -> None:
    completed, log = _run_template(tmp_path, uid=501)

    assert completed.returncode != 0
    assert log == ""


def test_system_provision_fails_closed_if_initial_nft_apply_fails(tmp_path: Path) -> None:
    completed, log = _run_template(tmp_path, nft_fail_call=1)

    assert completed.returncode != 0
    assert log.count("NFT_CALL_") == 1
    assert "ip saddr 172.30.47.2 reject" in log
    assert "dnsmasq " not in log
    assert "systemctl mask --now docker.service docker.socket containerd.service" in log
    assert "systemctl unmask" not in log


def test_interruption_after_persistent_mask_leaves_future_boot_closed(
    tmp_path: Path,
) -> None:
    completed, log = _run_template(
        tmp_path, install_fail_destination="/usr/local/sbin/glupta-egress-apply"
    )

    assert completed.returncode == 73
    assert "systemctl mask --now docker.service docker.socket containerd.service" in log
    assert "systemctl unmask" not in log
    assert "/etc/systemd/system/glupta-egress.service" not in log
    assert "NFT_CALL_" not in log


def test_system_provision_leaves_failsafe_after_later_failure(tmp_path: Path) -> None:
    completed, log = _run_template(tmp_path, dnsmasq_test_fails=True)

    assert completed.returncode != 0
    assert log.count("NFT_CALL_") == 1
    assert "ip saddr 172.30.47.2 reject" in log
    assert "ip daddr @codex4" not in log
    assert "systemctl mask --now docker.service docker.socket containerd.service" in log
    assert "systemctl unmask" not in log


def test_system_provision_replaces_failsafe_only_on_success(tmp_path: Path) -> None:
    completed, log = _run_template(tmp_path)

    assert completed.returncode == 0
    assert log.count("NFT_CALL_") == 2
    assert "ip saddr 172.30.47.2 reject" in log
    assert "ip daddr 172.30.47.3 tcp dport 5432 accept" in log
    assert "ip daddr @codex4 tcp dport 443 accept" in log
    assert "systemctl restart dnsmasq" in log
    assert "systemctl is-active --quiet dnsmasq" in log
    assert "systemctl stop" not in log
    assert "systemctl mask --now docker.service docker.socket containerd.service" in log
    assert "systemctl unmask docker.service docker.socket containerd.service" in log
    assert "sudo " not in log


def test_system_provision_installs_durable_runtime_ordering(tmp_path: Path) -> None:
    completed, log = _run_template(tmp_path)

    assert completed.returncode == 0
    state = tmp_path / "state"
    installed_script = (state / "installed-script").read_text(encoding="utf-8")
    service = (state / "service-unit").read_text(encoding="utf-8")
    dropin = (state / "dropin-unit").read_text(encoding="utf-8")
    assert installed_script == render_colima._script(TEMPLATE)
    assert "Before=docker.service docker.socket containerd.service" in service
    assert "ExecStart=/usr/local/sbin/glupta-egress-apply --apply" in service
    assert "Type=oneshot" in service
    assert "RemainAfterExit=yes" in service
    assert "WantedBy=multi-user.target" in service
    assert "Requires=glupta-egress.service" in dropin
    assert "After=glupta-egress.service" in dropin
    for unit in ("docker.service", "docker.socket", "containerd.service"):
        assert f"/etc/systemd/system/{unit}.d/90-glupta-egress.conf" in log
    assert log.index("systemctl restart glupta-egress.service") < log.index("NFT_CALL_1")
    assert log.index("systemctl is-active --quiet glupta-egress.service") < log.index(
        "systemctl unmask docker.service"
    )

    required = {
        dependency
        for line in dropin.splitlines()
        if line.startswith("Requires=")
        for dependency in line.removeprefix("Requires=").split()
    }
    ordered_after = {
        dependency
        for line in dropin.splitlines()
        if line.startswith("After=")
        for dependency in line.removeprefix("After=").split()
    }
    failed_jobs = {"glupta-egress.service"}
    for runtime in ("docker.service", "docker.socket", "containerd.service"):
        # systemd.unit: an activated unit is not started when a Requires= target
        # fails activation and the dependent is ordered After= that target.
        runtime_started = not bool(required & ordered_after & failed_jobs)
        assert not runtime_started, runtime


def test_shell_template_is_syntax_checked_and_fail_closed() -> None:
    subprocess.run(["/bin/sh", "-n", str(TEMPLATE)], check=True)  # noqa: S603
    script = TEMPLATE.read_text(encoding="utf-8")
    assert "priority filter - 10" in script
    assert "ip saddr 172.30.47.2" in script
    assert "ip daddr 172.30.47.3 tcp dport 5432 accept" in script
    assert "ip daddr @codex4 tcp dport 443 accept" in script
    assert "counter name glupta_denied reject" in script
    assert "systemctl stop docker.service docker.socket containerd.service" not in script
    assert "Requires=glupta-egress.service" in script
    assert "After=glupta-egress.service" in script
    assert "sudo " not in script
    assert all(term not in script.lower() for term in ("curl ", "wget ", "proxy", "sidecar"))
