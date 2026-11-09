"""Tamil speech to text on this machine, with Whisper (large-v3, run by faster-whisper).

Whisper is OpenAI's open-weight speech model (MIT license). Nothing leaves the machine and nothing is paid for.
A supervisor's voice note is written out here, and the text then goes through the same translate-and-classify
step as a typed note. The weights (about 3 GB, no token needed) are downloaded once with
`python -m loomtrack.ai.setup_speech`; the app itself never downloads anything. Until they are there, callers get
`None` and the voice note stays a recording for the merchandiser to listen to.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import threading
import time

from .. import config
from ..domain.reasons import REASON_CATEGORIES

REPO = "Systran/faster-whisper-large-v3"
LABEL = "Whisper large-v3"
LANGUAGE = "ta"
MAX_SECONDS = 120  # a voice note is a sentence or two; a longer recording is cut here to keep the machine free


def libraries_installed() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def downloaded() -> bool:
    """The weights are in the local cache. This never touches the network."""
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(REPO, local_files_only=True)
        return True
    except Exception:
        return False


def _use_gpu() -> bool:
    want = config.translate_device()
    if want == "cpu":
        return False
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


_status_cache: tuple[float, dict] | None = None


def status(*, fresh: bool = False) -> dict:
    """{'mode': 'whisper', 'model', 'device'} when ready, else {'mode': 'off', 'reason'}."""
    global _status_cache
    if _status_cache and not fresh and time.monotonic() - _status_cache[0] < 20:
        return _status_cache[1]
    if not config.ai_enabled():
        out = {"mode": "off", "reason": "Speech to text turned off (LOOMTRACK_AI=off)"}
    elif not libraries_installed():
        out = {"mode": "off", "reason": "Speech libraries are not installed (pip install -r requirements-speech.txt)"}
    elif not downloaded():
        out = {"mode": "off", "reason": "The speech model is not downloaded yet (python -m loomtrack.ai.setup_speech)"}
    else:
        out = {"mode": "whisper", "model": LABEL, "device": "cuda" if _use_gpu() else "cpu"}
    _status_cache = (time.monotonic(), out)
    return out


def available() -> bool:
    return status()["mode"] == "whisper"


_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            gpu = _use_gpu()
            if gpu:
                # CTranslate2 looks for the CUDA libraries on the DLL path; PyTorch ships them in its own folder.
                import torch

                lib = os.path.join(os.path.dirname(torch.__file__), "lib")
                if os.path.isdir(lib) and hasattr(os, "add_dll_directory"):
                    os.add_dll_directory(lib)
            from faster_whisper import WhisperModel

            # 8-bit weights: about 1.6 GB on the GPU, so it sits beside the translation models on a 6 GB card.
            _model = WhisperModel(REPO, device="cuda" if gpu else "cpu", compute_type="int8_float16" if gpu else "int8", local_files_only=True)
        return _model


def _spelling_hint() -> str:
    """The words a supervisor reports problems with, spelled the way the app spells them. Whisper otherwise
    drops letters in them (it wrote பற்றக்குரை for பற்றாக்குறை, 'shortage'), and a misspelt word translates wrongly."""
    return ", ".join(c["ta"] for c in REASON_CATEGORIES if c["code"] not in ("NO_ISSUE", "OTHER"))


def _transcribe(path: str) -> str:
    segments, _ = _load().transcribe(
        path, language=LANGUAGE, task="transcribe", beam_size=5, vad_filter=True,
        condition_on_previous_text=False, no_speech_threshold=0.6, temperature=0.0,
        initial_prompt=_spelling_hint(),
    )
    parts = []
    for s in segments:
        if s.start > MAX_SECONDS:
            break
        if s.no_speech_prob > 0.8:  # Whisper invents words over silence and noise
            continue
        parts.append(s.text.strip())
    return " ".join(" ".join(parts).split())


async def to_text(path: str) -> str | None:
    """The Tamil words said in the recording, or None when the model is not set up or nothing was said."""
    if not available():
        return None
    return (await asyncio.to_thread(_transcribe, path)) or None
