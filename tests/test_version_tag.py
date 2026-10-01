"""Run the actual tagging workflow script against a temporary local remote."""

import os
import shutil
import subprocess  # nosec B404 - exercise Git and the workflow in temporary local repositories
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/master.yml"


def test_version_tag(tmp_path: Path) -> None:
    """Create a tag, preserve it on reruns/new commits, and fail on remote errors."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    script = workflow["jobs"]["release"]["steps"][-2]["run"]
    remote = tmp_path / "remote.git"
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    git = shutil.which("git")
    bash = shutil.which("bash")
    assert git is not None and bash is not None
    env = {**os.environ, "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}"}

    def command(*args: str) -> str:
        # Arguments come only from this test and its local temporary paths.
        return subprocess.check_output(args, cwd=checkout, env=env, text=True)  # nosec B603

    command(git, "init", "--bare", str(remote))
    command(git, "init", "-b", "main")
    command(git, "config", "user.name", "Tag test")
    command(git, "config", "user.email", "tag-test@example.invalid")
    command(git, "config", "commit.gpgsign", "false")
    command(git, "config", "core.hooksPath", str(tmp_path / "no-hooks"))
    command(git, "remote", "add", "origin", str(remote))
    (checkout / "pyproject.toml").write_text('[project]\nversion = "2.6.0"\n')
    command(git, "add", "pyproject.toml")
    command(git, "commit", "-m", "test version")
    original = command(git, "rev-parse", "HEAD").strip()
    command(bash, "-c", script)
    command(git, "commit", "--allow-empty", "-m", "same version")
    assert "already exists" in command(bash, "-c", script)
    assert command(git, "ls-remote", "--tags", "origin").strip() == f"{original}\trefs/tags/2.6.0"
    command(git, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    with pytest.raises(subprocess.CalledProcessError):
        command(bash, "-c", script)


def test_version_release(tmp_path: Path) -> None:
    """Create a missing release, preserve it on reruns, and propagate CLI failures."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    script = workflow["jobs"]["release"]["steps"][-1]["run"]
    bash = shutil.which("bash")
    assert bash is not None
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.6.0"\n')
    gh = tmp_path / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        'if [ "$FAIL_GH" = "1" ]; then exit 2; fi\n'
        'case "$1 $2" in\n'
        '  "release view") test -f release.txt ;;\n'
        '  "release create") printf "%s\\n" "$@" > release.txt ;;\n'
        "  *) exit 2 ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}{os.pathsep}{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "FAIL_GH": "0",
    }

    def run() -> str:
        return subprocess.check_output([bash, "-c", script], cwd=tmp_path, env=env, text=True)  # nosec B603

    run()
    release = tmp_path / "release.txt"
    assert release.read_text().splitlines() == [
        "release",
        "create",
        "2.6.0",
        "--verify-tag",
        "--generate-notes",
        "--title",
        "2.6.0",
    ]
    release.write_text("existing release")
    assert "already exists" in run()
    assert release.read_text() == "existing release"
    env["FAIL_GH"] = "1"
    with pytest.raises(subprocess.CalledProcessError):
        run()
