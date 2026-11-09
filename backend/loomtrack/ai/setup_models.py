"""Download the two IndicTrans2 models and check that they translate. Run once, from the backend folder:

    python -m loomtrack.ai.setup_models           download (if needed), then translate a few sample lines
    python -m loomtrack.ai.setup_models --check   only translate the sample lines

The models are gated on Hugging Face: sign in at huggingface.co, accept the terms on each model page
(ai4bharat/indictrans2-indic-en-dist-200M and ai4bharat/indictrans2-en-indic-dist-200M), create a Read token and
put it in backend/.env as HF_TOKEN=... The token is only used here, to download.
"""

from __future__ import annotations

import asyncio
import sys

from .. import config
from . import translate

SAMPLES_TA = [
    "பிரிண்டிங் யூனிட்டில் கரண்ட் இல்லை, ஜெனரேட்டர் டீசல் தீர்ந்தது",
    "நூல் தீர்ந்துவிட்டது, லாரி நாளை வரும்",
    "இரண்டு மெஷின் பழுது, மெக்கானிக் வந்தார்",
    "இன்று 800 பீஸ் தைத்தோம், ஆட்கள் குறைவு",
    "துணி இன்னும் வரவில்லை",
]
SAMPLES_EN = [
    "Please send the fit sample photo today.",
    "Cutting is complete, stitching starts tomorrow.",
    "Your order is delayed by two days because of a power cut.",
]


def download() -> None:
    from huggingface_hub import snapshot_download

    token = config.hf_token()
    if not token:
        sys.exit("No HF_TOKEN in backend/.env. See the top of this file for how to get one (free).")
    for direction, (repo, revision, _, _) in translate.MODELS.items():
        print(f"downloading {repo} ...")
        try:
            snapshot_download(repo, revision=revision, token=token)
        except Exception as e:
            if any(code in str(e) for code in ("401", "403", "gated")):
                hint = f"Open https://huggingface.co/{repo}, accept the terms, and check the token."
            else:
                hint = "Run it again: a download picks up where it stopped."
            sys.exit(f"Could not download {repo}: {e}\n{hint}")


def check() -> int:
    print(translate.status(fresh=True))
    if not translate.available():
        return 1
    import time

    async def go() -> None:
        for text in SAMPLES_TA:
            t0 = time.time()
            print(f"{text}\n   -> {await translate.to_english(text)}   ({time.time() - t0:.2f}s)")
        for text in SAMPLES_EN:
            t0 = time.time()
            print(f"{text}\n   -> {await translate.to_tamil(text)}   ({time.time() - t0:.2f}s)")

    asyncio.run(go())
    return 0


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")  # Tamil on a Windows console
    if "--check" not in sys.argv:
        download()
    sys.exit(check())
