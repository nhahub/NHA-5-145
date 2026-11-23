import hashlib
import json
import os
import re
import subprocess
from zipfile import ZipFile

import pytest


def git(root, *arguments, input=None):
    environment = dict(os.environ)
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_TERMINAL_PROMPT="0",
        GIT_AUTHOR_DATE="2026-10-24T00:00:00+00:00",
        GIT_COMMITTER_DATE="2026-10-24T00:00:00+00:00",
    )
    return subprocess.run(
        ["git", "-c", f"core.hooksPath={os.devnull}", "-C", str(root), *arguments],
        input=input,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    ).stdout.strip()


@pytest.fixture
def reviewed(tmp_path):
    root = tmp_path / "reviewed source with spaces"
    root.mkdir()
    git(root, "init", "--template=")
    git(root, "config", "user.name", "Synthetic Reviewer")
    git(root, "config", "user.email", "reviewer@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    (root / ".gitignore").write_text(".scratch/\n", encoding="utf-8")
    (root / "app.py").write_text("print('reviewed')\n", encoding="utf-8")
    git(root, "add", ".gitignore", "app.py")
    git(root, "commit", "-m", "Reviewed source")
    return root, git(root, "rev-parse", "HEAD"), git(root, "rev-parse", "HEAD^{tree}")


def test_exact_original_provenance_is_deterministic_and_credential_free(reviewed, tmp_path):
    from eval.native_release_source import prepare

    root, revision, tree = reviewed
    marker = "SYNTHETIC_OWNER_CREDENTIAL_NEVER_EXPORT"
    git(root, "config", "remote.private.url", f"https://{marker}@example.invalid/private")
    git(root, "config", "credential.helper", marker)
    (root / ".git/owner-private").write_text(marker)
    (root / ".scratch").mkdir()
    (root / ".scratch/ignored-private").write_text(marker)
    before = (root / ".git/config").read_bytes()
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    report = prepare(root, first, revision=revision)
    assert prepare(root, second, revision=revision) == report
    assert first.read_bytes() == second.read_bytes()
    assert report["commit"] == revision
    assert report["tree"] == tree
    assert report["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert report["bytes"] == first.stat().st_size
    with ZipFile(first) as archive:
        manifest = json.loads(archive.read("source-snapshot.json"))
        assert manifest["format"] == 1
        assert manifest["commit"] == revision
        assert manifest["tree"] == tree
        assert set(archive.namelist()) == {*manifest["files"], "source-snapshot.json"}
        assert report["files"] == len(manifest["files"])
        assert archive.read(".git/HEAD") == f"{revision}\n".encode()
        assert archive.read(".git/shallow") == f"{revision}\n".encode()
        assert archive.read(".git/config") == (
            b"[core]\n\trepositoryformatversion = 0\n\tbare = false\n"
            b"\tfilemode = true\n\tautocrlf = false\n"
        )
        for entry in archive.infolist():
            assert entry.date_time == (1980, 1, 1, 0, 0, 0)
            assert not entry.is_dir()
            assert marker.encode() not in archive.read(entry)
            if entry.filename != "source-snapshot.json":
                assert (
                    hashlib.sha256(archive.read(entry)).hexdigest()
                    == manifest["files"][entry.filename]
                )
                assert entry.filename in {
                    ".git/HEAD",
                    ".git/config",
                    ".git/shallow",
                } or re.fullmatch(
                    r"\.git/objects/(?:[a-f0-9]{2}/[a-f0-9]{38}|pack/pack-[a-f0-9]{40}\.(?:pack|idx|rev))",
                    entry.filename,
                )
    assert (root / ".git/config").read_bytes() == before
    assert git(root, "status", "--porcelain", "--untracked-files=all") == ""


def test_snapshot_supports_real_git_checkout_fsck_and_clean_tree(reviewed, tmp_path):
    from eval.native_release_source import prepare

    root, revision, tree = reviewed
    output = tmp_path / "source.zip"
    prepare(root, output, revision=revision)
    checkout = tmp_path / "native checkout with spaces"
    checkout.mkdir()
    with ZipFile(output) as archive:
        archive.extractall(
            checkout, [name for name in archive.namelist() if name.startswith(".git/")]
        )
    (checkout / ".git/refs").mkdir()
    git(checkout, "checkout", "--detach", revision)
    git(checkout, "fsck", "--full", "--strict")
    assert git(checkout, "rev-parse", "HEAD") == revision
    assert git(checkout, "rev-parse", "HEAD^{tree}") == tree
    assert git(checkout, "status", "--porcelain", "--untracked-files=all") == ""
    assert (checkout / "app.py").read_bytes() == (root / "app.py").read_bytes()
    assert not (checkout / ".git/FETCH_HEAD").exists()
    assert not (checkout / ".git/refs/remotes").exists()


def test_original_commit_is_kept_without_exporting_prior_history(reviewed, tmp_path):
    from eval.native_release_source import prepare

    root, _, _ = reviewed
    previous = root / "historical-private"
    previous.write_text("SYNTHETIC_HISTORY_EXCLUDED")
    git(root, "add", "historical-private")
    git(root, "commit", "-m", "Historical fixture")
    old_commit = git(root, "rev-parse", "HEAD")
    old_blob = git(root, "rev-parse", "HEAD:historical-private")
    git(root, "rm", "historical-private")
    git(root, "commit", "-m", "Reviewed removal")
    revision = git(root, "rev-parse", "HEAD")
    output = tmp_path / "source.zip"
    prepare(root, output, revision=revision)
    checkout = tmp_path / "shallow checkout"
    checkout.mkdir()
    with ZipFile(output) as archive:
        archive.extractall(
            checkout, [name for name in archive.namelist() if name.startswith(".git/")]
        )
    (checkout / ".git/refs").mkdir()
    assert git(checkout, "cat-file", "-p", revision) == git(root, "cat-file", "-p", revision)
    assert f"parent {old_commit}" in git(checkout, "cat-file", "-p", revision)
    for excluded in (old_commit, old_blob):
        with pytest.raises(subprocess.CalledProcessError):
            git(checkout, "cat-file", "-e", excluded)
    git(checkout, "fsck", "--full", "--strict")


@pytest.mark.parametrize("kind", ["tracked", "staged", "untracked", "mismatch", "alias", "invalid"])
def test_dirty_or_noncurrent_exact_revision_is_refused(reviewed, tmp_path, kind):
    from eval.native_release_source import prepare

    root, revision, _ = reviewed
    if kind in {"tracked", "staged"}:
        (root / "app.py").write_text("unreviewed change")
        if kind == "staged":
            git(root, "add", "app.py")
    elif kind == "untracked":
        (root / "private-secret").write_text("SYNTHETIC_UNTRACKED_SECRET")
    else:
        revision = {"mismatch": "f" * 40, "alias": "HEAD", "invalid": "-" * 40}[kind]
    output = tmp_path / "refused.zip"
    with pytest.raises(ValueError, match="^Native source snapshot refused$"):
        prepare(root, output, revision=revision)
    assert not output.exists()


@pytest.mark.parametrize(
    "kind", ["overwrite", "inside", "missing-parent", "symlink", "parent-link"]
)
def test_output_must_be_new_external_regular_destination(reviewed, tmp_path, kind):
    from eval.native_release_source import prepare

    root, revision, _ = reviewed
    output = tmp_path / "refused.zip"
    if kind == "overwrite":
        output.write_bytes(b"preserve")
    elif kind == "inside":
        (root / ".scratch").mkdir()
        output = root / ".scratch/source.zip"
    elif kind == "missing-parent":
        output = tmp_path / "absent/source.zip"
    else:
        original = tmp_path / "original"
        original.mkdir()
        link = output if kind == "symlink" else tmp_path / "linked-parent"
        try:
            link.symlink_to(original, target_is_directory=True)
        except OSError:
            pytest.skip("Symlink creation unavailable")
        if kind == "parent-link":
            output = link / "source.zip"
    with pytest.raises(ValueError, match="^Native source snapshot refused$"):
        prepare(root, output, revision=revision)
    if kind == "overwrite":
        assert output.read_bytes() == b"preserve"
    elif kind != "symlink":
        assert not output.exists()


@pytest.mark.parametrize("mode", ["120000", "160000"])
def test_tracked_symlinks_and_submodules_are_refused(reviewed, tmp_path, mode):
    from eval.native_release_source import prepare

    root, revision, _ = reviewed
    object_id = (
        git(root, "hash-object", "-w", "--stdin", input="app.py") if mode == "120000" else revision
    )
    git(root, "update-index", "--add", "--cacheinfo", f"{mode},{object_id},unsupported")
    git(root, "commit", "-m", "Unsupported tracked entry")
    revision = git(root, "rev-parse", "HEAD")
    output = tmp_path / "refused.zip"
    with pytest.raises(ValueError, match="^Native source snapshot refused$"):
        prepare(root, output, revision=revision)
    assert not output.exists()


@pytest.mark.parametrize("bound", ["_MAX_BYTES", "_MAX_MEMBERS"])
def test_snapshot_bounds_refuse_without_publishing(reviewed, tmp_path, monkeypatch, bound):
    from eval import native_release_source

    root, revision, _ = reviewed
    monkeypatch.setattr(native_release_source, bound, 1)
    output = tmp_path / "refused.zip"
    with pytest.raises(ValueError, match="^Native source snapshot refused$"):
        native_release_source.prepare(root, output, revision=revision)
    assert not output.exists()
