import importlib.util
import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required"
)
def test_encrypted_hls_round_trip(tmp_path):
    path = Path(__file__).parents[1] / "scripts/package_video.py"
    spec = importlib.util.spec_from_file_location("packager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "input.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=navy:s=320x180:r=15",
            "-t",
            "7",
            "-c:v",
            "libx264",
            str(source),
        ],
        check=True,
    )
    metadata = module.package(source, tmp_path / "media")
    folder = tmp_path / "media" / metadata["asset_id"]
    assert 6.9 < metadata["duration"] < 7.1
    assert len((folder / "key.bin").read_bytes()) == 16
    assert "METHOD=AES-128" in (folder / "index.m3u8").read_text()
    assert not any(folder.glob("*keyinfo*"))
    assert (folder / "key.bin").stat().st_mode & 0o777 == 0o600
    # Decode the encrypted playlist with its key: verifies actual playable media, not just strings.
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-allowed_extensions",
            "ALL",
            "-i",
            str(folder / "index.m3u8"),
            "-f",
            "null",
            "-",
        ],
        check=True,
    )
