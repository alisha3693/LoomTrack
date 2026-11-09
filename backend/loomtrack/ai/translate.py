"""Tamil <-> English translation on this machine, with IndicTrans2.

IndicTrans2 (AI4Bharat, MIT license) is a pair of small translation models, one for each direction. They run on the
GPU when there is one and on the CPU otherwise. Nothing leaves the machine and nothing is paid for. The weights are
downloaded once with `python -m loomtrack.ai.setup_models` (they need a free Hugging Face token); the app itself never
downloads anything. Until they are downloaded, callers get `None` and use their no-AI fallback.

A glossary of the words the floor already says is tried first for plan-step names: it is exact, and a machine
translation of a garment term can be wrong.
"""

from __future__ import annotations

import asyncio
import importlib.util
import re
import threading
import time

from .. import config

# Pinned: the model repositories ship Python code that is run when they are loaded, so the app only loads the
# commit that was looked at, never whatever is newest.
MODELS = {
    "ta-en": ("ai4bharat/indictrans2-indic-en-dist-200M", "d66a2122ad6d28184f3dc3797b652bd80ae3f65f", "tam_Taml", "eng_Latn"),
    "en-ta": ("ai4bharat/indictrans2-en-indic-dist-200M", "2cfd0a20057756d756bf3e53528f492afc52f91a", "eng_Latn", "tam_Taml"),
}
MODEL_LABEL = "IndicTrans2"
MAX_TOKENS = 256

# Words as they are said on the floor: mostly the English trade word written in Tamil letters.
GLOSSARY = {
    "cutting": "கட்டிங்", "stitching": "தையல்", "sewing": "தையல்", "printing": "பிரிண்டிங்", "embroidery": "எம்ப்ராய்டரி",
    "washing": "வாஷிங்", "finishing": "ஃபினிஷிங்", "packing": "பேக்கிங்", "checking": "செக்கிங்", "ironing": "அயர்னிங்",
    "pressing": "பிரஸ்ஸிங்", "folding": "ஃபோல்டிங்", "labelling": "லேபிளிங்", "labeling": "லேபிளிங்", "tagging": "டேகிங்",
    "knitting": "நிட்டிங்", "linking": "லிங்கிங்", "trimming": "டிரிமிங்", "dyeing": "டையிங்", "bundling": "பண்டலிங்",
    "loading": "லோடிங்", "shipping": "ஷிப்பிங்", "drying": "உலர்த்துதல்", "sorting": "சார்ட்டிங்", "marking": "மார்க்கிங்",
    "inspection": "ஆய்வு", "approval": "ஒப்புதல்", "sample": "மாதிரி", "fabric": "துணி", "quality": "தரம்", "final": "இறுதி",
    "button": "பட்டன்", "zip": "ஜிப்", "label": "லேபிள்", "tag": "டேக்", "carton": "கார்ட்டன்", "polybag": "பாலிபேக்",
    "and": "&", "&": "&",
}

_TAMIL = re.compile(r"[஀-௿]")  # the Tamil block
_WORD = re.compile(r"[A-Za-z]+|&")
_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


def has_tamil(text: str) -> bool:
    return bool(_TAMIL.search(text))


def from_glossary(name: str) -> str | None:
    """Every word known: put the Tamil words together in the same order. Otherwise None."""
    words = _WORD.findall(name)
    leftovers = re.sub(r"[A-Za-z&\s/,\-]+", "", name)
    if not words or leftovers or any(w.lower() not in GLOSSARY for w in words):
        return None
    return " ".join(GLOSSARY[w.lower()] for w in words)


# --- The models --------------------------------------------------------------------------------------------------


def libraries_installed() -> bool:
    return all(importlib.util.find_spec(m) for m in ("torch", "transformers", "sentencepiece", "indicnlp", "huggingface_hub"))


def downloaded(direction: str) -> bool:
    """The weights are in the local cache. This never touches the network."""
    from huggingface_hub import snapshot_download

    repo, revision, _, _ = MODELS[direction]
    try:
        snapshot_download(repo, revision=revision, local_files_only=True)
        return True
    except Exception:  # not there yet, or an incomplete download
        return False


def device() -> str:
    import torch

    want = config.translate_device()
    if want == "cuda" or (want == "auto" and torch.cuda.is_available()):
        if not torch.cuda.is_available():
            raise RuntimeError("LOOMTRACK_TRANSLATE_DEVICE=cuda but PyTorch cannot see a GPU (it may be the CPU-only build)")
        return "cuda"
    return "cpu"


_status_cache: tuple[float, dict] | None = None


