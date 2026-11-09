"""Download the Whisper model for Tamil voice notes and check it. Run once, from the backend folder:

    python -m loomtrack.ai.setup_speech                download (about 3 GB, no token needed), then check
    python -m loomtrack.ai.setup_speech --check        only check
    python -m loomtrack.ai.setup_speech some_note.webm also write out that recording
"""

from __future__ import annotations

import asyncio
import sys
import time

from . import speech


def download() -> None:
    from huggingface_hub import snapshot_download

    print(f"downloading {speech.REPO} ...")
    snapshot_download(speech.REPO)


def check(files: list[str]) -> int:
    print(speech.status(fresh=True))
    if not speech.available():
        return 1
    t0 = time.time()
    speech._load()
    print(f"model loaded in {time.time() - t0:.1f}s")

    async def go() -> None:
        for f in files:
            t0 = time.time()
            print(f"{f}\n   -> {await speech.to_text(f)}   ({time.time() - t0:.1f}s)")

    asyncio.run(go())
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--check" not in sys.argv:
        download()
    sys.exit(check(args))
