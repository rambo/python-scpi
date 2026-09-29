"""Run the actual tagging workflow script against a temporary local remote."""

import os
import shutil
import subprocess  # nosec B404 - exercise Git and the workflow in temporary local repositories
import sys
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).parents[1] / ".github/workflows/check.yml"


def test_version_tag(tmp_path: Path) -> None:
    """Create a tag, preserve it on reruns/new commits, and fail on remote errors."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    script = workflow["jobs"]["tag"]["steps"][-1]["run"]
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
