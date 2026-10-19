#!/usr/bin/env python3
import argparse, json, secrets, shutil, subprocess, tempfile
from pathlib import Path


def package(source, root):
    source = Path(source).resolve(strict=True)
    if not source.is_file():
        raise ValueError("Input must be a local video file")
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    asset = secrets.token_hex(16)
    target = root / asset
    target.mkdir(mode=0o700)
    try:
        key = target / "key.bin"
        key.write_bytes(secrets.token_bytes(16))
        key.chmod(0o600)
        with tempfile.TemporaryDirectory() as temp:
            info = Path(temp) / "keyinfo"
            info.write_text("key.bin\n" + str(key) + "\n")
            info.chmod(0o600)
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-nostdin",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-vf",
                    "scale=w=1280:h=720:force_original_aspect_ratio=decrease:force_divisible_by=2",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-force_key_frames",
                    "expr:gte(t,n_forced*6)",
                    "-hls_time",
                    "6",
                    "-hls_playlist_type",
                    "vod",
                    "-hls_key_info_file",
                    str(info),
                    "-hls_segment_filename",
                    str(target / "segment_%05d.ts"),
                    str(target / "index.m3u8"),
                ],
                check=True,
            )
        data = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(source),
                ]
            )
        )
        result = {"asset_id": asset, "duration": float(data["format"]["duration"])}
        (target / "metadata.json").write_text(json.dumps(result))
        for p in target.iterdir():
            p.chmod(0o600)
        return result
    except BaseException:
        shutil.rmtree(target)
        raise


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--root", required=True)
    a = p.parse_args()
    print(json.dumps(package(a.source, a.root), indent=2))
