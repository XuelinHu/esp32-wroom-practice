"""Download ESP32 WAV recordings and convert them to local MP3 files."""

import re
import shutil
import subprocess
from pathlib import Path


PORT = "COM9"
REMOTE_DIR = ":/recordings"
LOCAL_DIR = Path(__file__).resolve().parent / "recordings"


def run_capture(args):
    return subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def remote_wav_names(mpremote):
    output = run_capture([
        mpremote, "connect", PORT, "fs", "ls", REMOTE_DIR
    ])
    names = []
    for line in output.splitlines():
        match = re.search(r"([A-Za-z0-9_.-]+\.wav)\s*$", line)
        if match:
            names.append(match.group(1))
    return names


def main():
    mpremote = shutil.which("mpremote")
    ffmpeg = shutil.which("ffmpeg")
    if mpremote is None:
        raise SystemExit("mpremote not found; run this command in the pyg environment")
    if ffmpeg is None:
        raise SystemExit("ffmpeg not found in PATH")

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    names = remote_wav_names(mpremote)
    if not names:
        print("No WAV recordings found on ESP32")
        return

    for name in names:
        local_wav = LOCAL_DIR / name
        local_mp3 = local_wav.with_suffix(".mp3")
        remote_path = REMOTE_DIR + "/" + name
        print("Downloading", name)
        subprocess.run(
            [mpremote, "connect", PORT, "fs", "cp", remote_path, str(local_wav)],
            check=True,
        )
        print("Converting", local_mp3.name)
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(local_wav),
                "-codec:a", "libmp3lame", "-b:a", "96k",
                str(local_mp3),
            ],
            check=True,
        )
        print("Saved", local_mp3)


if __name__ == "__main__":
    main()