def status(*, fresh: bool = False) -> dict:
    """{'mode': 'indictrans2', 'model', 'device'} when both directions are ready, else {'mode': 'keywords', 'reason'}."""
    global _status_cache
    if _status_cache and not fresh and time.monotonic() - _status_cache[0] < 20:
        return _status_cache[1]
    if not config.ai_enabled():
        out = {"mode": "keywords", "reason": "Translation turned off (LOOMTRACK_AI=off)"}
    elif not libraries_installed():
        out = {"mode": "keywords", "reason": "Translation libraries are not installed (pip install -r requirements-translate.txt)"}
    elif not (downloaded("ta-en") and downloaded("en-ta")):
        out = {"mode": "keywords", "reason": "Translation models are not downloaded yet (python -m loomtrack.ai.setup_models)"}
    else:
        try:
            out = {"mode": "indictrans2", "model": MODEL_LABEL, "device": device()}
        except RuntimeError as e:
            out = {"mode": "keywords", "reason": str(e)}
    _status_cache = (time.monotonic(), out)
    return out


def available() -> bool:
    return status()["mode"] == "indictrans2"


def _tidy(text: str, lang: str) -> str:
    text = " ".join(text.split())
    if lang == "eng_Latn":  # the English tokenizer leaves a gap before contractions: "haven 't" -> "haven't"
        text = re.sub(r"\s+'(t|s|re|ve|ll|d|m)\b", r"'\1", text)
    return text


class _Engine:
    """One direction: loaded on first use, then kept in memory (about 0.4 GB on the GPU)."""

    def __init__(self, direction: str):
        self.repo, self.revision, self.src, self.tgt = MODELS[direction]
        self.tok = self.model = None
        self.lock = threading.Lock()

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        dev = device()
        common = dict(trust_remote_code=True, revision=self.revision, local_files_only=True, token=config.hf_token())
        self.tok = AutoTokenizer.from_pretrained(self.repo, **common)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.repo, dtype=torch.float16 if dev == "cuda" else torch.float32, **common)
        self.model.to(dev).eval()

    @staticmethod
    def _to_model_script(text: str, lang: str) -> str:
        """IndicTrans2 reads every Indian script as Devanagari, so Tamil goes through the Unicode script map first."""
        from indicnlp.normalize.indic_normalize import IndicNormalizerFactory
        from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator

        text = IndicNormalizerFactory().get_normalizer(lang).normalize(text)
        return UnicodeIndicTransliterator.transliterate(text, lang, "hi")

    @staticmethod
    def _from_model_script(text: str, lang: str) -> str:
        from indicnlp.transliterate.unicode_transliterate import UnicodeIndicTransliterator

        return UnicodeIndicTransliterator.transliterate(text, "hi", lang)

    def translate(self, texts: list[str]) -> list[str]:
        import torch

        with self.lock:
            if self.model is None:
                self._load()
            clean = [" ".join(t.split()) for t in texts]
            if self.src == "tam_Taml":
                clean = [self._to_model_script(t, "ta") for t in clean]
            batch = [f"{self.src} {self.tgt} {t}" for t in clean]
            enc = self.tok(batch, src=True, truncation=True, padding="longest", max_length=MAX_TOKENS, return_tensors="pt").to(self.model.device)
            with torch.inference_mode():
                out = self.model.generate(**enc, num_beams=5, num_return_sequences=1, max_length=MAX_TOKENS, use_cache=False)
            with self.tok.as_target_tokenizer():
                decoded = self.tok.batch_decode(out.detach().cpu().tolist(), skip_special_tokens=True, clean_up_tokenization_spaces=True)
            if self.tgt == "tam_Taml":
                decoded = [self._from_model_script(t, "ta") for t in decoded]
            return [_tidy(t, self.tgt) for t in decoded]


_engines: dict[str, _Engine] = {}


def _engine(direction: str) -> _Engine:
    if direction not in _engines:
        _engines[direction] = _Engine(direction)
    return _engines[direction]


async def _run(direction: str, text: str) -> str:
    # The model call blocks for a fraction of a second: keep it off the event loop.
    # The models were trained on single sentences, so a longer note is translated one sentence at a time.
    parts = [p for p in _SENTENCE_END.split(text) if p.strip()] or [text]
    out = await asyncio.to_thread(lambda: _engine(direction).translate(parts))
    return " ".join(out)


async def to_english(text: str) -> str | None:
    """Tamil to English. None when the models are not ready, or when there is no Tamil in the text. Raises if the model fails."""
    text = text.strip()
    if not text or not has_tamil(text) or not available():
        return None
    return await _run("ta-en", text) or None


async def to_tamil(text: str) -> str | None:
    """English to Tamil. None when the models are not ready. Raises if the model fails."""
    text = text.strip()
    if not text or not available():
        return None
    return await _run("en-ta", text) or None


async def suggest_tamil(name: str) -> dict:
    """{'ta': text or None, 'source': 'glossary' | 'model' | None} for a plan-step name. Never raises: no suggestion is a normal answer."""
    name = " ".join(name.split())
    if len(name) < 2 or len(name) > 60:
        return {"ta": None, "source": None}
    known = from_glossary(name)
    if known:
        return {"ta": known, "source": "glossary"}
    try:
        text = await to_tamil(name)
    except Exception:
        return {"ta": None, "source": None}
    # A reply with no Tamil letters in it, or one that runs on, is not a usable name.
    if not text or not has_tamil(text) or len(text) > 60:
        return {"ta": None, "source": None}
    return {"ta": text, "source": "model"}
