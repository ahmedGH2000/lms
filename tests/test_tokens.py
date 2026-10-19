import importlib.util
from pathlib import Path
import pytest
from nightjar_learning.tokens import issue, verify, safe_path

SECRET = "testing-only-secret-" * 3
ASSET = "a" * 32


def grant():
    return issue(
        SECRET,
        member="alice",
        session="session-a",
        lesson="lesson",
        asset=ASSET,
        now=1000,
    )


def test_valid_grant():
    assert (
        verify(SECRET, grant(), member="alice", session="session-a", now=1001)["l"]
        == "lesson"
    )


@pytest.mark.parametrize(
    "member,session,now",
    [
        ("bob", "session-a", 1001),
        ("alice", "session-b", 1001),
        ("alice", "session-a", 1300),
        ("alice", "session-a", 989),
    ],
)
def test_identity_expiry_and_future(member, session, now):
    with pytest.raises(ValueError):
        verify(SECRET, grant(), member=member, session=session, now=now)


@pytest.mark.parametrize("token", ["", "bad", "a.b.c", "a.b", "x" * 4097, None])
def test_malformed(token):
    with pytest.raises(ValueError):
        verify(SECRET, token, member="alice", session="session-a", now=1001)


def test_tampering_and_rotation():
    with pytest.raises(ValueError):
        verify(
            SECRET, grant()[:-1] + "!", member="alice", session="session-a", now=1001
        )
    with pytest.raises(ValueError):
        verify(
            SECRET + "rotated", grant(), member="alice", session="session-a", now=1001
        )


def test_weak_secret_rejected():
    with pytest.raises(ValueError):
        issue("weak", member="a", session="s", lesson="l", asset=ASSET)


@pytest.mark.parametrize(
    "filename",
    [
        "../key.bin",
        "/etc/passwd",
        "metadata.json",
        "segment_00000.ts/../key.bin",
        "%2e%2e/key.bin",
    ],
)
def test_path_traversal(tmp_path, filename):
    with pytest.raises(ValueError):
        safe_path(tmp_path, ASSET, filename)


def test_path_and_symlink(tmp_path):
    folder = tmp_path / ASSET
    folder.mkdir()
    key = folder / "key.bin"
    key.write_bytes(b"key")
    assert safe_path(tmp_path, ASSET, "key.bin") == key
    key.unlink()
    outside = tmp_path / "secret"
    outside.write_bytes(b"secret")
    key.symlink_to(outside)
    with pytest.raises(ValueError):
        safe_path(tmp_path, ASSET, "key.bin")


def test_asset_directory_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "key.bin").write_bytes(b"secret")
    (tmp_path / ASSET).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        safe_path(tmp_path, ASSET, "key.bin")
