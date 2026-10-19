"""Patch safety with real temporary Git repositories, not mocked Git results."""
import importlib.util
from pathlib import Path
import subprocess
import pytest


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def fixture(tmp_path):
    source = Path(__file__).parents[1] / "deploy/apply_upstream_patches.py"
    spec = importlib.util.spec_from_file_location("reviewed_patches", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__file__ = str(tmp_path / "deploy/apply_upstream_patches.py")
    patches = tmp_path / "deploy/patches"
    patches.mkdir(parents=True)
    targets = []
    for name in ("frappe", "lms"):
        repo = tmp_path / "apps" / name
        run("git", "init", str(repo))
        run("git", "-C", str(repo), "config", "user.email", "test@example.invalid")
        run("git", "-C", str(repo), "config", "user.name", "Test")
        (repo / "source.txt").write_text("before\n")
        run("git", "-C", str(repo), "add", ".")
        run("git", "-C", str(repo), "commit", "-m", "fixture")
        revision = run("git", "-C", str(repo), "rev-parse", "HEAD")
        (patches / (name + ".patch")).write_text("diff --git a/source.txt b/source.txt\n--- a/source.txt\n+++ b/source.txt\n@@ -1 +1 @@\n-before\n+after\n")
        targets.append((name, revision, name + ".patch"))
    module.TARGETS = targets
    return module


def test_applies_once_and_keeps_unrelated_edits(tmp_path):
    module = fixture(tmp_path)
    unrelated = tmp_path / "apps/lms/unrelated.txt"
    unrelated.write_text("user work")
    module.apply(tmp_path)
    module.apply(tmp_path)
    assert (tmp_path / "apps/frappe/source.txt").read_text() == "after\n"
    assert (tmp_path / "apps/lms/source.txt").read_text() == "after\n"
    assert unrelated.read_text() == "user work"


def test_conflicting_second_patch_leaves_first_repo_untouched(tmp_path):
    module = fixture(tmp_path)
    target = tmp_path / "apps/lms/source.txt"
    target.write_text("user edits\n")
    with pytest.raises(SystemExit, match="conflicting"):
        module.apply(tmp_path)
    assert (tmp_path / "apps/frappe/source.txt").read_text() == "before\n"
    assert target.read_text() == "user edits\n"


def test_unknown_revision_refused(tmp_path):
    module = fixture(tmp_path)
    module.TARGETS[0] = ("frappe", "0" * 40, "frappe.patch")
    with pytest.raises(SystemExit, match="reviewed revision"):
        module.apply(tmp_path)
    assert (tmp_path / "apps/frappe/source.txt").read_text() == "before\n"
